"""Unit checks for the fixed local generation contract."""
import importlib.util
import json
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('generation', REPO / 'src/generation.py')
generation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generation)


class GenerationUnitTests(unittest.TestCase):
    def evidence(self, count=6):
        return [
            {
                'seller_id': 'seller-aurora', 'text': f'Policy condition {position}.',
                'document_name': f'Policy {position}', 'section': f'Section {position}',
            }
            for position in range(1, count + 1)
        ]

    def test_builds_fixed_ollama_request_from_first_five_evidence_chunks(self):
        captured = {}

        def transport(url, payload, timeout):
            captured.update(url=url, payload=payload, timeout=timeout)
            return {'message': {'content': json.dumps({
                'answer': 'The policy applies when condition 1 is met.',
                'evidence_ids': ['E1'],
            })}}

        result = generation.generate_answer(
            'seller-aurora', 'Does the policy apply?', self.evidence(), transport=transport)

        self.assertEqual(result['evidence_ids'], ['E1'])
        self.assertEqual(result['citations'], [{
            'evidence_id': 'E1', 'document_name': 'Policy 1', 'section': 'Section 1'}])
        self.assertEqual(captured['url'], 'http://127.0.0.1:11434/api/chat')
        payload = captured['payload']
        self.assertEqual(payload['model'], 'qwen2.5:7b-instruct-q4_K_M')
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['options'], {
            'temperature': 0, 'num_ctx': 8192, 'num_predict': 384})
        supplied = json.loads(payload['messages'][1]['content'])['evidence']
        self.assertEqual([item['evidence_id'] for item in supplied],
                         ['E1', 'E2', 'E3', 'E4', 'E5'])
        self.assertNotIn('Policy condition 6.', payload['messages'][1]['content'])
        self.assertEqual(payload['format']['properties']['evidence_ids']['items']['enum'],
                         ['E1', 'E2', 'E3', 'E4', 'E5'])

    def test_rejects_missing_or_cross_seller_evidence_before_transport(self):
        def unexpected(*_):
            self.fail('transport must not be called')

        with self.assertRaises(generation.GenerationError):
            generation.generate_answer(
                'seller-aurora', 'Question?', [], transport=unexpected)
        with self.assertRaises(generation.GenerationError):
            generation.generate_answer(
                'seller-aurora', 'Question?',
                [{'seller_id': 'seller-beacon', 'text': 'Different policy.'}],
                transport=unexpected)

    def test_rejects_invalid_or_unknown_model_output(self):
        responses = [
            {'message': {'content': 'not json'}},
            {'message': {'content': json.dumps({'answer': 'Claim', 'evidence_ids': ['E9']})}},
            {'message': {'content': json.dumps({'answer': 'Claim', 'evidence_ids': []})}},
        ]
        for response in responses:
            with self.subTest(response=response), self.assertRaises(generation.GenerationError):
                generation.generate_answer(
                    'seller-aurora', 'Question?', self.evidence(1),
                    transport=lambda *_args, response=response: response)

    def test_resolves_only_trusted_available_citation_metadata(self):
        evidence = self.evidence(2)
        evidence[0]['page'] = 3
        evidence[1].pop('section')
        citations = generation.resolve_citations(
            'seller-aurora', evidence, ['E2', 'E1'])
        self.assertEqual(citations, [
            {'evidence_id': 'E2', 'document_name': 'Policy 2'},
            {'evidence_id': 'E1', 'document_name': 'Policy 1',
             'section': 'Section 1', 'page': 3},
        ])
        with self.assertRaises(generation.GenerationError):
            generation.resolve_citations('seller-aurora', evidence, ['E3'])


if __name__ == '__main__':
    unittest.main()
