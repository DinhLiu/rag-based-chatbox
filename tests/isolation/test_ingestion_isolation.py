"""Isolation checks: seller_id scopes parsing, corpus reads, and chunks."""
import importlib.util
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ingestion', REPO / 'src/ingestion.py')
ingestion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingestion)
chunking_spec = importlib.util.spec_from_file_location('chunking', REPO / 'src/chunking.py')
chunking = importlib.util.module_from_spec(chunking_spec)
chunking_spec.loader.exec_module(chunking)
indexing_spec = importlib.util.spec_from_file_location('indexing', REPO / 'src/indexing.py')
indexing = importlib.util.module_from_spec(indexing_spec)
indexing_spec.loader.exec_module(indexing)


class IngestionIsolationTests(unittest.TestCase):
    def test_overlapping_document_ids_remain_seller_distinct(self):
        aurora = ingestion.ingest_seller_corpus('seller-aurora', root=REPO)
        beacon = ingestion.ingest_seller_corpus('seller-beacon', root=REPO)
        aurora_ids = {doc['document_id'] for doc in aurora}
        beacon_ids = {doc['document_id'] for doc in beacon}
        self.assertTrue({'return_policy', 'warranty_policy', 'shipping_policy'} <= aurora_ids)
        self.assertEqual(beacon_ids, {'return_policy', 'warranty_policy', 'shipping_policy'})
        by_seller = {}
        for doc in aurora + beacon:
            by_seller.setdefault(doc['seller_id'], {})[doc['document_id']] = doc['text']
        self.assertIn('14 days', by_seller['seller-aurora']['return_policy'])
        self.assertIn('7 days', by_seller['seller-beacon']['return_policy'])
        self.assertNotIn('restocking fee', by_seller['seller-aurora']['return_policy'])
        self.assertIn('15% restocking fee', by_seller['seller-beacon']['return_policy'])
        self.assertTrue(all(doc['seller_id'] == 'seller-aurora' for doc in aurora))
        self.assertTrue(all(doc['seller_id'] == 'seller-beacon' for doc in beacon))

    def test_seller_load_cannot_return_another_sellers_documents(self):
        aurora = ingestion.ingest_seller_corpus('seller-aurora', root=REPO)
        leaked = [doc for doc in aurora if 'Beacon Outdoor Supply' in doc['text']
                  or doc['source_path'].startswith('seller-beacon/')]
        self.assertEqual(leaked, [])
        with self.assertRaises(ingestion.IngestionError):
            ingestion.ingest_document(
                'seller-aurora', 'return_policy', source_format='markdown',
                path='seller-beacon/return_policy.md', root=REPO / 'data/raw')

    def test_direct_text_cannot_omit_or_swap_seller_identity(self):
        with self.assertRaises(ingestion.IngestionError):
            ingestion.ingest_document('', 'return_policy', source_format='text',
                                      text='Returns within 14 days.')
        parsed = ingestion.ingest_document(
            'seller-aurora', 'return_policy', source_format='text',
            text='Beacon-like wording must still belong to Aurora.')
        self.assertEqual(parsed['seller_id'], 'seller-aurora')
        self.assertNotEqual(parsed['seller_id'], 'seller-beacon')

    def test_overlapping_document_ids_keep_seller_identity_in_every_chunk(self):
        by_seller = {}
        for seller_id in ('seller-aurora', 'seller-beacon'):
            document = next(doc for doc in ingestion.ingest_seller_corpus(seller_id, root=REPO)
                            if doc['document_id'] == 'return_policy')
            by_seller[seller_id] = chunking.chunk_document(document, chunk_size=120, overlap=10)
        self.assertTrue(all(item['seller_id'] == 'seller-aurora'
                            for item in by_seller['seller-aurora']))
        self.assertTrue(all(item['seller_id'] == 'seller-beacon'
                            for item in by_seller['seller-beacon']))
        self.assertFalse(any('15% restocking fee' in item['text']
                             for item in by_seller['seller-aurora']))
        self.assertTrue(any('15% restocking fee' in item['text']
                            for item in by_seller['seller-beacon']))

    def test_shared_index_reads_only_the_selected_seller(self):
        connection = indexing.open_index()
        chunks = {}
        for seller_id in ('seller-aurora', 'seller-beacon'):
            document = next(doc for doc in ingestion.ingest_seller_corpus(seller_id, root=REPO)
                            if doc['document_id'] == 'return_policy')
            chunks[seller_id] = chunking.chunk_document(document, chunk_size=120, overlap=10)
            indexing.index_chunks(connection, seller_id, chunks[seller_id])
        aurora = indexing.list_indexed_chunks(connection, 'seller-aurora')
        beacon = indexing.list_indexed_chunks(connection, 'seller-beacon')
        self.assertEqual(len(aurora), len(chunks['seller-aurora']))
        self.assertEqual(len(beacon), len(chunks['seller-beacon']))
        self.assertTrue(all(item['seller_id'] == 'seller-aurora' for item in aurora))
        self.assertTrue(all(item['seller_id'] == 'seller-beacon' for item in beacon))
        self.assertFalse(any('15% restocking fee' in item['text'] for item in aurora))
        self.assertTrue(any('15% restocking fee' in item['text'] for item in beacon))

    def test_index_rejects_a_mixed_seller_batch_without_partial_writes(self):
        connection = indexing.open_index()
        aurora = {'seller_id': 'seller-aurora', 'document_id': 'return_policy',
                  'chunk_position': 0, 'text': 'Returns in 14 days.'}
        beacon = dict(aurora, seller_id='seller-beacon', text='Returns in 7 days.')
        with self.assertRaises(indexing.IndexingError):
            indexing.index_chunks(connection, 'seller-aurora', [aurora, beacon])
        self.assertEqual(indexing.list_indexed_chunks(connection, 'seller-aurora'), [])
        self.assertEqual(indexing.list_indexed_chunks(connection, 'seller-beacon'), [])


if __name__ == '__main__':
    unittest.main()
