#!/usr/bin/env python3
"""Evaluate grounded generation with gold and retrieved evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.chunking import chunk_document
from src.generation import (DEFAULT_BASE_URL, MODEL, OPTIONS, PROMPT_VERSION,
                            generate_answer)
from src.indexing import (DEFAULT_DIMENSIONS, EMBEDDING_MODEL, index_chunks,
                          list_indexed_chunks, open_index, retrieve_chunks)
from src.ingestion import ingest_seller_corpus

DATASET = Path('evals/datasets/eval-policy-questions-v1.json')
CALIBRATION = Path('evals/datasets/generation-judge-calibration-v1.json')
CORPUS = Path('data/raw/corpus.json')
BASELINE = Path('evals/reports/generation-baseline-v1.json')
CACHE = Path('/tmp/rag-policy-generation-current.json')
JUDGE_MODEL = 'qwen2.5:7b-instruct-q4_K_M'
JUDGE_PROMPT_VERSION = 'atomic-generation-judge-v1'
JUDGE_OPTIONS = {'temperature': 0, 'num_ctx': 8192, 'num_predict': 512}
CHUNKING = {'strategy': 'recursive', 'chunk_size': 1000, 'overlap': 100}
THRESHOLDS = {
    'calibration_agreement': 0.90,
    'calibration_kappa': 0.80,
    'unsupported_precision': 0.95,
    'unsupported_recall': 0.90,
    'gold_relevant_cases': 30,
    'gold_complete_points': 64,
    'retrieved_relevant_cases': 27,
    'retrieved_complete_points': 40,
    'retrieved_conditional_completeness': 0.90,
}
CALIBRATION_BATCH_SIZE = 8


class EvaluationError(ValueError):
    pass


class EvaluationUnavailable(RuntimeError):
    pass


def _read_json(path):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f'{path}: {exc}') from exc
    if not isinstance(value, dict):
        raise EvaluationError(f'{path}: root must be an object')
    return value


def _post_json(path, payload=None, *, timeout=180):
    url = DEFAULT_BASE_URL.rstrip('/') + path
    request = Request(url, method='GET' if payload is None else 'POST')
    if payload is not None:
        request.data = json.dumps(payload, ensure_ascii=False).encode()
        request.add_header('Content-Type', 'application/json')
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise EvaluationUnavailable(f'Ollama prerequisite unavailable: {exc}') from exc


def _sha256(paths):
    digest = hashlib.sha256()
    for path in sorted(Path(path) for path in paths):
        digest.update(str(path.relative_to(ROOT)).encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def _source_sha256():
    return _sha256([
        ROOT / 'src/ingestion.py', ROOT / 'src/chunking.py', ROOT / 'src/indexing.py',
        ROOT / 'src/generation.py', Path(__file__).resolve(),
        ROOT / 'docs/decisions/0004-phase-3-generation-evaluation.md',
        ROOT / 'docs/decisions/0005-phase-3-judge-retry-runtime.md',
        ROOT / CALIBRATION,
    ])


def _identity(item):
    return (item.get('seller_id'), item.get('document_id'),
            item.get('version'), item.get('section'))


def _model_identity(tag):
    tags = _post_json('/api/tags').get('models', [])
    model = next((item for item in tags if item.get('name') == tag or item.get('model') == tag), None)
    if model is None:
        raise EvaluationUnavailable(f'required Ollama model is not installed: {tag}')
    return {
        'requested_tag': tag,
        'resolved_name': model.get('name') or model.get('model'),
        'digest': model.get('digest'),
        'size_bytes': model.get('size'),
        'details': model.get('details'),
    }


def _call_generator(case, evidence):
    raw = {}

    def transport(url, payload, timeout):
        del url
        response = _post_json('/api/chat', payload, timeout=timeout)
        raw.update(response)
        return response

    started = time.perf_counter()
    result = generate_answer(case['seller_id'], case['query'], evidence,
                             transport=transport, timeout=180)
    return result, raw, (time.perf_counter() - started) * 1000


def _answer_sentences(answer):
    return [part.strip() for part in re.split(r'(?<=[.!?])\s+', answer.strip())
            if part.strip()]


def _judge_schema(fields, count, index_values):
    item = {
        'type': 'object',
        'properties': {'example_index': {'type': 'integer'}},
        'required': ['example_index', *fields],
        'additionalProperties': False,
    }
    for field in fields:
        item['properties'][field] = ({'type': 'boolean'} if field == 'relevant' else {
            'type': 'array', 'items': {'type': 'integer', 'enum': index_values},
            'uniqueItems': True,
        })
    return {
        'type': 'object',
        'properties': {'results': {
            'type': 'array', 'items': item, 'minItems': count, 'maxItems': count,
        }},
        'required': ['results'],
        'additionalProperties': False,
    }


def _structured_judge(messages, schema):
    payload = {'model': JUDGE_MODEL, 'messages': messages, 'stream': False,
               'format': schema, 'options': dict(JUDGE_OPTIONS)}
    started = time.perf_counter()
    raw = _post_json('/api/chat', payload, timeout=180)
    latency_ms = (time.perf_counter() - started) * 1000
    try:
        content = raw['message']['content']
        if not isinstance(content, str):
            raise TypeError
        stripped = content.strip()
        if stripped.startswith('```') and stripped.endswith('```'):
            stripped = stripped.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
        value = json.loads(stripped)
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise EvaluationError('judge returned invalid structured output') from exc
    if not isinstance(value, dict) or set(value) != {'results'}:
        raise EvaluationError('judge output has unexpected fields')
    return value['results'], raw, latency_ms


def _validated_results(results, items, fields, bounds):
    if not isinstance(results, list) or len(results) != len(items):
        raise EvaluationError('judge returned the wrong result count')
    by_index = {}
    expected_fields = {'example_index', *fields}
    for result in results:
        if not isinstance(result, dict) or set(result) != expected_fields:
            raise EvaluationError('judge result has unexpected fields')
        index = result['example_index']
        if not isinstance(index, int) or isinstance(index, bool) or index in by_index:
            raise EvaluationError('judge returned an invalid example_index')
        by_index[index] = result
    if set(by_index) != set(range(len(items))):
        raise EvaluationError('judge omitted or invented an example_index')
    ordered = []
    for index, item in enumerate(items):
        result = by_index[index]
        for field in fields:
            if field == 'relevant':
                if not isinstance(result[field], bool):
                    raise EvaluationError('judge returned invalid relevance')
                continue
            values = result[field]
            valid = set(range(bounds(field, item)))
            if (not isinstance(values, list) or any(
                    not isinstance(value, int) or isinstance(value, bool) or value not in valid
                    for value in values)):
                raise EvaluationError(f'judge returned invalid {field}: {values!r}')
            result[field] = sorted(set(values))
        ordered.append(result)
    return ordered


def _support_judge(items):
    inputs = []
    for example_index, (case, evidence, generated) in enumerate(items):
        by_id = {f'E{position}': item for position, item in enumerate(evidence[:5], 1)}
        sentences = _answer_sentences(generated['answer'])
        inputs.append({
            'example_index': example_index,
            'question': case['query'],
            'cited_evidence': [
                {'evidence_id': evidence_id, 'text': by_id[evidence_id]['text']}
                for evidence_id in generated['evidence_ids']
            ],
            'answer_sentences': [{'sentence_index': index, 'text': sentence}
                                 for index, sentence in enumerate(sentences)],
        })
    fields = ('supported_sentence_indices', 'relevant')
    sentence_counts = {len(item['answer_sentences']) for item in inputs}
    if len(sentence_counts) != 1:
        raise EvaluationError('support judge batch must have a uniform sentence count')
    schema = _judge_schema(fields, len(items), list(range(sentence_counts.pop())))
    messages = [
        {'role': 'system', 'content': (
            'Evaluate only sentence support and answer relevance. For each example, mark a '
            'sentence supported only when every factual part is entailed by at least one cited '
            'evidence item. Accept faithful paraphrases. A compound sentence with any unsupported '
            'part is unsupported. Do not penalize omitted facts or require facts not stated in the '
            'answer. Relevant means the answer directly addresses the question. Copy each '
            'example_index exactly and use only sentence_index values listed in that same example. '
            'Return one result for every example_index and only the requested JSON.')},
        {'role': 'user', 'content': json.dumps({'examples': inputs}, ensure_ascii=False,
                                               separators=(',', ':'))},
    ]
    results, raw, latency = _structured_judge(messages, schema)
    return _validated_results(
        results, inputs, fields,
        lambda field, item: len(item['answer_sentences']) if field.startswith('supported') else 0,
    ), raw, latency


def _coverage_judge(items):
    inputs = []
    for example_index, (case, evidence, generated) in enumerate(items):
        sentences = _answer_sentences(generated['answer'])
        inputs.append({
            'example_index': example_index,
            'question': case['query'],
            'expected_answer_points': [
                {'point_index': index, 'text': point}
                for index, point in enumerate(case['expected_answer_points'])
            ],
            'evidence': [item['text'] for item in evidence[:5]],
            'answer_sentences': [{'sentence_index': index, 'text': sentence}
                                 for index, sentence in enumerate(sentences)],
        })
    fields = ('available_answer_point_indices', 'covered_answer_point_indices')
    point_counts = {len(item['expected_answer_points']) for item in inputs}
    if len(point_counts) != 1:
        raise EvaluationError('coverage judge batch must have a uniform answer-point count')
    schema = _judge_schema(fields, len(items), list(range(point_counts.pop())))
    messages = [
        {'role': 'system', 'content': (
            'Evaluate only answer-point availability and coverage. An expected point is available '
            'when the supplied evidence entails it. It is covered when the answer states the same '
            'meaning without contradiction. Covered must be a subset of available. Do not judge '
            'citation selection or add missing points. Copy each example_index exactly and use '
            'only point_index values listed in that same example. Return one result for every '
            'example_index and only the requested JSON.')},
        {'role': 'user', 'content': json.dumps({'examples': inputs}, ensure_ascii=False,
                                               separators=(',', ':'))},
    ]
    results, raw, latency = _structured_judge(messages, schema)
    results = _validated_results(
        results, inputs, fields, lambda field, item: len(item['expected_answer_points']))
    for result in results:
        available = set(result['available_answer_point_indices'])
        result['covered_answer_point_indices'] = [
            value for value in result['covered_answer_point_indices'] if value in available]
    return results, raw, latency


def _judge(case, evidence, generated):
    items = [(case, evidence, generated)]
    support, support_raw, support_ms = _support_judge(items)
    coverage, coverage_raw, coverage_ms = _coverage_judge(items)
    sentences = _answer_sentences(generated['answer'])
    supported = set(support[0]['supported_sentence_indices'])
    unsupported = [sentence for index, sentence in enumerate(sentences) if index not in supported]
    judgment = {
        'faithful': not unsupported,
        'relevant': support[0]['relevant'],
        'citation_correct': not unsupported,
        'available_answer_point_indices': coverage[0]['available_answer_point_indices'],
        'covered_answer_point_indices': coverage[0]['covered_answer_point_indices'],
        'unsupported_claims': unsupported,
    }
    return judgment, {'support': support_raw, 'coverage': coverage_raw}, support_ms + coverage_ms


def _human_authored_calibration(cases, gold_by_case, calibration):
    rows = calibration.get('cases')
    if not isinstance(rows, list) or len(rows) != 31:
        raise EvaluationError('judge calibration requires exactly 31 case definitions')
    if len({row.get('case_id') for row in rows}) != 31:
        raise EvaluationError('judge calibration case IDs must be unique')
    if sum(row.get('split') == 'holdout' for row in rows) != 10:
        raise EvaluationError('judge calibration requires exactly 10 holdout cases')
    examples = []
    for row in rows:
        case_id = row.get('case_id')
        if case_id not in cases or row.get('split') not in {'tune', 'holdout'}:
            raise EvaluationError('judge calibration references an invalid case or split')
        negative = row.get('unsupported_sentence')
        if not isinstance(negative, str) or not negative.strip():
            raise EvaluationError('judge calibration requires an unsupported sentence')
        case = cases[case_id]
        evidence = gold_by_case[case_id]
        evidence_ids = [f'E{position}' for position in range(1, len(evidence) + 1)]
        point_sentences = [point.rstrip('.!?') + '.' for point in case['expected_answer_points']]
        all_points = list(range(len(point_sentences)))
        examples.extend([
            {'case': case, 'evidence': evidence,
             'generated': {'answer': ' '.join(point_sentences), 'evidence_ids': evidence_ids},
             'split': row['split'], 'kind': 'supported',
             'expected_supported': all_points, 'expected_relevant': True,
             'expected_available': all_points, 'expected_covered': all_points},
            {'case': case, 'evidence': evidence,
             'generated': {'answer': f'{point_sentences[0]} {negative.strip()}',
                           'evidence_ids': evidence_ids},
             'split': row['split'], 'kind': 'unsupported',
             'expected_supported': [0], 'expected_relevant': True,
             'expected_available': all_points, 'expected_covered': [0]},
        ])
    return examples


def _kappa(expected, actual):
    if len(expected) != len(actual) or not expected:
        raise EvaluationError('calibration labels must be non-empty and aligned')
    agreement = sum(left == right for left, right in zip(expected, actual)) / len(expected)
    expected_true = sum(expected) / len(expected)
    actual_true = sum(actual) / len(actual)
    chance = expected_true * actual_true + (1 - expected_true) * (1 - actual_true)
    return agreement, (agreement - chance) / (1 - chance) if chance != 1 else 1.0


def _calibration_metrics(rows):
    expected_labels = []
    actual_labels = []
    true_unsupported = false_unsupported = missed_unsupported = 0
    for row in rows:
        expected_supported = set(row['expected']['supported_sentence_indices'])
        actual_supported = set(row['actual']['supported_sentence_indices'])
        sentence_count = row['sentence_count']
        for index in range(sentence_count):
            expected = index in expected_supported
            actual = index in actual_supported
            expected_labels.append(expected)
            actual_labels.append(actual)
            if not expected and not actual:
                true_unsupported += 1
            elif expected and not actual:
                false_unsupported += 1
            elif not expected and actual:
                missed_unsupported += 1
        expected_labels.append(row['expected']['relevant'])
        actual_labels.append(row['actual']['relevant'])
        for field in ('available_answer_point_indices', 'covered_answer_point_indices'):
            expected_indices = set(row['expected'][field])
            actual_indices = set(row['actual'][field])
            for index in range(row['point_count']):
                expected_labels.append(index in expected_indices)
                actual_labels.append(index in actual_indices)
    agreement, kappa = _kappa(expected_labels, actual_labels)
    precision_denominator = true_unsupported + false_unsupported
    recall_denominator = true_unsupported + missed_unsupported
    return {
        'example_count': len(rows), 'label_count': len(expected_labels),
        'agreement': agreement, 'cohens_kappa': kappa,
        'unsupported_precision': (true_unsupported / precision_denominator
                                  if precision_denominator else 1.0),
        'unsupported_recall': (true_unsupported / recall_denominator
                               if recall_denominator else 1.0),
        'false_unsupported_count': false_unsupported,
    }


def _calibrate(cases, gold_by_case, calibration):
    examples = _human_authored_calibration(cases, gold_by_case, calibration)
    calls = []
    support_by_index = {}
    coverage_by_index = {}
    indexed = list(enumerate(examples))
    for kind, output, judge, size in (
            ('support', support_by_index, _support_judge,
             lambda example: len(_answer_sentences(example['generated']['answer']))),
            ('coverage', coverage_by_index, _coverage_judge,
             lambda example: len(example['case']['expected_answer_points']))):
        for item_size in sorted({size(example) for example in examples}):
            group = [(index, example) for index, example in indexed
                     if size(example) == item_size]
            for start in range(0, len(group), CALIBRATION_BATCH_SIZE):
                batch = group[start:start + CALIBRATION_BATCH_SIZE]
                items = [(example['case'], example['evidence'], example['generated'])
                         for _, example in batch]
                results, raw, latency_ms = judge(items)
                calls.append({'kind': kind, 'latency_ms': latency_ms,
                              'prompt_eval_count': raw.get('prompt_eval_count'),
                              'eval_count': raw.get('eval_count')})
                for offset, (index, _) in enumerate(batch):
                    output[index] = results[offset]
    rows = []
    for index, example in indexed:
        support = support_by_index[index]
        coverage = coverage_by_index[index]
        sentences = _answer_sentences(example['generated']['answer'])
        rows.append({
            'case_id': example['case']['case_id'], 'split': example['split'],
            'kind': example['kind'], 'sentence_count': len(sentences),
            'point_count': len(example['case']['expected_answer_points']),
            'expected': {
                'supported_sentence_indices': example['expected_supported'],
                'relevant': example['expected_relevant'],
                'available_answer_point_indices': example['expected_available'],
                'covered_answer_point_indices': example['expected_covered'],
            },
            'actual': {
                'supported_sentence_indices': support['supported_sentence_indices'],
                'relevant': support['relevant'],
                'available_answer_point_indices':
                    coverage['available_answer_point_indices'],
                'covered_answer_point_indices':
                    coverage['covered_answer_point_indices'],
            },
        })
    overall = _calibration_metrics(rows)
    holdout = _calibration_metrics([row for row in rows if row['split'] == 'holdout'])
    return {**overall, 'holdout': holdout, 'examples': rows, 'calls': calls}


def _view_metrics(results):
    available = sum(len(item['judgment']['available_answer_point_indices']) for item in results)
    covered = sum(len(item['judgment']['covered_answer_point_indices']) for item in results)
    unsupported = sum(len(item['judgment']['unsupported_claims']) for item in results)
    return {
        'case_count': len(results),
        'faithful_cases': sum(item['judgment']['faithful'] for item in results),
        'relevant_cases': sum(item['judgment']['relevant'] for item in results),
        'citation_correct_cases': sum(item['judgment']['citation_correct'] for item in results),
        'available_answer_points': available,
        'covered_answer_points': covered,
        'conditional_completeness': covered / available if available else None,
        'unsupported_claim_count': unsupported,
    }


def _percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


def _usage(results, calibration):
    generations = [item['generation'] for item in results]
    judgments = [item[kind] for item in results
                 for kind in ('support_judge', 'coverage_judge')]
    calibration_calls = calibration['calls']
    return {
        'generation_prompt_tokens': sum(item.get('prompt_eval_count') or 0 for item in generations),
        'generation_output_tokens': sum(item.get('eval_count') or 0 for item in generations),
        'judge_prompt_tokens': sum(item.get('prompt_eval_count') or 0
                                   for item in judgments + calibration_calls),
        'judge_output_tokens': sum(item.get('eval_count') or 0
                                   for item in judgments + calibration_calls),
    }


def _passes(calibration, gold, retrieved, failures, leakage_count):
    return (
        not failures and leakage_count == 0 and
        calibration['agreement'] >= THRESHOLDS['calibration_agreement'] and
        calibration['cohens_kappa'] >= THRESHOLDS['calibration_kappa'] and
        calibration['unsupported_precision'] >= THRESHOLDS['unsupported_precision'] and
        calibration['unsupported_recall'] >= THRESHOLDS['unsupported_recall'] and
        calibration['false_unsupported_count'] == 0 and
        calibration['holdout']['agreement'] >= THRESHOLDS['calibration_agreement'] and
        calibration['holdout']['cohens_kappa'] >= THRESHOLDS['calibration_kappa'] and
        calibration['holdout']['unsupported_precision'] >=
        THRESHOLDS['unsupported_precision'] and
        calibration['holdout']['unsupported_recall'] >= THRESHOLDS['unsupported_recall'] and
        calibration['holdout']['false_unsupported_count'] == 0 and
        gold['case_count'] == 31 and gold['faithful_cases'] == 31 and
        gold['citation_correct_cases'] == 31 and gold['unsupported_claim_count'] == 0 and
        gold['relevant_cases'] >= THRESHOLDS['gold_relevant_cases'] and
        gold['covered_answer_points'] >= THRESHOLDS['gold_complete_points'] and
        retrieved['case_count'] == 31 and retrieved['faithful_cases'] == 31 and
        retrieved['citation_correct_cases'] == 31 and
        retrieved['unsupported_claim_count'] == 0 and
        retrieved['relevant_cases'] >= THRESHOLDS['retrieved_relevant_cases'] and
        retrieved['covered_answer_points'] >= THRESHOLDS['retrieved_complete_points'] and
        retrieved['conditional_completeness'] is not None and
        retrieved['conditional_completeness'] >=
        THRESHOLDS['retrieved_conditional_completeness']
    )


def evaluate(root=ROOT, *, measured_at=None):
    root = Path(root)
    dataset_path = root / DATASET
    calibration_path = root / CALIBRATION
    corpus_path = root / CORPUS
    dataset = _read_json(dataset_path)
    calibration_fixture = _read_json(calibration_path)
    corpus = _read_json(corpus_path)
    answerable = [case for case in dataset.get('cases', []) if case.get('answerable') is True]
    if len(answerable) != 31:
        raise EvaluationError('generation evaluation requires exactly 31 answerable cases')
    cases = {case['case_id']: case for case in answerable}

    connection = open_index()
    for seller in corpus.get('sellers', []):
        seller_id = seller['seller_id']
        chunks = [chunk for document in ingest_seller_corpus(seller_id, root=root)
                  for chunk in chunk_document(document, **CHUNKING)]
        index_chunks(connection, seller_id, chunks, dimensions=DEFAULT_DIMENSIONS)

    indexed = {seller['seller_id']: list_indexed_chunks(connection, seller['seller_id'])
               for seller in corpus['sellers']}
    gold_by_case = {}
    for case in answerable:
        expected = {_identity(item) for item in case['expected_source_identity']}
        gold = [item for item in indexed[case['seller_id']] if _identity(item) in expected]
        if not gold or len(gold) > 5:
            raise EvaluationError(f"{case['case_id']}: expected 1-5 gold evidence chunks")
        gold_by_case[case['case_id']] = gold

    runtime = {
        'ollama_version': _post_json('/api/version').get('version'),
        'generator': _model_identity(MODEL),
        'judge': _model_identity(JUDGE_MODEL),
    }
    calibration = _calibrate(cases, gold_by_case, calibration_fixture)
    results = []
    failures = []
    leakage_count = 0
    for case in answerable:
        retrieved = retrieve_chunks(connection, case['seller_id'], case['query'], top_k=5)
        for view, evidence in (('gold', gold_by_case[case['case_id']]),
                               ('retrieved', retrieved)):
            try:
                leakage = [item for item in evidence if item.get('seller_id') != case['seller_id']]
                leakage_count += len(leakage)
                generated, generation_raw, generation_ms = _call_generator(case, evidence)
                judgment, judge_raw, judge_ms = _judge(case, evidence, generated)
                results.append({
                    'case_id': case['case_id'], 'view': view,
                    'expected_answer_points': case['expected_answer_points'],
                    'expected_source_identity': case['expected_source_identity'],
                    'evidence_identity': [dict(seller_id=item.get('seller_id'),
                                               document_id=item.get('document_id'),
                                               document_name=item.get('document_name'),
                                               version=item.get('version'),
                                               section=item.get('section'), page=item.get('page'))
                                          for item in evidence],
                    'answer': generated['answer'], 'citations': generated['citations'],
                    'judgment': judgment,
                    'generation_latency_ms': generation_ms, 'judge_latency_ms': judge_ms,
                    'generation': {key: generation_raw.get(key) for key in
                                   ('total_duration', 'load_duration', 'prompt_eval_count',
                                    'prompt_eval_duration', 'eval_count', 'eval_duration')},
                    'support_judge': {key: judge_raw['support'].get(key) for key in
                                      ('total_duration', 'load_duration', 'prompt_eval_count',
                                       'prompt_eval_duration', 'eval_count', 'eval_duration')},
                    'coverage_judge': {key: judge_raw['coverage'].get(key) for key in
                                       ('total_duration', 'load_duration', 'prompt_eval_count',
                                        'prompt_eval_duration', 'eval_count', 'eval_duration')},
                })
            except Exception as exc:
                failures.append({'case_id': case['case_id'], 'view': view, 'error': str(exc)})

    gold_results = [item for item in results if item['view'] == 'gold']
    retrieved_results = [item for item in results if item['view'] == 'retrieved']
    gold_metrics = _view_metrics(gold_results)
    retrieved_metrics = _view_metrics(retrieved_results)
    generation_latencies = [item['generation_latency_ms'] for item in results]
    judge_latencies = [item['judge_latency_ms'] for item in results]
    measured_at = measured_at or datetime.now(timezone.utc).isoformat()
    source_sha = _source_sha256()
    passed = _passes(calibration, gold_metrics, retrieved_metrics, failures, leakage_count)
    report = {
        'report_schema_version': 1,
        'report_id': 'generation-baseline-' + source_sha[:16],
        'measured_at': measured_at,
        'command': ['python3', 'scripts/evaluate_generation.py', '--gate', 'generation'],
        'status': 'passed' if passed else 'failed',
        'baseline_role': 'initial_generation_baseline',
        'dataset': {'id': dataset.get('dataset_id'), 'version': dataset.get('dataset_version'),
                    'sha256': _sha256([dataset_path])},
        'judge_calibration_dataset': {
            'id': calibration_fixture.get('calibration_id'),
            'version': calibration_fixture.get('calibration_version'),
            'sha256': _sha256([calibration_path]),
        },
        'corpus': {'id': corpus.get('corpus_id'), 'version': corpus.get('corpus_version'),
                   'sha256': _sha256([corpus_path, *sorted((root / 'data/raw').glob('*/*.md'))])},
        'source_sha256': source_sha,
        'configuration': {
            'chunking': CHUNKING,
            'embedding': {'model': EMBEDDING_MODEL, 'dimensions': DEFAULT_DIMENSIONS},
            'retrieval': {'method': 'dense_cosine', 'top_k': 5},
            'generator': {'model': MODEL, 'prompt_version': PROMPT_VERSION, 'options': OPTIONS},
            'judge': {'model': JUDGE_MODEL, 'prompt_version': JUDGE_PROMPT_VERSION,
                      'options': JUDGE_OPTIONS},
            'thresholds': THRESHOLDS,
        },
        'runtime': runtime,
        'counts': {'collected_cases': 31, 'views_per_case': 2, 'expected_outputs': 62,
                   'executed_outputs': len(results), 'skipped_outputs': 0,
                   'failed_outputs': len(failures), 'calibration_examples': 62,
                   'calibration_judge_calls': len(calibration['calls'])},
        'calibration': calibration,
        'metrics': {
            'gold': gold_metrics, 'retrieved': retrieved_metrics,
            'seller_leakage_count': leakage_count,
            'error_rate': len(failures) / 62,
            'latency_ms': {
                'generation_mean': sum(generation_latencies) / len(generation_latencies)
                if generation_latencies else None,
                'generation_p95': _percentile(generation_latencies, 0.95),
                'judge_mean': sum(judge_latencies) / len(judge_latencies)
                if judge_latencies else None,
                'judge_p95': _percentile(judge_latencies, 0.95),
            },
            'token_usage': _usage(results, calibration),
            'cost_per_query_usd': 0.0,
        },
        'failures': failures,
        'cases': results,
        'baseline_comparison': {'reference_report_id': None, 'regressions': [],
                                'metric_deltas': None},
    }
    return report


def _stable_metrics(report):
    return {
        'gold': report['metrics']['gold'],
        'retrieved': report['metrics']['retrieved'],
        'seller_leakage_count': report['metrics']['seller_leakage_count'],
        'error_rate': report['metrics']['error_rate'],
        'calibration_agreement': report['calibration']['agreement'],
        'calibration_kappa': report['calibration']['cohens_kappa'],
    }


def compare_to_baseline(report, baseline):
    regressions = []
    baseline_passes = {(item['case_id'], item['view']): item['judgment']
                       for item in baseline['cases']}
    for item in report['cases']:
        prior = baseline_passes.get((item['case_id'], item['view']))
        if prior and prior['faithful'] and not item['judgment']['faithful']:
            regressions.append({'case_id': item['case_id'], 'view': item['view'],
                                'metric': 'faithfulness'})
        if prior and prior['citation_correct'] and not item['judgment']['citation_correct']:
            regressions.append({'case_id': item['case_id'], 'view': item['view'],
                                'metric': 'citation_correctness'})
    current = _stable_metrics(report)
    previous = _stable_metrics(baseline)
    deltas = {}
    for view in ('gold', 'retrieved'):
        deltas[view] = {key: current[view][key] - previous[view][key]
                        for key in current[view] if isinstance(current[view][key], (int, float))
                        and isinstance(previous[view].get(key), (int, float))}
    report['baseline_comparison'] = {
        'reference_report_id': baseline['report_id'],
        'regressions': regressions,
        'metric_deltas': deltas,
    }
    if regressions:
        report['status'] = 'failed'
    return not regressions


def _load_or_run(force=False):
    source_sha = _source_sha256()
    if not force and CACHE.is_file():
        cached = _read_json(CACHE)
        if cached.get('source_sha256') == source_sha:
            return cached
    report = evaluate()
    CACHE.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gate', choices=('generation', 'regression', 'system'),
                        default='generation')
    parser.add_argument('--write-baseline', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = _load_or_run(force=args.gate == 'generation')
        baseline_path = ROOT / BASELINE
        if args.write_baseline:
            if report['status'] != 'passed':
                raise EvaluationError('refusing to pin a failing generation baseline')
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        elif not baseline_path.is_file():
            raise EvaluationError('generation baseline report is missing')
        else:
            baseline = _read_json(baseline_path)
            compare_to_baseline(report, baseline)

        if args.gate == 'regression':
            passed = report['status'] == 'passed' and not report['baseline_comparison']['regressions']
        elif args.gate == 'system':
            metrics = report['metrics']
            passed = (report['status'] == 'passed' and metrics['error_rate'] == 0 and
                      metrics['seller_leakage_count'] == 0 and
                      all(value is not None for value in metrics['latency_ms'].values()) and
                      all(value is not None for value in metrics['token_usage'].values()))
        else:
            passed = report['status'] == 'passed'
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if passed else 1
    except EvaluationUnavailable as exc:
        print(json.dumps({'status': 'unavailable', 'error': str(exc)}, indent=2), file=sys.stderr)
        return 3
    except EvaluationError as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
