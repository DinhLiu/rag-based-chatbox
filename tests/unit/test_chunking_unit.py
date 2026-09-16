"""Unit checks for configurable baseline chunking."""
import importlib.util
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('chunking', REPO / 'src/chunking.py')
chunking = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chunking)


class ChunkingUnitTests(unittest.TestCase):
    def document(self, text):
        return {
            'seller_id': 'seller-aurora', 'document_id': 'returns',
            'document_name': 'Returns', 'version': '1', 'source_path': 'seller-aurora/returns.md',
            'text': text, 'sections': [], 'pages': [],
        }

    def test_fixed_chunks_preserve_metadata_positions_and_overlap(self):
        document = self.document('abcdefghij')
        chunks = chunking.chunk_document(document, strategy='fixed', chunk_size=4, overlap=1)
        self.assertEqual([item['text'] for item in chunks], ['abcd', 'defg', 'ghij'])
        self.assertEqual([(item['start'], item['end']) for item in chunks], [(0, 4), (3, 7), (6, 10)])
        self.assertEqual([item['chunk_position'] for item in chunks], [0, 1, 2])
        self.assertTrue(all(item['seller_id'] == 'seller-aurora' for item in chunks))
        self.assertTrue(all(item['source_path'] == 'seller-aurora/returns.md' for item in chunks))

    def test_recursive_chunks_use_boundaries_and_keep_sections_separate(self):
        text = '# Policy\n\n## Section 1 — Returns\n\nReturn within fourteen days. Original box required.\n\n## Section 2 — Fees\n\nNo fee applies.'
        document = self.document(text)
        chunks = chunking.chunk_document(document, chunk_size=48, overlap=0)
        self.assertTrue(all(len(item['text']) <= 48 for item in chunks))
        self.assertEqual(chunks[0]['section'], None)
        self.assertIn('Section 1', {item['section'] for item in chunks})
        self.assertIn('Section 2', {item['section'] for item in chunks})
        self.assertFalse(any('Section 1' in item['text'] and 'Section 2' in item['text'] for item in chunks))
        for item in chunks:
            self.assertEqual(item['text'], text[item['start']:item['end']])

        short_boundaries = chunking.chunk_document(
            self.document('a\n\nbbbbbbbbbbbbbbbbbbbb'), chunk_size=10, overlap=5)
        self.assertEqual(short_boundaries[-1]['end'], 23)

    def test_page_chunks_preserve_page_references(self):
        document = self.document('First page.\n\nSecond page.')
        document['pages'] = [
            {'page': 1, 'text': 'First page.'},
            {'page': 2, 'text': 'Second page.'},
        ]
        chunks = chunking.chunk_document(document, chunk_size=8, overlap=0)
        self.assertEqual({item['page'] for item in chunks}, {1, 2})
        self.assertFalse(any('First' in item['text'] and item['page'] == 2 for item in chunks))
        for item in chunks:
            self.assertEqual(item['text'], document['text'][item['start']:item['end']])

    def test_rejects_invalid_document_and_configuration(self):
        cases = [
            ({'document_id': 'returns', 'text': 'policy'}, {}),
            (self.document('policy'), {'strategy': 'semantic'}),
            (self.document('policy'), {'chunk_size': 0}),
            (self.document('policy'), {'chunk_size': 4, 'overlap': 4}),
            (self.document('policy'), {'separators': []}),
        ]
        for document, options in cases:
            with self.subTest(options=options), self.assertRaises(chunking.ChunkingError):
                chunking.chunk_document(document, **options)


if __name__ == '__main__':
    unittest.main()
