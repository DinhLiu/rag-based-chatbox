#!/usr/bin/env python3
"""Validate the fixed Phase 1 corpus and evaluation-question annotations."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = Path('data/raw/corpus.json')
DATASET = Path('evals/datasets/eval-policy-questions-v1.json')
CATEGORIES = {
    'simple': 0.40,
    'paraphrased': 0.20,
    'multi_policy': 0.15,
    'unanswerable': 0.15,
    'ambiguous_adversarial': 0.10,
}
STOP_WORDS = {
    'after', 'and', 'are', 'before', 'for', 'from', 'has', 'have', 'into',
    'may', 'must', 'only', 'that', 'the', 'their', 'this', 'was', 'when',
    'with',
}


def load_json(path, errors):
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f'{path}: {exc}')
        return {}
    if not isinstance(value, dict):
        errors.append(f'{path}: root must be an object')
        return {}
    return value


def sections(text):
    found = {}
    for part in re.split(r'(?m)^## ', text)[1:]:
        heading, _, body = part.partition('\n')
        name = heading.split(' — ', 1)[0].strip()
        found[name] = body.strip()
    return found


def words(text):
    return {word for word in re.findall(r'[a-z0-9@.$%]+', text.lower())
            if len(word) > 2 and word not in STOP_WORDS}


def validate(root=ROOT):
    errors = []
    corpus_path = root / CORPUS
    dataset_path = root / DATASET
    corpus = load_json(corpus_path, errors)
    dataset = load_json(dataset_path, errors)
    documents = {}
    seller_names = {}

    sellers = corpus.get('sellers')
    if not isinstance(sellers, list) or not sellers:
        errors.append('corpus: sellers must be a non-empty list')
        sellers = []
    for seller in sellers:
        if not isinstance(seller, dict):
            errors.append('corpus: each seller must be an object')
            continue
        seller_id = seller.get('seller_id')
        seller_name = seller.get('seller_name')
        if not isinstance(seller_id, str) or not seller_id.strip() or seller_id in seller_names:
            errors.append(f'corpus: invalid or duplicate seller_id {seller_id!r}')
            continue
        seller_names[seller_id] = seller_name
        listed = seller.get('documents')
        if not isinstance(listed, list) or not listed:
            errors.append(f'corpus: {seller_id} documents must be a non-empty list')
            continue
        for document in listed:
            if not isinstance(document, dict):
                errors.append(f'corpus: {seller_id} document must be an object')
                continue
            document_id = document.get('document_id')
            version = document.get('version')
            identity = (seller_id, document_id, version)
            if not all(isinstance(value, str) and value.strip() for value in identity):
                errors.append(f'corpus: invalid identity {identity!r}')
                continue
            if identity in documents:
                errors.append(f'corpus: duplicate identity {identity!r}')
                continue
            relative = document.get('path')
            expected_parent = Path(seller_id)
            if (not isinstance(relative, str) or Path(relative).is_absolute()
                    or '..' in Path(relative).parts or Path(relative).parent != expected_parent):
                errors.append(f'corpus: {identity!r} has invalid seller-scoped path {relative!r}')
                continue
            path = corpus_path.parent / relative
            try:
                text = path.read_text()
            except OSError as exc:
                errors.append(f'corpus: {identity!r} cannot read {relative}: {exc}')
                continue
            document_name = document.get('document_name')
            if not text.strip():
                errors.append(f'corpus: {identity!r} document is empty')
            if not text.startswith(f'# {document_name}\n'):
                errors.append(f'corpus: {identity!r} title does not match document_name')
            if f'Seller: {seller_name}' not in text:
                errors.append(f'corpus: {identity!r} seller header does not match catalog')
            if f'Version: {version}' not in text:
                errors.append(f'corpus: {identity!r} version header does not match catalog')
            parsed_sections = sections(text)
            if not parsed_sections:
                errors.append(f'corpus: {identity!r} has no sections')
            documents[identity] = (document, parsed_sections)

    for field in ('corpus_id', 'corpus_version'):
        if not isinstance(corpus.get(field), str) or not corpus[field].strip():
            errors.append(f'corpus: {field} must be a non-empty string')
    if dataset.get('corpus_id') != corpus.get('corpus_id'):
        errors.append('dataset: corpus_id does not match corpus catalog')
    if dataset.get('corpus_version') != corpus.get('corpus_version'):
        errors.append('dataset: corpus_version does not match corpus catalog')
    for field in ('dataset_id', 'dataset_version'):
        if not isinstance(dataset.get(field), str) or not dataset[field].strip():
            errors.append(f'dataset: {field} must be a non-empty string')
    if dataset.get('dataset_version') and not dataset_path.stem.endswith(
            f"-v{dataset['dataset_version']}"):
        errors.append('dataset: filename does not preserve dataset_version')

    cases = dataset.get('cases')
    if not isinstance(cases, list) or not cases:
        errors.append('dataset: cases must be a non-empty list')
        cases = []
    if cases and not 30 <= len(cases) <= 50:
        errors.append(f'dataset: expected 30-50 cases, found {len(cases)}')
    case_ids = set()
    counts = Counter()
    covered_sellers = set()
    skipped = 0

    for position, case in enumerate(cases, 1):
        label = f'case {position}'
        if not isinstance(case, dict):
            errors.append(f'{label}: must be an object')
            continue
        case_id = case.get('case_id')
        label = case_id if isinstance(case_id, str) and case_id else label
        if not isinstance(case_id, str) or not case_id.strip() or case_id in case_ids:
            errors.append(f'{label}: invalid or duplicate case_id')
        else:
            case_ids.add(case_id)
        if case.get('skip') or case.get('status') == 'skipped':
            skipped += 1
            errors.append(f'{label}: skipped evaluation cases are not allowed')
        category = case.get('category')
        if category not in CATEGORIES:
            errors.append(f'{label}: invalid category {category!r}')
        else:
            counts[category] += 1
        seller_id = case.get('seller_id')
        if seller_id not in seller_names:
            errors.append(f'{label}: unknown seller_id {seller_id!r}')
        else:
            covered_sellers.add(seller_id)
        if not isinstance(case.get('query'), str) or not case['query'].strip():
            errors.append(f'{label}: query must be non-empty')
        if not isinstance(case.get('answerable'), bool):
            errors.append(f'{label}: answerable must be boolean')

        source_ids = case.get('expected_sources')
        identities = case.get('expected_source_identity')
        if not isinstance(source_ids, list) or any(not isinstance(x, str) or not x for x in source_ids):
            errors.append(f'{label}: expected_sources must be a list of non-empty strings')
            source_ids = []
        if len(source_ids) != len(set(source_ids)):
            errors.append(f'{label}: expected_sources must be unique')
        if not isinstance(identities, list):
            errors.append(f'{label}: expected_source_identity must be a list')
            identities = []
        cited_ids = []
        evidence = []
        for source in identities:
            if not isinstance(source, dict):
                errors.append(f'{label}: source identity must be an object')
                continue
            identity = (source.get('seller_id'), source.get('document_id'), source.get('version'))
            if identity[0] != seller_id:
                errors.append(f'{label}: source identity crosses seller boundary {identity!r}')
            match = documents.get(identity)
            if match is None:
                errors.append(f'{label}: source identity not found in corpus {identity!r}')
                continue
            document, parsed_sections = match
            if source.get('document_name') != document.get('document_name'):
                errors.append(f'{label}: document_name does not match corpus for {identity!r}')
            section = source.get('section')
            if section not in parsed_sections:
                errors.append(f'{label}: section {section!r} not found for {identity!r}')
            else:
                evidence.append(parsed_sections[section])
            cited_ids.append(identity[1])
        if list(dict.fromkeys(cited_ids)) != source_ids:
            errors.append(f'{label}: expected_sources do not match source identities')

        points = case.get('expected_answer_points')
        if case.get('answerable') is True:
            if not isinstance(points, list) or not points or any(
                    not isinstance(point, str) or not point.strip() for point in points):
                errors.append(f'{label}: answerable case needs expected_answer_points')
            else:
                evidence_words = words(' '.join(evidence))
                for point in points:
                    point_words = words(point)
                    overlap = len(point_words & evidence_words) / len(point_words) if point_words else 0
                    if overlap < 0.5:
                        errors.append(f'{label}: answer point is not supported by cited sections: {point!r}')
        elif points:
            errors.append(f'{label}: unanswerable case must not have expected_answer_points')
        if case.get('answerable') is False and (
                not isinstance(case.get('notes'), str) or not case['notes'].strip()):
            errors.append(f'{label}: unanswerable case needs explanatory notes')

    declared = dataset.get('distribution')
    actual = dict(counts)
    expected = {name: round(len(cases) * ratio) for name, ratio in CATEGORIES.items()}
    if declared != actual:
        errors.append(f'dataset: declared distribution {declared!r} does not match actual {actual!r}')
    if cases and actual != expected:
        errors.append(f'dataset: distribution {actual!r} does not match spec target {expected!r}')
    if cases and covered_sellers != set(seller_names):
        errors.append('dataset: every corpus seller must have at least one evaluation case')
    if cases and skipped == len(cases):
        errors.append('dataset: all cases are skipped')

    return {
        'status': 'passed' if not errors else 'failed',
        'corpus_id': corpus.get('corpus_id'),
        'corpus_version': corpus.get('corpus_version'),
        'dataset_id': dataset.get('dataset_id'),
        'dataset_version': dataset.get('dataset_version'),
        'collected': len(cases),
        'executed': len(cases) - skipped,
        'skipped': skipped,
        'failed_checks': len(errors),
        'distribution': actual,
        'seller_count': len(covered_sellers),
        'document_count': len(documents),
        'errors': errors,
    }


def main():
    report = validate()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
