"""Mutation checks for the fixed Phase 1 dataset validator."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('dataset_validator', REPO / 'scripts/validate_dataset.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class DatasetValidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        shutil.copytree(REPO / 'data', self.root / 'data')
        shutil.copytree(REPO / 'evals', self.root / 'evals')
        self.dataset_path = self.root / validator.DATASET
        self.corpus_path = self.root / validator.CORPUS

    def mutate(self, path, change):
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value, indent=2) + '\n')

    def errors(self):
        return validator.validate(self.root)['errors']

    def test_repository_dataset_passes_with_all_cases_executed(self):
        report = validator.validate(REPO)
        self.assertEqual(report['errors'], [])
        self.assertEqual((report['collected'], report['executed'], report['skipped']), (40, 40, 0))

    def test_empty_dataset_fails(self):
        self.mutate(self.dataset_path, lambda value: value.update(cases=[]))
        self.assertTrue(any('non-empty' in error for error in self.errors()))

    def test_wholly_skipped_dataset_fails(self):
        def skip_all(value):
            for case in value['cases']:
                case['skip'] = True
        self.mutate(self.dataset_path, skip_all)
        errors = self.errors()
        self.assertTrue(any('skipped evaluation cases' in error for error in errors))
        self.assertTrue(any('all cases are skipped' in error for error in errors))

    def test_cross_seller_or_missing_section_identity_fails(self):
        def change(value):
            source = value['cases'][0]['expected_source_identity'][0]
            source.update(seller_id='seller-beacon', section='Section 99')
        self.mutate(self.dataset_path, change)
        errors = self.errors()
        self.assertTrue(any('crosses seller boundary' in error for error in errors))
        self.assertTrue(any('section' in error and 'not found' in error for error in errors))

    def test_unsupported_answer_point_fails(self):
        self.mutate(self.dataset_path, lambda value: value['cases'][0].update(
            expected_answer_points=['purple elephants receive unlimited lifetime service']))
        self.assertTrue(any('not supported by cited sections' in error for error in self.errors()))

    def test_version_and_distribution_mismatches_fail(self):
        self.mutate(self.dataset_path, lambda value: value.update(
            corpus_version='2', distribution={'simple': 40}))
        errors = self.errors()
        self.assertTrue(any('corpus_version does not match' in error for error in errors))
        self.assertTrue(any('declared distribution' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
