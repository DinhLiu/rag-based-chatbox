"""Configurable baseline chunking for seller-scoped ingested documents."""
from __future__ import annotations

import re


class ChunkingError(ValueError):
    pass


def chunk_document(document, *, strategy='recursive', chunk_size=1000, overlap=100,
                   separators=('\n\n', '\n', '. ', ' ')):
    """Split one ingested document while retaining source identity and offsets."""
    if not isinstance(document, dict):
        raise ChunkingError('document must be an object')
    for field in ('seller_id', 'document_id'):
        if not isinstance(document.get(field), str) or not document[field].strip():
            raise ChunkingError(f'{field} is required')
    text = document.get('text')
    if not isinstance(text, str) or not text:
        raise ChunkingError('document text is required')
    if strategy not in {'fixed', 'recursive'}:
        raise ChunkingError(f'unsupported strategy {strategy!r}')
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size < 1:
        raise ChunkingError('chunk_size must be a positive integer')
    if not isinstance(overlap, int) or isinstance(overlap, bool) or not 0 <= overlap < chunk_size:
        raise ChunkingError('overlap must be an integer smaller than chunk_size')
    if (not isinstance(separators, (tuple, list)) or not separators
            or any(not isinstance(item, str) or not item for item in separators)):
        raise ChunkingError('separators must be a non-empty sequence of strings')

    metadata = {key: value for key, value in document.items()
                if key not in {'text', 'sections', 'pages', 'section', 'page'}}
    chunks = []
    for region_start, region_end, section, page in _source_regions(document):
        region = text[region_start:region_end]
        for start, end in _boundaries(region, strategy, chunk_size, overlap, separators):
            chunks.append({
                **metadata,
                'section': section,
                'page': page,
                'chunk_position': len(chunks),
                'start': region_start + start,
                'end': region_start + end,
                'text': region[start:end],
            })
    return chunks


def _source_regions(document):
    text = document['text']
    pages = [page for page in document.get('pages') or []
             if isinstance(page, dict) and page.get('text')]
    if pages:
        regions = []
        cursor = 0
        for page in pages:
            start = text.find(page['text'], cursor)
            if start < 0:
                raise ChunkingError('page text does not match document text')
            end = start + len(page['text'])
            regions.append((start, end, document.get('section'), page.get('page')))
            cursor = end
        return regions

    headings = list(re.finditer(r'(?m)^## (.+)$', text))
    if not headings:
        return [(0, len(text), document.get('section'), None)]
    regions = []
    if headings[0].start():
        regions.append((0, headings[0].start(), document.get('section'), None))
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = heading.group(1).split(' — ', 1)[0].strip()
        regions.append((heading.start(), end, section, None))
    return regions


def _boundaries(text, strategy, chunk_size, overlap, separators):
    cursor = 0
    while cursor < len(text):
        limit = min(cursor + chunk_size, len(text))
        end = limit if strategy == 'fixed' else _recursive_end(text, cursor, limit, separators)
        yield cursor, end
        if end == len(text):
            break
        next_cursor = end - overlap
        cursor = next_cursor if next_cursor > cursor else end


def _recursive_end(text, start, limit, separators):
    if limit == len(text):
        return limit
    window = text[start:limit]
    for separator in separators:
        split = window.rfind(separator)
        if split > 0:
            return start + split + len(separator)
    return limit
