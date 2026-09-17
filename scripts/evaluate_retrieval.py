#!/usr/bin/env python3
"""Measure and reproduce the fixed dense-retrieval baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.chunking import chunk_document
from src.indexing import DEFAULT_DIMENSIONS, EMBEDDING_MODEL, index_chunks, open_index, retrieve_chunks
from src.ingestion import ingest_seller_corpus

DATASET = Path('evals/datasets/eval-policy-questions-v1.json')
CORPUS = Path('data/raw/corpus.json')
BASELINE = Path('evals/reports/retrieval-baseline-v1.json')
CONFIG = {
    'chunking': {'strategy': 'recursive', 'chunk_size': 1000, 'overlap': 100},
    'embedding': {'model': EMBEDDING_MODEL, 'dimensions': DEFAULT_DIMENSIONS},
    'retrieval': {'method': 'dense_cosine', 'top_k': 10, 'recall_k': 5, 'mrr_k': 10},
    'seed': None,
}


class EvaluationError(ValueError):
    pass


def _read_json(path):
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f'{path}: {exc}') from exc
    if not isinstance(value, dict):
        raise EvaluationError(f'{path}: root must be an object')
    return value


def _sha256(paths):
    digest = hashlib.sha256()
    for path in sorted(paths):
        relative = path.relative_to(ROOT)
        digest.update(str(relative).encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def _identity(item):
    return (item.get('seller_id'), item.get('document_id'), item.get('version'), item.get('section'))


def _grade(case, retrieved):
    expected = {_identity(item) for item in case['expected_source_identity']}
    leakage = [item for item in retrieved if item.get('seller_id') != case['seller_id']]
    if not expected:
        return None, None, [], leakage
    top_five = {_identity(item) for item in retrieved[:5]}
    recall = len(expected & top_five) / len(expected)
    first_rank = next((rank for rank, item in enumerate(retrieved[:10], 1)
                       if _identity(item) in expected), None)
    return recall, 1 / first_rank if first_rank else 0.0, sorted(expected & top_five), leakage


def evaluate(root=ROOT, *, measured_at=None):
    global ROOT
    original_root = ROOT
    ROOT = Path(root)
    try:
        dataset_path = ROOT / DATASET
        corpus_path = ROOT / CORPUS
        dataset = _read_json(dataset_path)
        corpus = _read_json(corpus_path)
        cases = dataset.get('cases')
        sellers = corpus.get('sellers')
        if not isinstance(cases, list) or not cases:
            raise EvaluationError('dataset cases must be non-empty')
        if not isinstance(sellers, list) or not sellers:
            raise EvaluationError('corpus sellers must be non-empty')

        connection = open_index()
        indexed_chunks = 0
        for seller in sellers:
            seller_id = seller['seller_id']
            chunks = [chunk for document in ingest_seller_corpus(seller_id, root=ROOT)
                      for chunk in chunk_document(document, **CONFIG['chunking'])]
            index_chunks(connection, seller_id, chunks, dimensions=CONFIG['embedding']['dimensions'])
            indexed_chunks += len(chunks)

        results = []
        recall_values = []
        reciprocal_ranks = []
        latencies = []
        failures = []
        leakage_count = 0
        for case in cases:
            started = time.perf_counter()
            try:
                retrieved = retrieve_chunks(
                    connection, case['seller_id'], case['query'],
                    top_k=CONFIG['retrieval']['top_k'])
                latency_ms = (time.perf_counter() - started) * 1000
                recall, reciprocal_rank, matched, leakage = _grade(case, retrieved)
                if recall is not None:
                    recall_values.append(recall)
                    reciprocal_ranks.append(reciprocal_rank)
                leakage_count += len(leakage)
                results.append({
                    'case_id': case['case_id'],
                    'seller_id': case['seller_id'],
                    'answerable': case['answerable'],
                    'expected_evidence': case['expected_source_identity'],
                    'retrieved_evidence': [{
                        'rank': rank,
                        'seller_id': item.get('seller_id'),
                        'document_id': item.get('document_id'),
                        'document_name': item.get('document_name'),
                        'version': item.get('version'),
                        'section': item.get('section'),
                        'chunk_id': item.get('chunk_id'),
                        'score': item['score'],
                    } for rank, item in enumerate(retrieved, 1)],
                    'matched_at_5': [dict(zip(
                        ('seller_id', 'document_id', 'version', 'section'), item))
                        for item in matched],
                    'recall_at_5': recall,
                    'reciprocal_rank_at_10': reciprocal_rank,
                    'retrieval_latency_ms': latency_ms,
                    'failure_reason': 'seller_leakage' if leakage else None,
                })
                latencies.append(latency_ms)
            except Exception as exc:  # Preserve every case failure in the report.
                failures.append({'case_id': case.get('case_id'), 'error': str(exc)})

        measured_at = measured_at or datetime.now(timezone.utc).isoformat()
        stable_identity = {
            'dataset_sha256': _sha256([dataset_path]),
            'corpus_sha256': _sha256([corpus_path, *sorted((ROOT / 'data/raw').glob('*/*.md'))]),
            'source_sha256': _sha256([ROOT / 'src/ingestion.py', ROOT / 'src/chunking.py',
                                      ROOT / 'src/indexing.py', Path(__file__).resolve()]),
            'configuration': CONFIG,
        }
        run_id = hashlib.sha256(json.dumps(stable_identity, sort_keys=True).encode()).hexdigest()[:16]
        sorted_latencies = sorted(latencies)
        metrics = {
            'recall_at_5': sum(recall_values) / len(recall_values) if recall_values else None,
            'mrr_at_10': sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else None,
            'graded_case_count': len(recall_values),
            'ungraded_case_count': len(cases) - len(recall_values),
            'seller_leakage_count': leakage_count,
            'error_rate': len(failures) / len(cases),
            'retrieval_latency_ms': {
                'mean': sum(latencies) / len(latencies) if latencies else None,
                'p50': sorted_latencies[len(sorted_latencies) // 2] if sorted_latencies else None,
            },
            'end_to_end_latency_ms': None,
            'llm_latency_ms': None,
            'token_usage': None,
            'cost_per_query': None,
        }
        status = ('passed' if len(results) == len(cases) and not failures and not leakage_count
                  and recall_values else 'failed')
        return {
            'report_schema_version': 1,
            'report_id': f'dense-baseline-{run_id}',
            'run_id': run_id,
            'measured_at': measured_at,
            'command': ['python3', 'scripts/evaluate_retrieval.py'],
            'status': status,
            'baseline_role': 'initial_dense_baseline',
            'acceptance_policy': {
                'name': 'complete_measurement_v1',
                'criteria': ['all cases executed', 'no skipped cases', 'no evaluation errors',
                             'no cross-seller evidence', 'Recall@5 and MRR@10 recorded'],
                'numeric_quality_floor': None,
                'note': 'The first baseline records quality; future changes compare against it.',
            },
            'dataset': {'id': dataset.get('dataset_id'), 'version': dataset.get('dataset_version'),
                        'sha256': stable_identity['dataset_sha256']},
            'corpus': {'id': corpus.get('corpus_id'), 'version': corpus.get('corpus_version'),
                       'sha256': stable_identity['corpus_sha256']},
            'source_sha256': stable_identity['source_sha256'],
            'configuration': CONFIG,
            'counts': {'collected': len(cases), 'executed': len(results), 'skipped': 0,
                       'failed': len(failures), 'indexed_chunks': indexed_chunks},
            'grading': {
                'method': 'exact seller_id/document_id/version/section identity',
                'version': 'retrieval-evidence-identity-v1',
                'recall_at_5': 'mean fraction of expected identities present in the first 5 results',
                'mrr_at_10': 'mean reciprocal rank of the first expected identity in the first 10 results',
                'empty_expected_evidence': 'executed and reported, excluded from both metric denominators',
            },
            'metrics': metrics,
            'failures': failures,
            'cases': results,
            'baseline_comparison': {'reference_report_id': None, 'metric_deltas': None,
                                    'regressions': None,
                                    'note': 'Initial baseline; no earlier comparable report exists.'},
        }
    finally:
        ROOT = original_root


def _stable_report(report):
    stable = json.loads(json.dumps(report))
    stable.pop('measured_at', None)
    stable['metrics'].pop('retrieval_latency_ms', None)
    for case in stable['cases']:
        case.pop('retrieval_latency_ms', None)
    return stable


def matches_baseline(current, baseline):
    return _stable_report(current) == _stable_report(baseline)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-baseline', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = evaluate()
        baseline_path = ROOT / BASELINE
        if args.write_baseline:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        else:
            baseline = _read_json(baseline_path)
            if not matches_baseline(report, baseline):
                report['status'] = 'failed'
                report['failures'].append({'case_id': None, 'error': 'current results differ from pinned baseline'})
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report['status'] == 'passed' else 1
    except EvaluationError as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
