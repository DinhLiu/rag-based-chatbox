"""Integration checks for seller-scoped corpus and file ingestion."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'unit'))
from pdf_fixture import make_pdf

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ingestion', REPO / 'src/ingestion.py')
ingestion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingestion)


class IngestionIntegrationTests(unittest.TestCase):
    def test_ingests_versioned_markdown_corpus_for_each_seller(self):
        aurora = ingestion.ingest_seller_corpus('seller-aurora', root=REPO)
        beacon = ingestion.ingest_seller_corpus('seller-beacon', root=REPO)
        self.assertEqual(len(aurora), 9)
        self.assertEqual(len(beacon), 3)
        self.assertTrue(all(doc['seller_id'] == 'seller-aurora' for doc in aurora))
        self.assertTrue(all(doc['seller_id'] == 'seller-beacon' for doc in beacon))
        aurora_return = next(doc for doc in aurora if doc['document_id'] == 'return_policy')
        beacon_return = next(doc for doc in beacon if doc['document_id'] == 'return_policy')
        self.assertEqual(aurora_return['document_name'], 'Return Policy')
        self.assertEqual(aurora_return['policy_type'], 'return')
        self.assertEqual(aurora_return['version'], '1')
        self.assertEqual(aurora_return['source_path'], 'seller-aurora/return_policy.md')
        self.assertIn('Section 2', [item['section'] for item in aurora_return['sections']])
        self.assertIn('14 days', aurora_return['text'])
        self.assertIn('7 days', beacon_return['text'])
        self.assertNotIn('7 days', aurora_return['text'])

    def test_ingests_txt_and_pdf_files_from_seller_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            txt_path = root / 'seller-aurora' / 'hours.txt'
            pdf_path = root / 'seller-aurora' / 'notice.pdf'
            txt_path.parent.mkdir()
            txt_path.write_text('Support hours are 9 to 17.\n', encoding='utf-8')
            pdf_path.write_bytes(make_pdf(['Package protection is optional.']))
            txt = ingestion.ingest_document(
                'seller-aurora', 'hours', source_format='txt', path=txt_path.relative_to(root),
                root=root, document_name='Support Hours')
            pdf = ingestion.ingest_document(
                'seller-aurora', 'notice', source_format='pdf', path=pdf_path.relative_to(root),
                root=root, version='1')
            self.assertEqual(txt['text'], 'Support hours are 9 to 17.')
            self.assertEqual(txt['document_name'], 'Support Hours')
            self.assertIn('Package protection is optional.', pdf['text'])
            self.assertEqual(pdf['pages'][0]['page'], 1)

    def test_unknown_seller_and_missing_file_fail(self):
        with self.assertRaises(ingestion.IngestionError):
            ingestion.ingest_seller_corpus('seller-missing', root=REPO)
        with self.assertRaises(ingestion.IngestionError):
            ingestion.ingest_document(
                'seller-aurora', 'missing', source_format='markdown',
                path='seller-aurora/missing.md', root=REPO / 'data/raw')


if __name__ == '__main__':
    unittest.main()
