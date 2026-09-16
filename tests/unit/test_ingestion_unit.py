"""Unit checks for seller-scoped parsing. No chunking or retrieval."""
import importlib.util
from pathlib import Path
import unittest

from pdf_fixture import make_pdf

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ingestion', REPO / 'src/ingestion.py')
ingestion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingestion)


class IngestionUnitTests(unittest.TestCase):
    def parse(self, **kwargs):
        return ingestion.ingest_document(**kwargs)

    def test_markdown_txt_and_direct_text_preserve_metadata_and_sections(self):
        markdown = self.parse(
            seller_id='seller-aurora', document_id='return_policy', source_format='md',
            document_name='Return Policy', policy_type='return', version='1',
            created_at='2026-01-15', updated_at='2026-01-15', section='Section 2',
            text='# Return Policy\n\n## Section 2 — Return period\n\nReturned within 14 days.\n')
        self.assertEqual(markdown['seller_id'], 'seller-aurora')
        self.assertEqual(markdown['source_format'], 'markdown')
        self.assertEqual(markdown['document_name'], 'Return Policy')
        self.assertEqual(markdown['policy_type'], 'return')
        self.assertEqual(markdown['version'], '1')
        self.assertEqual(markdown['section'], 'Section 2')
        self.assertEqual(markdown['sections'][0]['section'], 'Section 2')
        self.assertIn('14 days', markdown['sections'][0]['text'])
        self.assertEqual(markdown['pages'], [])

        plain = self.parse(seller_id='seller-aurora', document_id='note',
                           source_format='text', text='Direct policy text.')
        self.assertEqual(plain['text'], 'Direct policy text.')
        self.assertEqual(plain['source_format'], 'text')

        txt = self.parse(seller_id='seller-beacon', document_id='shipping_policy',
                         source_format='txt', content=b'Shipping takes 3 days.\n')
        self.assertEqual(txt['seller_id'], 'seller-beacon')
        self.assertEqual(txt['text'], 'Shipping takes 3 days.')

    def test_pdf_extracts_pages_including_flate_and_show_operators(self):
        parsed = self.parse(
            seller_id='seller-aurora', document_id='warranty_policy', source_format='pdf',
            document_name='Warranty Policy', content=make_pdf(
                ['Manufacturing defects are covered for 12 months.', 'Page two keeps seller scope.'],
                compress=True))
        self.assertEqual([page['page'] for page in parsed['pages']], [1, 2])
        self.assertIn('12 months', parsed['pages'][0]['text'])
        self.assertIn('seller scope', parsed['pages'][1]['text'])
        self.assertIn('12 months', parsed['text'])

        custom = (
            b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
            b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
            b'3 0 obj\n<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>\nendobj\n'
            b'4 0 obj\n<< /Length 48 >>\nstream\n'
            b'BT [(Hel\\)lo) <20576F726C64>] TJ (\\n) Tj ET\n'
            b'endstream\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n'
        )
        shown = self.parse(seller_id='seller-aurora', document_id='faq',
                           source_format='pdf', content=custom)
        self.assertIn('Hel)lo', shown['text'])
        self.assertIn(' World', shown['text'])

    def test_rejects_missing_seller_empty_text_and_unsupported_format(self):
        with self.assertRaises(ingestion.IngestionError):
            self.parse(seller_id=' ', document_id='return_policy', source_format='text',
                       text='policy')
        with self.assertRaises(ingestion.IngestionError):
            self.parse(seller_id='seller-aurora', document_id='return_policy',
                       source_format='text', text='   \n')
        with self.assertRaises(ingestion.IngestionError):
            self.parse(seller_id='seller-aurora', document_id='return_policy',
                       source_format='docx', text='policy')
        with self.assertRaises(ingestion.IngestionError):
            self.parse(seller_id='seller-aurora', document_id='return_policy',
                       source_format='pdf', text='not bytes')
        with self.assertRaises(ingestion.IngestionError):
            self.parse(seller_id='seller-aurora', document_id='return_policy',
                       source_format='text', text='a', content=b'b')

    def test_rejects_cross_seller_or_unsafe_paths(self):
        with self.assertRaises(ingestion.IngestionError):
            self.parse(seller_id='seller-aurora', document_id='return_policy',
                       source_format='markdown', path='seller-beacon/return_policy.md')
        with self.assertRaises(ingestion.IngestionError):
            self.parse(seller_id='seller-aurora', document_id='return_policy',
                       source_format='markdown', path='../secrets.md')
        with self.assertRaises(ingestion.IngestionError):
            self.parse(seller_id='seller-aurora', document_id='return_policy',
                       source_format='markdown', path='/tmp/return_policy.md')


if __name__ == '__main__':
    unittest.main()
