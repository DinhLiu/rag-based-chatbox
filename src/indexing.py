"""Deterministic embeddings and seller-scoped SQLite chunk storage."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3

EMBEDDING_MODEL = 'feature-hashing-v1'
DEFAULT_DIMENSIONS = 256
_TOKENS = re.compile(r"\w+", re.UNICODE)


class IndexingError(ValueError):
    pass


def embed_text(text, *, dimensions=DEFAULT_DIMENSIONS):
    """Return a reproducible, unit-normalized feature-hashing vector."""
    if not isinstance(text, str) or not text.strip():
        raise IndexingError('text is required')
    if not isinstance(dimensions, int) or isinstance(dimensions, bool) or dimensions < 1:
        raise IndexingError('dimensions must be a positive integer')
    tokens = _TOKENS.findall(text.casefold())
    if not tokens:
        raise IndexingError('text must contain a word')
    # ponytail: offline token hashing is the baseline; replace only if evaluation misses targets.
    vector = [0.0] * dimensions
    for token in tokens:
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], 'big') % dimensions
        vector[index] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector]


def open_index(path=':memory:'):
    connection = sqlite3.connect(path)
    connection.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            seller_id TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            version TEXT,
            chunk_position INTEGER NOT NULL,
            text TEXT NOT NULL,
            metadata TEXT NOT NULL,
            embedding TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_dimensions INTEGER NOT NULL,
            PRIMARY KEY (seller_id, chunk_id)
        )
    ''')
    connection.execute('''
        CREATE INDEX IF NOT EXISTS chunks_by_seller_document
        ON chunks (seller_id, document_id, version)
    ''')
    connection.commit()
    return connection


def index_chunks(connection, seller_id, chunks, *, dimensions=DEFAULT_DIMENSIONS):
    """Embed and store a non-empty batch belonging to exactly one seller."""
    seller_id = _required(seller_id, 'seller_id')
    if not isinstance(chunks, (list, tuple)) or not chunks:
        raise IndexingError('chunks must be a non-empty sequence')
    rows = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise IndexingError('each chunk must be an object')
        if chunk.get('seller_id') != seller_id:
            raise IndexingError('every chunk must match seller_id')
        document_id = _required(chunk.get('document_id'), 'document_id')
        position = chunk.get('chunk_position')
        if not isinstance(position, int) or isinstance(position, bool) or position < 0:
            raise IndexingError('chunk_position must be a non-negative integer')
        text = chunk.get('text')
        vector = embed_text(text, dimensions=dimensions)
        metadata = {key: value for key, value in chunk.items() if key != 'text'}
        try:
            encoded_metadata = json.dumps(metadata, sort_keys=True, separators=(',', ':'))
        except (TypeError, ValueError) as exc:
            raise IndexingError(f'chunk metadata is not JSON serializable: {exc}') from exc
        chunk_id = _chunk_id(chunk)
        rows.append((seller_id, chunk_id, document_id, chunk.get('version'), position, text,
                     encoded_metadata, json.dumps(vector, separators=(',', ':')),
                     EMBEDDING_MODEL, dimensions))
    with connection:
        connection.executemany('''
            INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (seller_id, chunk_id) DO UPDATE SET
                document_id=excluded.document_id,
                version=excluded.version,
                chunk_position=excluded.chunk_position,
                text=excluded.text,
                metadata=excluded.metadata,
                embedding=excluded.embedding,
                embedding_model=excluded.embedding_model,
                embedding_dimensions=excluded.embedding_dimensions
        ''', rows)
    return [row[1] for row in rows]


def list_indexed_chunks(connection, seller_id):
    """Inspect stored chunks for one seller; no unscoped read is exposed."""
    seller_id = _required(seller_id, 'seller_id')
    rows = connection.execute('''
        SELECT chunk_id, text, metadata, embedding, embedding_model, embedding_dimensions
        FROM chunks WHERE seller_id = ? ORDER BY document_id, version, chunk_position, chunk_id
    ''', (seller_id,)).fetchall()
    return [{
        **json.loads(metadata),
        'chunk_id': chunk_id,
        'text': text,
        'embedding': json.loads(embedding),
        'embedding_model': model,
        'embedding_dimensions': dimensions,
    } for chunk_id, text, metadata, embedding, model, dimensions in rows]


def retrieve_chunks(connection, seller_id, query, *, top_k=5):
    """Return the selected seller's top-K chunks by cosine similarity."""
    seller_id = _required(seller_id, 'seller_id')
    query = _required(query, 'query')
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise IndexingError('top_k must be a positive integer')
    candidates = list_indexed_chunks(connection, seller_id)
    if not candidates:
        return []
    configurations = {(item['embedding_model'], item['embedding_dimensions'])
                      for item in candidates}
    if len(configurations) != 1 or next(iter(configurations))[0] != EMBEDDING_MODEL:
        raise IndexingError('seller index must use one supported embedding configuration')
    _, dimensions = next(iter(configurations))
    query_embedding = embed_text(query, dimensions=dimensions)
    ranked = []
    for item in candidates:
        evidence = {key: value for key, value in item.items()
                    if key not in {'embedding', 'embedding_model', 'embedding_dimensions'}}
        evidence['score'] = sum(left * right
                                for left, right in zip(query_embedding, item['embedding']))
        ranked.append(evidence)
    ranked.sort(key=lambda item: (-item['score'], item['chunk_id']))
    return ranked[:top_k]


def _chunk_id(chunk):
    identity = {key: chunk.get(key) for key in
                ('seller_id', 'document_id', 'version', 'chunk_position', 'start', 'end', 'text')}
    payload = json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(payload).hexdigest()


def _required(value, name):
    if not isinstance(value, str) or not value.strip():
        raise IndexingError(f'{name} is required')
    return value.strip()
