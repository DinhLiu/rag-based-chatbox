"""Isolation checks: seller_id scopes every parse and corpus read."""
import importlib.util
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ingestion', REPO / 'src/ingestion.py')
ingestion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingestion)


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


if __name__ == '__main__':
    unittest.main()
