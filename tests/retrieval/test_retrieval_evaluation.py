"""Checks for complete, reproducible dense-retrieval evaluation."""
import copy
import importlib.util
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('retrieval_evaluation', REPO / 'scripts/evaluate_retrieval.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class RetrievalEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluation.evaluate(REPO, measured_at='test-time')

    def test_complete_fixed_dataset_records_primary_metrics(self):
        report = self.report
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['counts']['collected'], 40)
        self.assertEqual(report['counts']['executed'], 40)
        self.assertEqual(report['counts']['skipped'], 0)
        self.assertEqual(report['counts']['failed'], 0)
        self.assertEqual(report['metrics']['graded_case_count'], 39)
        self.assertEqual(report['metrics']['ungraded_case_count'], 1)
        self.assertGreaterEqual(report['metrics']['recall_at_5'], 0)
        self.assertLessEqual(report['metrics']['recall_at_5'], 1)
        self.assertGreaterEqual(report['metrics']['mrr_at_10'], 0)
        self.assertLessEqual(report['metrics']['mrr_at_10'], 1)

    def test_all_retrieved_evidence_keeps_the_requested_seller(self):
        self.assertEqual(self.report['metrics']['seller_leakage_count'], 0)
        for case in self.report['cases']:
            self.assertTrue(all(item['seller_id'] == case['seller_id']
                                for item in case['retrieved_evidence']))

    def test_pinned_baseline_matches_the_current_deterministic_results(self):
        baseline = evaluation._read_json(REPO / evaluation.BASELINE)
        self.assertTrue(evaluation.matches_baseline(self.report, baseline))
        changed = copy.deepcopy(baseline)
        changed['metrics']['recall_at_5'] = -1
        self.assertFalse(evaluation.matches_baseline(self.report, changed))

    def test_grading_uses_exact_source_identity_and_fractional_recall(self):
        case = {'seller_id': 'seller-a', 'expected_source_identity': [
            {'seller_id': 'seller-a', 'document_id': 'one', 'version': '1', 'section': 'A'},
            {'seller_id': 'seller-a', 'document_id': 'two', 'version': '1', 'section': 'B'},
        ]}
        retrieved = [
            {'seller_id': 'seller-a', 'document_id': 'other', 'version': '1', 'section': 'A'},
            {'seller_id': 'seller-a', 'document_id': 'two', 'version': '1', 'section': 'B'},
        ]
        recall, reciprocal_rank, matched, leakage = evaluation._grade(case, retrieved)
        self.assertEqual(recall, 0.5)
        self.assertEqual(reciprocal_rank, 0.5)
        self.assertEqual(len(matched), 1)
        self.assertEqual(leakage, [])


if __name__ == '__main__':
    unittest.main()
