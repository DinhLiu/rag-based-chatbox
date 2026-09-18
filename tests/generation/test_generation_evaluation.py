"""Checks for Phase 3 generation grading and acceptance."""
import importlib.util
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'generation_evaluation', REPO / 'scripts/evaluate_generation.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class GenerationEvaluationTests(unittest.TestCase):
    def metrics(self, **changes):
        value = {
            'case_count': 31, 'faithful_cases': 31, 'relevant_cases': 31,
            'citation_correct_cases': 31, 'available_answer_points': 71,
            'covered_answer_points': 71, 'conditional_completeness': 1.0,
            'unsupported_claim_count': 0,
        }
        value.update(changes)
        return value

    def test_accepted_thresholds_pass_only_without_safety_failures(self):
        calibration_metrics = {
            'agreement': 0.9, 'cohens_kappa': 0.8,
            'unsupported_precision': 0.95, 'unsupported_recall': 0.9,
            'false_unsupported_count': 0,
        }
        calibration = {**calibration_metrics, 'holdout': dict(calibration_metrics)}
        self.assertTrue(evaluation._passes(
            calibration, self.metrics(relevant_cases=30, covered_answer_points=64),
            self.metrics(relevant_cases=27, covered_answer_points=40,
                         conditional_completeness=0.9), [], 0))
        for gold, retrieved, failures, leakage in (
                (self.metrics(faithful_cases=30), self.metrics(), [], 0),
                (self.metrics(), self.metrics(unsupported_claim_count=1), [], 0),
                (self.metrics(), self.metrics(), [{'error': 'failure'}], 0),
                (self.metrics(), self.metrics(), [], 1)):
            with self.subTest(gold=gold, retrieved=retrieved,
                              failures=failures, leakage=leakage):
                self.assertFalse(evaluation._passes(
                    calibration, gold, retrieved, failures, leakage))

    def test_calibration_has_sixty_two_representative_examples_and_holdout(self):
        dataset = evaluation._read_json(REPO / evaluation.DATASET)
        calibration = evaluation._read_json(REPO / evaluation.CALIBRATION)
        cases = {case['case_id']: case for case in dataset['cases'] if case['answerable']}
        evidence = {case_id: [{'seller_id': case['seller_id'], 'text': 'fixture'}]
                    for case_id, case in cases.items()}
        examples = evaluation._human_authored_calibration(cases, evidence, calibration)
        self.assertEqual(len(examples), 62)
        self.assertEqual(sum(example['split'] == 'holdout' for example in examples), 20)
        self.assertEqual(sum(example['kind'] == 'unsupported' for example in examples), 31)
        self.assertEqual({example['case']['case_id'] for example in examples}, set(cases))

    def test_kappa_requires_aligned_non_empty_labels(self):
        agreement, kappa = evaluation._kappa(
            [True, True, False, False], [True, True, False, False])
        self.assertEqual(agreement, 1.0)
        self.assertEqual(kappa, 1.0)
        with self.assertRaises(evaluation.EvaluationError):
            evaluation._kappa([], [])

    def test_view_metrics_do_not_double_count_repeated_point_ids(self):
        results = [{'judgment': {
            'faithful': True, 'relevant': True, 'citation_correct': True,
            'available_answer_point_indices': [0],
            'covered_answer_point_indices': [0], 'unsupported_claims': [],
        }}]
        self.assertEqual(evaluation._view_metrics(results)['covered_answer_points'], 1)

    def test_atomic_judge_prompts_separate_support_from_coverage(self):
        source = (REPO / 'scripts/evaluate_generation.py').read_text()
        self.assertIn('Evaluate only sentence support and answer relevance', source)
        self.assertIn('Do not penalize omitted facts', source)
        self.assertIn('Evaluate only answer-point availability and coverage', source)
        self.assertIn('Copy each example_index exactly', source)
        self.assertIn('only point_index values listed in that same example', source)

    def test_answer_sentences_are_bounded_to_generated_text(self):
        answer = 'First supported claim. Second unsupported claim!'
        self.assertEqual(
            evaluation._answer_sentences(answer),
            ['First supported claim.', 'Second unsupported claim!'],
        )

    def test_judge_batches_require_uniform_shape_and_schema_bounds_indices(self):
        schema = evaluation._judge_schema(('supported_sentence_indices',), 1, [0, 1])
        enum = schema['properties']['results']['items']['properties'][
            'supported_sentence_indices']['items']['enum']
        self.assertEqual(enum, [0, 1])
        case = {'query': 'Question?', 'expected_answer_points': ['point']}
        evidence = [{'text': 'evidence'}]
        with self.assertRaises(evaluation.EvaluationError):
            evaluation._support_judge([
                (case, evidence, {'answer': 'One.', 'evidence_ids': ['E1']}),
                (case, evidence, {'answer': 'One. Two.', 'evidence_ids': ['E1']}),
            ])


if __name__ == '__main__':
    unittest.main()
