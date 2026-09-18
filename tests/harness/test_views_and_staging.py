"""State-view and plan-order regressions, not application evaluation results."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('harness_views', ROOT / 'scripts/harness.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.features = [
            dict(id='phase-0', name='Foundation', status='verified', dependencies=[]),
            dict(id='phase-1', name='Evaluation Dataset', status='not_started', dependencies=['phase-0']),
            dict(id='p1-policies', parent='phase-1', status='not_started', dependencies=[]),
            dict(id='p1-annotations', parent='phase-1', status='not_started', dependencies=['p1-policies']),
            dict(id='p1-dataset-checks', parent='phase-1', status='not_started', dependencies=['p1-annotations'])]

    def test_status_selects_next_phase_and_shows_dependency_blockers(self):
        result = h.status_view(self.features)
        self.assertIn('Current milestone: phase-1', result)
        self.assertIn('p1-policies (open phase-1 first)', result)
        self.assertIn('p1-annotations → waiting for p1-policies', result)
        self.assertIn('p1-dataset-checks → waiting for p1-annotations', result)
        self.assertIn('not proof that verification gates are available', result)
        self.assertNotIn('acceptance_criteria', result)

    def test_status_prioritizes_active_task_and_limits_eligibility(self):
        self.features[1]['status'] = 'in_progress'
        self.features[2]['status'] = 'in_progress'
        self.features[3]['dependencies'] = []
        result = h.status_view(self.features)
        self.assertIn('Active:\n  p1-policies', result)
        self.assertIn('waiting for active task p1-policies', result)
        self.assertNotIn('Eligible task:', result)

    def test_explicit_phase_blocker_prevents_eligible_work(self):
        self.features[1].update(status='blocked', blocker='Waiting for policy samples')
        result = h.status_view(self.features)
        self.assertIn('Waiting for policy samples', result)
        self.assertNotIn('Eligible task:', result)

    def test_completed_children_do_not_hide_explicit_phase_blocker(self):
        for task in self.features[2:]:
            task['status'] = 'verified'
        self.features[1].update(status='blocked', blocker='Review a phase-level failure')
        result = h.status_view(self.features)
        self.assertIn('Milestone blocker: Review a phase-level failure', result)
        self.assertNotIn('set phase-1 implemented', result)

    def test_implemented_task_is_awaiting_verification(self):
        self.features[1]['status'] = 'in_progress'
        self.features[2]['status'] = 'implemented'
        self.assertIn('Awaiting verification:\n  p1-policies', h.status_view(self.features))

    def test_finished_children_require_phase_verification(self):
        for task in self.features[2:]:
            task['status'] = 'verified'
        self.features[1]['status'] = 'in_progress'
        self.assertIn('run verify-task phase-1', h.status_view(self.features))
        self.features[1]['status'] = 'verified'
        self.assertIn('All milestones verified', h.status_view(self.features))

    def test_unverified_phase_dependency_is_shown(self):
        self.features[0]['status'] = 'blocked'
        self.features[0]['blocker'] = 'Needs repair'
        self.features[1]['status'] = 'in_progress'
        # Active task selects its own phase, even when a predecessor is reopened.
        self.features[2]['status'] = 'in_progress'
        self.assertIn('waiting for phase-0', h.status_view(self.features))

    def test_views_do_not_mutate_state_or_evidence(self):
        before = copy.deepcopy(self.features)
        h.status_view(self.features)
        self.assertEqual(self.features, before)
        state_before = (ROOT / 'feature_list.json').read_bytes()
        evidence_before = set((ROOT / 'verification/evidence').iterdir())
        for args in (['status'], ['task', 'p1-policies']):
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/harness.py'), *args],
                                    cwd='/tmp', capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            if args[0] == 'task':
                task = json.loads(result.stdout)
                self.assertEqual(task['id'], 'p1-policies')
                self.assertEqual(task['effective_dependencies'], ['phase-0'])
                for field in ('description', 'spec_sections', 'dependencies', 'acceptance_criteria',
                              'required_gates', 'status', 'evidence'):
                    self.assertIn(field, task)
                self.assertNotIn('features', task)
        self.assertEqual((ROOT / 'feature_list.json').read_bytes(), state_before)
        self.assertEqual(set((ROOT / 'verification/evidence').iterdir()), evidence_before)

    def test_task_unknown_id_is_usage_error(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/harness.py'), 'task', 'missing'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Unknown task', result.stderr)

    def test_invalid_state_fails_views(self):
        for args in (['status'], ['task', 'p1-policies']):
            with patch.object(h, 'check', return_value=['Invalid fixture state']), \
                 patch('sys.argv', ['harness.py', *args]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(h.main(), 1)


class GateStagingTests(unittest.TestCase):
    def setUp(self):
        self.features = h.read_json(ROOT / 'feature_list.json')['features']
        self.tasks = {f['id']: f for f in self.features}

    def test_phase_one_defers_complete_dataset_validation(self):
        for task in ('p1-policies', 'p1-annotations'):
            self.assertEqual(self.tasks[task]['required_gates'], ['harness'])
        for task in ('p1-dataset-checks', 'phase-1'):
            self.assertEqual(self.tasks[task]['required_gates'], ['harness', 'dataset'])

    def test_generation_implementation_does_not_require_full_quality_gate(self):
        for task in ('p3-generation', 'p3-citations'):
            self.assertEqual(self.tasks[task]['required_gates'], ['harness','unit','integration','isolation'])
        for task in ('p3-generation-evaluation', 'phase-3'):
            self.assertEqual(self.tasks[task]['required_gates'],
                             ['harness','unit','integration','dataset','retrieval','generation','isolation','regression','system'])

    def test_phase_three_local_generation_decision_is_persistent(self):
        decision = (ROOT / 'docs/decisions/0003-phase-3-local-generation.md').read_text()
        generation = ' '.join(self.tasks['p3-generation']['acceptance_criteria'])
        citations = ' '.join(self.tasks['p3-citations']['acceptance_criteria'])
        evaluation = ' '.join(self.tasks['p3-generation-evaluation']['acceptance_criteria'])
        for value in ('qwen2.5:7b-instruct-q4_K_M', 'feature-hashing-v1', 'num_ctx: 8192',
                      'num_predict: 384'):
            self.assertIn(value, decision)
        self.assertIn('qwen2.5:7b-instruct-q4_K_M', generation)
        self.assertIn('first five retrieved chunks', generation)
        self.assertIn('trusted seller-scoped retrieval metadata', citations)
        self.assertIn('annotated gold evidence separately', evaluation)
        self.assertIn('missing Ollama service', evaluation)

    def test_roadmap_can_bootstrap_its_verification_capabilities(self):
        # Simulate only scheduling, never promote repository tasks or fabricate evidence.
        # These owners match the tasks' documented runner implementation responsibilities.
        provides = {'p1-dataset-checks': {'dataset'},
                    'p2-ingestion': {'unit', 'integration', 'isolation'},
                    'p2-retrieval-evaluation': {'retrieval'},
                    'p3-generation-evaluation': {'generation', 'regression', 'system'},
                    'p4-abstention-evaluation': {'abstention'}}
        available = {'harness'}
        finished = set()
        while True:
            previous = len(finished)
            for task in self.features:
                if task['id'] in finished:
                    continue
                deps = set(h.prerequisites(task, self.tasks))
                deps.update(c['id'] for c in h.children(task['id'], self.features))
                if deps <= finished and set(task['required_gates']) <= available | provides.get(task['id'], set()):
                    available.update(provides.get(task['id'], set()))
                    finished.add(task['id'])
            if len(finished) == previous:
                break
        self.assertEqual(set(self.tasks) - finished, set(), 'Gate availability blocks a prerequisite of its own runner')


if __name__ == '__main__':
    unittest.main()
