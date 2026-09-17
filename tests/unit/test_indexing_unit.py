"""Unit checks for deterministic embedding and chunk storage."""
import importlib.util
import math
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('indexing', REPO / 'src/indexing.py')
indexing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(indexing)


class IndexingUnitTests(unittest.TestCase):
    def chunk(self, **changes):
        chunk = {
            'seller_id': 'seller-aurora', 'document_id': 'returns',
            'document_name': 'Returns', 'version': '1', 'section': 'Eligibility',
            'source_path': 'seller-aurora/returns.md', 'chunk_position': 0,
            'start': 0, 'end': 22, 'text': 'Returns within 14 days.',
        }
        chunk.update(changes)
        return chunk

    def test_embedding_is_reproducible_normalized_and_configurable(self):
        first = indexing.embed_text('Returns within 14 days.', dimensions=32)
        second = indexing.embed_text('Returns within 14 days.', dimensions=32)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 32)
        self.assertAlmostEqual(math.sqrt(sum(value * value for value in first)), 1.0)
        self.assertNotEqual(first, indexing.embed_text('Warranty covers defects.', dimensions=32))

    def test_index_preserves_text_metadata_and_embedding_identity(self):
        connection = indexing.open_index()
        ids = indexing.index_chunks(connection, 'seller-aurora', [self.chunk()], dimensions=32)
        stored = indexing.list_indexed_chunks(connection, 'seller-aurora')
        self.assertEqual(len(ids), 1)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]['chunk_id'], ids[0])
        self.assertEqual(stored[0]['text'], 'Returns within 14 days.')
        self.assertEqual(stored[0]['section'], 'Eligibility')
        self.assertEqual(stored[0]['source_path'], 'seller-aurora/returns.md')
        self.assertEqual(stored[0]['embedding_model'], indexing.EMBEDDING_MODEL)
        self.assertEqual(len(stored[0]['embedding']), 32)

    def test_rejects_invalid_embedding_and_chunk_batches(self):
        for text, dimensions in [('', 32), ('...', 32), ('policy', 0), ('policy', True)]:
            with self.subTest(text=text, dimensions=dimensions), self.assertRaises(indexing.IndexingError):
                indexing.embed_text(text, dimensions=dimensions)
        connection = indexing.open_index()
        with self.assertRaises(indexing.IndexingError):
            indexing.index_chunks(connection, 'seller-aurora', [])
        with self.assertRaises(indexing.IndexingError):
            indexing.index_chunks(connection, 'seller-aurora', [self.chunk(chunk_position=-1)])


if __name__ == '__main__':
    unittest.main()
