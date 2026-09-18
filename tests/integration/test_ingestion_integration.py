"""Integration checks for seller-scoped ingestion and chunking."""
import importlib.util
import json
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
chunking_spec = importlib.util.spec_from_file_location('chunking', REPO / 'src/chunking.py')
chunking = importlib.util.module_from_spec(chunking_spec)
chunking_spec.loader.exec_module(chunking)
indexing_spec = importlib.util.spec_from_file_location('indexing', REPO / 'src/indexing.py')
indexing = importlib.util.module_from_spec(indexing_spec)
indexing_spec.loader.exec_module(indexing)
generation_spec = importlib.util.spec_from_file_location('generation', REPO / 'src/generation.py')
generation = importlib.util.module_from_spec(generation_spec)
generation_spec.loader.exec_module(generation)


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

    def test_ingested_sections_become_positioned_chunks(self):
        document = next(doc for doc in ingestion.ingest_seller_corpus('seller-aurora', root=REPO)
                        if doc['document_id'] == 'return_policy')
        for strategy in ('fixed', 'recursive'):
            with self.subTest(strategy=strategy):
                chunks = chunking.chunk_document(
                    document, strategy=strategy, chunk_size=180, overlap=20)
                self.assertGreater(len(chunks), 1)
                self.assertEqual([item['chunk_position'] for item in chunks], list(range(len(chunks))))
                self.assertIn('Section 2', {item['section'] for item in chunks})
                for item in chunks:
                    self.assertEqual(item['seller_id'], 'seller-aurora')
                    self.assertEqual(item['document_id'], 'return_policy')
                    self.assertEqual(item['version'], '1')
                    self.assertEqual(item['text'], document['text'][item['start']:item['end']])

    def test_ingested_corpus_chunks_are_embedded_and_persisted_with_metadata(self):
        documents = ingestion.ingest_seller_corpus('seller-aurora', root=REPO)
        chunks = [chunk for document in documents
                  for chunk in chunking.chunk_document(document, chunk_size=180, overlap=20)]
        connection = indexing.open_index()
        chunk_ids = indexing.index_chunks(connection, 'seller-aurora', chunks)
        stored = indexing.list_indexed_chunks(connection, 'seller-aurora')
        self.assertEqual(len(chunk_ids), len(chunks))
        self.assertEqual(len(stored), len(chunks))
        self.assertTrue(all(item['seller_id'] == 'seller-aurora' for item in stored))
        self.assertTrue(all(item['embedding_model'] == indexing.EMBEDDING_MODEL for item in stored))
        return_chunk = next(item for item in stored
                            if item['document_id'] == 'return_policy' and item['section'] == 'Section 2')
        self.assertEqual(return_chunk['document_name'], 'Return Policy')
        self.assertEqual(return_chunk['version'], '1')
        self.assertEqual(return_chunk['text'], documents[0]['text'][return_chunk['start']:return_chunk['end']])

    def test_corpus_pipeline_retrieves_dense_top_k_evidence(self):
        documents = ingestion.ingest_seller_corpus('seller-aurora', root=REPO)
        chunks = [chunk for document in documents
                  for chunk in chunking.chunk_document(document, chunk_size=180, overlap=20)]
        connection = indexing.open_index()
        indexing.index_chunks(connection, 'seller-aurora', chunks)
        results = indexing.retrieve_chunks(
            connection, 'seller-aurora',
            'Products may be returned within 14 days of delivery.', top_k=5)
        self.assertEqual(len(results), 5)
        self.assertEqual(results[0]['document_id'], 'return_policy')
        self.assertEqual(results[0]['section'], 'Section 2')
        self.assertTrue(all(item['seller_id'] == 'seller-aurora' for item in results))

    def test_retrieved_evidence_drives_the_generation_request(self):
        documents = ingestion.ingest_seller_corpus('seller-aurora', root=REPO)
        chunks = [chunk for document in documents
                  for chunk in chunking.chunk_document(document, chunk_size=180, overlap=20)]
        connection = indexing.open_index()
        indexing.index_chunks(connection, 'seller-aurora', chunks)
        evidence = indexing.retrieve_chunks(
            connection, 'seller-aurora',
            'Products may be returned within 14 days of delivery.', top_k=5)
        captured = {}

        def transport(_url, payload, _timeout):
            captured.update(payload)
            return {'message': {'content': '{"answer":"Unused products may be returned '
                                            'within 14 days of delivery.",'
                                            '"evidence_ids":["E1"]}'}}

        result = generation.generate_answer(
            'seller-aurora', 'Can I return an unused product after seven days?', evidence,
            transport=transport)
        supplied = json.loads(captured['messages'][1]['content'])['evidence']
        self.assertIn('14 days', supplied[0]['text'])
        self.assertIn('14 days', result['answer'])
        self.assertEqual(result['evidence_ids'], ['E1'])
        self.assertEqual(result['citations'], [{
            'evidence_id': 'E1', 'document_name': 'Return Policy', 'section': 'Section 2'}])


if __name__ == '__main__':
    unittest.main()
