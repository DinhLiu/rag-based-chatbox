"""Checks required Phase 3 system observations."""
import importlib.util
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'generation_evaluation', REPO / 'scripts/evaluate_generation.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class GenerationSystemTests(unittest.TestCase):
    def test_runtime_configuration_records_models_prompts_options_and_thresholds(self):
        self.assertEqual(evaluation.MODEL, 'qwen2.5:7b-instruct-q4_K_M')
        self.assertEqual(evaluation.JUDGE_MODEL, 'qwen2.5:7b-instruct-q4_K_M')
        self.assertEqual(evaluation.OPTIONS['temperature'], 0)
        self.assertEqual(evaluation.JUDGE_OPTIONS['temperature'], 0)
        self.assertEqual(evaluation.THRESHOLDS['gold_complete_points'], 64)
        self.assertEqual(evaluation.THRESHOLDS['retrieved_complete_points'], 40)
        self.assertTrue(evaluation.PROMPT_VERSION)
        self.assertTrue(evaluation.JUDGE_PROMPT_VERSION)
        self.assertEqual(evaluation.PROMPT_VERSION, 'grounded-answer-v2')
        self.assertEqual(evaluation.JUDGE_PROMPT_VERSION, 'atomic-generation-judge-v1')
        self.assertEqual(evaluation.THRESHOLDS['unsupported_precision'], 0.95)
        self.assertEqual(evaluation.THRESHOLDS['unsupported_recall'], 0.90)

    def test_source_identity_includes_current_judge_decision(self):
        source = (REPO / 'scripts/evaluate_generation.py').read_text()
        self.assertIn('0005-phase-3-judge-retry-runtime.md', source)


if __name__ == '__main__':
    unittest.main()
