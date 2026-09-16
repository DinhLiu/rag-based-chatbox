"""Seller-scoped document parsing. Does not chunk, embed, index, or retrieve."""
from __future__ import annotations

import json
import re
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = Path('data/raw/corpus.json')
SUPPORTED_FORMATS = {'pdf', 'markdown', 'txt', 'text'}
_FORMAT_ALIASES = {'md': 'markdown'}


class IngestionError(ValueError):
    pass


def ingest_document(
    seller_id,
    document_id,
    *,
    source_format,
    text=None,
    content=None,
    path=None,
    root=None,
    document_name=None,
    policy_type=None,
    version=None,
    created_at=None,
    updated_at=None,
    section=None,
):
    seller_id = _required(seller_id, 'seller_id')
    document_id = _required(document_id, 'document_id')
    source_format = _FORMAT_ALIASES.get(source_format, source_format)
    if source_format not in SUPPORTED_FORMATS:
        raise IngestionError(f'unsupported source_format {source_format!r}')
    source_path = _scoped_path(seller_id, path) if path is not None else None
    provided = [item is not None for item in (text, content, path)]
    if sum(provided) != 1:
        raise IngestionError('provide exactly one of text, content, or path')
    if text is not None:
        raw_text, pages = _from_text(source_format, text)
    elif content is not None:
        if not isinstance(content, (bytes, bytearray)):
            raise IngestionError('content must be bytes')
        raw_text, pages = _from_bytes(source_format, bytes(content))
    else:
        target = (Path(root) if root is not None else ROOT) / source_path
        try:
            data = target.read_bytes()
        except OSError as exc:
            raise IngestionError(f'cannot read {source_path}: {exc}') from exc
        raw_text, pages = _from_bytes(source_format, data)
    raw_text = _clean(raw_text)
    if not raw_text:
        raise IngestionError('document text is empty')
    if section is not None:
        section = _required(section, 'section')
    return {
        'seller_id': seller_id,
        'document_id': document_id,
        'document_name': document_name or _title(raw_text) or document_id,
        'policy_type': policy_type,
        'section': section,
        'version': version,
        'created_at': created_at,
        'updated_at': updated_at,
        'source_format': source_format,
        'source_path': None if source_path is None else str(source_path),
        'text': raw_text,
        'sections': _sections(raw_text),
        'pages': pages,
    }


