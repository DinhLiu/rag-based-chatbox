"""Evidence-grounded answer generation through the local Ollama API."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL = 'qwen2.5:1.5b-instruct'
DEFAULT_BASE_URL = 'http://127.0.0.1:11434'
PROMPT_VERSION = 'grounded-answer-v1'
OPTIONS = {'temperature': 0, 'num_ctx': 8192, 'num_predict': 384}


class GenerationError(ValueError):
    pass


class GenerationUnavailableError(RuntimeError):
    pass


def generate_answer(seller_id, query, evidence, *, base_url=DEFAULT_BASE_URL,
                    transport=None, timeout=120):
    """Return an answer and supporting evidence IDs from at most five chunks."""
    seller_id = _required(seller_id, 'seller_id')
    query = _required(query, 'query')
    if not isinstance(evidence, (list, tuple)) or not evidence:
        raise GenerationError('evidence must be a non-empty sequence')
    selected = evidence[:5]
    if any(not isinstance(item, dict) or item.get('seller_id') != seller_id
           for item in selected):
        raise GenerationError('every evidence chunk must match seller_id')
    labeled = []
    for position, item in enumerate(selected, 1):
        text = _required(item.get('text'), 'evidence text')
        labeled.append({'evidence_id': f'E{position}', 'text': text})
    evidence_ids = [item['evidence_id'] for item in labeled]
    schema = {
        'type': 'object',
        'properties': {
            'answer': {'type': 'string'},
            'evidence_ids': {
                'type': 'array', 'items': {'type': 'string', 'enum': evidence_ids},
                'uniqueItems': True, 'minItems': 1,
            },
        },
        'required': ['answer', 'evidence_ids'],
        'additionalProperties': False,
    }
    payload = {
        'model': MODEL,
        'messages': [
            {
                'role': 'system',
                'content': (
                    'Answer the customer using only the supplied policy evidence. '
                    'Preserve every relevant condition, be concise, and make no unsupported '
                    'policy claim. Return only the requested JSON object. Cite support only by '
                    'its evidence_id.'
                ),
            },
            {
                'role': 'user',
                'content': json.dumps(
                    {'question': query, 'evidence': labeled},
                    ensure_ascii=False, separators=(',', ':'),
                ),
            },
        ],
        'stream': False,
        'format': schema,
        'options': dict(OPTIONS),
    }
    response = (transport or _post_json)(
        base_url.rstrip('/') + '/api/chat', payload, timeout)
    try:
        result = json.loads(response['message']['content'])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise GenerationError('Ollama returned an invalid structured response') from exc
    if not isinstance(result, dict) or set(result) != {'answer', 'evidence_ids'}:
        raise GenerationError('generated response must contain only answer and evidence_ids')
    answer = _required(result.get('answer'), 'answer')
    cited = result.get('evidence_ids')
    if (not isinstance(cited, list) or not cited or
            any(not isinstance(item, str) or item not in evidence_ids for item in cited) or
            len(cited) != len(set(cited))):
        raise GenerationError('generated evidence_ids must be unique supplied evidence IDs')
    return {
        'answer': answer,
        'evidence_ids': cited,
        'citations': resolve_citations(seller_id, selected, cited),
    }


def resolve_citations(seller_id, evidence, evidence_ids):
    """Resolve model-selected IDs to trusted retrieval metadata."""
    seller_id = _required(seller_id, 'seller_id')
    if not isinstance(evidence, (list, tuple)) or not evidence:
        raise GenerationError('evidence must be a non-empty sequence')
    selected = evidence[:5]
    if any(not isinstance(item, dict) or item.get('seller_id') != seller_id
           for item in selected):
        raise GenerationError('every evidence chunk must match seller_id')
    if (not isinstance(evidence_ids, list) or not evidence_ids or
            any(not isinstance(item, str) for item in evidence_ids) or
            len(evidence_ids) != len(set(evidence_ids))):
        raise GenerationError('evidence_ids must be a non-empty unique string list')
    by_id = {f'E{position}': item for position, item in enumerate(selected, 1)}
    if any(evidence_id not in by_id for evidence_id in evidence_ids):
        raise GenerationError('citation references unknown evidence')
    citations = []
    for evidence_id in evidence_ids:
        item = by_id[evidence_id]
        citation = {
            'evidence_id': evidence_id,
            'document_name': _required(item.get('document_name'), 'document_name'),
        }
        for field in ('section', 'page'):
            if item.get(field) is not None:
                citation[field] = item[field]
        citations.append(citation)
    return citations


def _post_json(url, payload, timeout):
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise GenerationUnavailableError(f'Ollama request failed: {exc}') from exc


def _required(value, name):
    if not isinstance(value, str) or not value.strip():
        raise GenerationError(f'{name} is required')
    return value.strip()
