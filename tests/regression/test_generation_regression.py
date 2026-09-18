"""Checks generation regression comparison behavior."""
import copy
import importlib.util
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'generation_evaluation', REPO / 'scripts/evaluate_generation.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class GenerationRegressionTests(unittest.TestCase):
    def report(self):
        view = {
            'case_count': 1, 'faithful_cases': 1, 'relevant_cases': 1,
            'citation_correct_cases': 1, 'available_answer_points': 1,
            'covered_answer_points': 1, 'conditional_completeness': 1.0,
            'unsupported_claim_count': 0,
        }
        return {
            'report_id': 'fixture', 'status': 'passed',
            'metrics': {'gold': copy.deepcopy(view), 'retrieved': copy.deepcopy(view),
                        'seller_leakage_count': 0, 'error_rate': 0.0},
            'calibration': {'agreement': 1.0, 'cohens_kappa': 1.0},
            'cases': [{'case_id': 'case-1', 'view': 'gold',
                       'judgment': {'faithful': True, 'citation_correct': True}}],
        }

    def test_previously_passing_safety_case_cannot_regress(self):
        baseline = self.report()
        current = copy.deepcopy(baseline)
        self.assertTrue(evaluation.compare_to_baseline(current, baseline))
        current = copy.deepcopy(baseline)
        current['cases'][0]['judgment']['faithful'] = False
        self.assertFalse(evaluation.compare_to_baseline(current, baseline))
        self.assertEqual(current['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