def ingest_seller_corpus(seller_id, *, root=None):
    seller_id = _required(seller_id, 'seller_id')
    base = Path(root) if root is not None else ROOT
    catalog_path = base / CORPUS
    try:
        catalog = json.loads(catalog_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise IngestionError(f'cannot read corpus catalog: {exc}') from exc
    for seller in catalog.get('sellers') or []:
        if not isinstance(seller, dict) or seller.get('seller_id') != seller_id:
            continue
        documents = seller.get('documents')
        if not isinstance(documents, list) or not documents:
            raise IngestionError(f'{seller_id} has no documents')
        parsed = []
        for document in documents:
            if not isinstance(document, dict):
                raise IngestionError(f'{seller_id} document must be an object')
            parsed.append(ingest_document(
                seller_id,
                document.get('document_id'),
                source_format=document.get('format'),
                path=document.get('path'),
                root=catalog_path.parent,
                document_name=document.get('document_name'),
                policy_type=document.get('policy_type'),
                version=document.get('version'),
                created_at=document.get('created_at'),
                updated_at=document.get('updated_at'),
            ))
        return parsed
    raise IngestionError(f'unknown seller_id {seller_id!r}')


def _required(value, name):
    if not isinstance(value, str) or not value.strip():
        raise IngestionError(f'{name} is required')
    return value.strip()


def _scoped_path(seller_id, path):
    if not isinstance(path, (str, Path)) or isinstance(path, str) and not path.strip():
        raise IngestionError('path must be a seller-scoped relative path')
    relative = Path(path)
    if relative.is_absolute() or '..' in relative.parts:
        raise IngestionError(f'path {relative} is not seller-scoped')
    if len(relative.parts) > 1 and relative.parts[0] != seller_id:
        raise IngestionError(f'path {relative} is not scoped to {seller_id}')
    return relative


def _clean(text):
    text = text.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')
    return '\n'.join(line.rstrip() for line in text.split('\n')).strip()


def _title(text):
    match = re.match(r'^# (.+)$', text, re.M)
    return match.group(1).strip() if match else None


def _sections(text):
    found = []
    for part in re.split(r'(?m)^## ', text)[1:]:
        heading, _, body = part.partition('\n')
        name = heading.split(' — ', 1)[0].strip()
        if name:
            found.append({'section': name, 'text': body.strip()})
    return found


def _from_text(source_format, text):
    if source_format == 'pdf':
        raise IngestionError('pdf requires bytes content or a file path')
    if not isinstance(text, str):
        raise IngestionError('text must be a string')
    return text, []


def _from_bytes(source_format, data):
    if source_format == 'pdf':
        return _pdf_text(data)
    try:
        return data.decode('utf-8'), []
    except UnicodeDecodeError as exc:
        raise IngestionError(f'{source_format} is not valid UTF-8: {exc}') from exc


def _pdf_text(data):
    # ponytail: object-regex extractor for Latin text PDFs; no CMaps/OCR/XObjects.
    if not data.startswith(b'%PDF'):
        raise IngestionError('content is not a PDF')
    objects = {int(match.group(1)): match.group(2)
               for match in re.finditer(rb'(\d+)\s+0\s+obj(.*?)endobj', data, re.S)}
    pages = []
    for number, page_id in enumerate(_pdf_page_ids(objects), 1):
        texts = []
        for content_id in _page_content_ids(_header_text(objects[page_id])):
            payload = _pdf_stream(objects.get(content_id, b''))
            texts.append(_pdf_show_text(payload.decode('latin-1', 'replace')))
        pages.append({'page': number, 'text': _clean('\n'.join(texts))})
    combined = _clean('\n\n'.join(page['text'] for page in pages if page['text']))
    return combined, pages


def _header_text(body):
    return body.partition(b'stream')[0].decode('latin-1', 'replace')


def _refs(text):
    return [int(number) for number in re.findall(r'(\d+)\s+0\s+R', text)]


def _pdf_page_ids(objects):
    ordered = []
    for obj_id, body in objects.items():
        header = _header_text(body)
        if re.search(r'/Type\s*/Pages\b', header) and '/Kids' in header:
            ordered = _page_ids_from_tree(objects, obj_id, set())
            if ordered:
                return ordered
    return [obj_id for obj_id, body in objects.items()
            if re.search(r'/Type\s*/Page\b', _header_text(body))
            and not re.search(r'/Type\s*/Pages\b', _header_text(body))]


def _page_ids_from_tree(objects, node_id, seen):
    if node_id in seen or node_id not in objects:
        return []
    seen.add(node_id)
    header = _header_text(objects[node_id])
    kids = re.search(r'/Kids\s*\[(.*?)\]', header, re.S)
    if kids:
        found = []
        for child in _refs(kids.group(1)):
            found.extend(_page_ids_from_tree(objects, child, seen))
        return found
    if re.search(r'/Type\s*/Page\b', header):
        return [node_id]
    return []


def _page_content_ids(header):
    grouped = re.search(r'/Contents\s*\[(.*?)\]', header, re.S)
    if grouped:
        return _refs(grouped.group(1))
    single = re.search(r'/Contents\s+(\d+)\s+0\s+R', header)
    return [int(single.group(1))] if single else []


def _pdf_stream(obj):
    header, marker, rest = obj.partition(b'stream')
    if not marker:
        return b''
    if rest.startswith(b'\r\n'):
        rest = rest[2:]
    elif rest.startswith(b'\n') or rest.startswith(b'\r'):
        rest = rest[1:]
    payload = rest.partition(b'endstream')[0]
    if payload.endswith(b'\r\n'):
        payload = payload[:-2]
    elif payload.endswith((b'\n', b'\r')):
        payload = payload[:-1]
    if re.search(r'/Filter\s*/FlateDecode', header.decode('latin-1', 'replace')):
        try:
            return zlib.decompress(payload)
        except zlib.error as exc:
            raise IngestionError(f'PDF stream is not valid FlateDecode: {exc}') from exc
    return payload


def _unescape_pdf_literal(body):
    out = []
    index = 0
    named = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f',
             '(': '(', ')': ')', '\\': '\\'}
    while index < len(body):
        char = body[index]
        if char == '\\' and index + 1 < len(body):
            nxt = body[index + 1]
            if nxt in named:
                out.append(named[nxt])
                index += 2
                continue
            if nxt in '01234567':
                octal = nxt
                index += 2
                while index < len(body) and len(octal) < 3 and body[index] in '01234567':
                    octal += body[index]
                    index += 1
                out.append(chr(int(octal, 8)))
                continue
            out.append(nxt)
            index += 2
            continue
        out.append(char)
        index += 1
    return ''.join(out)


def _pdf_show_text(content):
    chunks = []
    for match in re.finditer(r'\((?:\\.|[^\\)])*\)\s*Tj', content):
        literal = match.group(0)
        chunks.append(_unescape_pdf_literal(literal[1:literal.rfind(')')]))
    for match in re.finditer(r'<([0-9A-Fa-f]+)>\s*Tj', content):
        chunks.append(bytes.fromhex(match.group(1)).decode('latin-1'))
    for match in re.finditer(r'\[(.*?)\]\s*TJ', content, re.S):
        for item in re.finditer(r'\((?:\\.|[^\\)])*\)|<([0-9A-Fa-f]+)>', match.group(1)):
            if item.group(0).startswith('('):
                chunks.append(_unescape_pdf_literal(item.group(0)[1:-1]))
            else:
                chunks.append(bytes.fromhex(item.group(1)).decode('latin-1'))
    return '\n'.join(chunk for chunk in chunks if chunk)
