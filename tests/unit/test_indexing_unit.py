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

    def test_dense_retrieval_returns_ranked_top_k_evidence(self):
        connection = indexing.open_index()
        chunks = [
            self.chunk(text='Returns and refunds are available.', chunk_position=0),
            self.chunk(text='Warranty covers manufacturing defects.', chunk_position=1),
            self.chunk(text='Shipping takes three business days.', chunk_position=2),
        ]
        indexing.index_chunks(connection, 'seller-aurora', chunks)
        results = indexing.retrieve_chunks(
            connection, 'seller-aurora', 'returns refunds available', top_k=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['chunk_position'], 0)
        self.assertGreaterEqual(results[0]['score'], results[1]['score'])
        self.assertNotIn('embedding', results[0])

    def test_retrieval_validates_inputs_and_allows_an_empty_seller_index(self):
        connection = indexing.open_index()
        self.assertEqual(indexing.retrieve_chunks(
            connection, 'seller-missing', 'return policy'), [])
        for seller_id, query, top_k in [('', 'policy', 1), ('seller', '', 1),
                                         ('seller', 'policy', 0), ('seller', 'policy', True)]:
            with self.subTest(seller_id=seller_id, query=query, top_k=top_k), \
                    self.assertRaises(indexing.IndexingError):
                indexing.retrieve_chunks(connection, seller_id, query, top_k=top_k)


if __name__ == '__main__':
    unittest.main()
