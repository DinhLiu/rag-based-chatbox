"""Control-plane behavior tests; no product tests or RAG measurements."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('control_plane', REPO / 'scripts/harness.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in h.REQUIRED:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / name, target)
        self.state = h.read_json(self.root / 'feature_list.json')
        self.state['features'] = [f for f in self.state['features'] if 'parent' not in f]
        for task in self.state['features']:
            task.update(status='not_started', evidence=[], blocker=None)
        self.write()

    def write(self):
        h.save_json(self.root / 'feature_list.json', self.state)

    def test_valid_initial_state(self):
        self.assertEqual(h.check(self.root), [])

    def test_missing_routing_document_fails(self):
        (self.root / 'AGENTS.md').unlink()
        self.assertTrue(h.check(self.root))

    def test_unknown_status_and_duplicate_ids_fail(self):
        self.state['features'][0]['status'] = 'done'
        self.write()
        self.assertTrue(h.check(self.root))
        self.state['features'][0]['status'] = 'not_started'
        self.state['features'][1]['id'] = 'phase-0'
        self.write()
        self.assertTrue(h.check(self.root))

    def test_unverified_dependency_and_multiple_active_tasks_fail(self):
        self.state['features'][1]['status'] = 'in_progress'
        self.write()
        self.assertTrue(h.check(self.root))
        self.state['features'][0]['status'] = 'in_progress'
        self.write()
        self.assertTrue(h.check(self.root))

    def test_dependency_cycle_fails(self):
        self.state['features'][0]['dependencies'] = ['phase-1']
        self.write()
        self.assertTrue(h.check(self.root))

    def test_blocker_requires_reason(self):
        self.state['features'][0]['status'] = 'blocked'
        self.write()
        self.assertTrue(h.check(self.root))

    def test_verified_without_evidence_fails(self):
        self.state['features'][0]['status'] = 'verified'
        self.write()
        self.assertTrue(h.check(self.root))

    def test_failed_unavailable_missing_and_wrong_task_evidence_fail(self):
        task = self.state['features'][0]
        task.update(status='verified', evidence=['verification/evidence/fixture.json'])
        record = dict(task_id='phase-0', gate='harness', status='passed', exit_code=0,
                      command=['test-fixture-only'], timestamp='test', stdout='test-only output',
                      snapshot_sha256='0'*64)
        self.write()
        self.assertTrue(h.check(self.root))
        for changes in ({'status':'failed','exit_code':1}, {'status':'unavailable','exit_code':3},
                        {'task_id':'phase-1'}, {'stdout':''}, {'gate':'unit'}):
            h.save_json(self.root / task['evidence'][0], record | changes)
            self.assertTrue(h.check(self.root), changes)

    def test_application_gates_are_unavailable(self):
        for gate in (gate for gate in h.GATES[1:] if gate != 'dataset'):
            with self.subTest(gate=gate), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(h.execute(gate), 3)
                self.assertIn('UNAVAILABLE', output.getvalue())

    def test_dataset_gate_is_available(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(h.execute('dataset'), 0)

    def test_snapshot_tracks_source_not_session_notes(self):
        before = h.snapshot(self.root)
        (self.root / 'progress.md').write_text('Session state only')
        self.assertEqual(before, h.snapshot(self.root))
        (self.root / 'ARCHITECTURE.md').write_text('Changed architecture')
        self.assertNotEqual(before, h.snapshot(self.root))

    def test_empty_and_wholly_skipped_suites_fail(self):
        class Skipped(unittest.TestCase):
            @unittest.skip('fixture only')
            def test_skip(self):
                pass
        for suite in (unittest.TestSuite(), unittest.defaultTestLoader.loadTestsFromTestCase(Skipped)):
            with patch.object(h, 'check', return_value=[]), \
                 patch.object(h.unittest.defaultTestLoader, 'discover', return_value=suite), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(h.execute('harness'), 1)

    def test_failed_or_unavailable_run_cannot_promote_task(self):
        for exit_code in (1, 2, 3):
            self.state['features'][0]['status'] = 'implemented'
            self.write()
            with patch.object(h, 'ROOT', self.root), patch.object(h, 'check', return_value=[]), \
                 patch.object(h, 'snapshot', return_value='a'*64), \
                 patch.object(h, 'run_gate', return_value=(exit_code, 'test-only.json')), \
                 patch('sys.argv', ['harness.py','verify-task','phase-0']), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(h.main(), exit_code)
            task = h.read_json(self.root / 'feature_list.json')['features'][0]
            self.assertEqual(task['status'], 'implemented')
            self.assertEqual(task['evidence'], [])

    def test_successful_gate_promotes_and_records_reference(self):
        self.state['features'][0]['status'] = 'implemented'
        self.write()
        with patch.object(h, 'ROOT', self.root), patch.object(h, 'check', return_value=[]), \
             patch.object(h, 'snapshot', return_value='a'*64), \
             patch.object(h, 'run_gate', return_value=(0, 'fixture-only.json')), \
             patch('sys.argv', ['harness.py','verify-task','phase-0']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(h.main(), 0)
        task = h.read_json(self.root / 'feature_list.json')['features'][0]
        self.assertEqual(task['status'], 'verified')
        self.assertEqual(task['evidence'], ['fixture-only.json'])

    def test_changed_inputs_during_verification_prevent_promotion(self):
        self.state['features'][0]['status'] = 'implemented'
        self.write()
        with patch.object(h, 'ROOT', self.root), patch.object(h, 'check', return_value=[]), \
             patch.object(h, 'snapshot', side_effect=['a'*64, 'b'*64]), \
             patch.object(h, 'run_gate', return_value=(0, 'fixture-only.json')), \
             patch('sys.argv', ['harness.py','verify-task','phase-0']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(h.main(), 1)
        self.assertEqual(h.read_json(self.root / 'feature_list.json')['features'][0]['status'], 'implemented')

    def test_failed_recheck_reopens_verified_task(self):
        self.state['features'][0]['status'] = 'verified'
        self.write()
        with patch.object(h, 'ROOT', self.root), patch.object(h, 'check', return_value=[]), \
             patch.object(h, 'snapshot', return_value='a'*64), \
             patch.object(h, 'run_gate', return_value=(1, 'fixture-only.json')), \
             patch('sys.argv', ['harness.py','verify-task','phase-0']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(h.main(), 1)
        self.assertEqual(h.read_json(self.root / 'feature_list.json')['features'][0]['status'], 'implemented')

    def test_not_started_cannot_be_promoted(self):
        with patch.object(h, 'ROOT', self.root), patch.object(h, 'check', return_value=[]), \
             patch.object(h, 'run_gate') as gate, \
             patch('sys.argv', ['harness.py','verify-task','phase-0']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(h.main(), 1)
            gate.assert_not_called()

    def add_child(self, task_id='p0-fixture', parent='phase-0'):
        child = dict(self.state['features'][0], id=task_id, parent=parent,
                     dependencies=[], evidence=[], status='not_started')
        self.state['features'].append(child)
        return child

    def verify_fixture(self, task):
        # Synthetic evidence stays in the temporary fixture repository.
        relative = f"verification/evidence/{task['id']}.json"
        h.save_json(self.root / relative, dict(task_id=task['id'], gate='harness',
                    status='passed', exit_code=0, command=['fixture-only'], timestamp='test',
                    stdout='fixture', snapshot_sha256='0'*64))
        task.update(status='verified', evidence=[relative])

    def test_parent_and_one_active_child_are_valid(self):
        self.state['features'][0]['status'] = 'in_progress'
        self.add_child()['status'] = 'in_progress'
        self.write()
        self.assertEqual(h.check(self.root), [])
        self.add_child('p0-second')['status'] = 'in_progress'
        self.write()
        self.assertTrue(h.check(self.root))

    def test_invalid_parent_links_fail(self):
        child = self.add_child()
        for parent in ('missing', 'p0-fixture', None, 42):
            child['parent'] = parent
            self.write()
            self.assertTrue(h.check(self.root), parent)
        child['parent'] = 'phase-0'
        self.add_child('nested', 'p0-fixture')
        self.write()
        self.assertTrue(h.check(self.root))

    def test_child_inherits_phase_prerequisites(self):
        self.state['features'][1]['status'] = 'blocked'
        self.state['features'][1]['blocker'] = 'fixture'
        self.add_child('p1-fixture', 'phase-1')['status'] = 'in_progress'
        self.write()
        self.assertTrue(h.check(self.root))
        self.verify_fixture(self.state['features'][0])
        self.write()
        self.assertEqual(h.check(self.root), [])

    def test_child_requires_open_parent(self):
        self.add_child()['status'] = 'in_progress'
        self.write()
        self.assertTrue(h.check(self.root))

    def test_child_cannot_depend_on_own_parent_or_later_phase(self):
        child = self.add_child()
        for dependency in ('phase-0', 'phase-1'):
            child['dependencies'] = [dependency]
            self.write()
            self.assertTrue(h.check(self.root))

    def test_phase_requires_verified_children_and_own_evidence(self):
        parent = self.state['features'][0]
        child = self.add_child()
        self.verify_fixture(parent)
        self.write()
        self.assertTrue(h.check(self.root))
        self.verify_fixture(child)
        self.write()
        self.assertEqual(h.check(self.root), [])
        parent['evidence'] = []
        self.write()
        self.assertTrue(h.check(self.root))

    def test_phase_promotion_rejects_unfinished_children(self):
        self.state['features'][0]['status'] = 'implemented'
        self.add_child()
        self.write()
        with patch.object(h, 'ROOT', self.root), patch.object(h, 'check', return_value=[]), \
             patch.object(h, 'run_gate') as gate, \
             patch('sys.argv', ['harness.py', 'verify-task', 'phase-0']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(h.main(), 1)
            gate.assert_not_called()

    def test_failed_child_recheck_reopens_verified_parent(self):
        parent = self.state['features'][0]
        parent['status'] = 'verified'
        child = self.add_child()
        child['status'] = 'verified'
        self.write()
        with patch.object(h, 'ROOT', self.root), patch.object(h, 'check', return_value=[]), \
             patch.object(h, 'snapshot', return_value='a'*64), \
             patch.object(h, 'run_gate', return_value=(3, 'fixture-only.json')), \
             patch('sys.argv', ['harness.py', 'verify-task', child['id']]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(h.main(), 3)
        updated = h.read_json(self.root / 'feature_list.json')
        self.assertEqual(updated['features'][0]['status'], 'implemented')
        self.assertEqual(updated['features'][0]['evidence'], [])

    def test_cli_usage_and_unavailable_have_distinct_codes(self):
        for arguments, expected in (([], 2), (['verify','unknown'], 2),
                                    (['verify-task','unknown'], 2), (['_run','retrieval'], 3)):
            result = subprocess.run([sys.executable, str(REPO / 'scripts/harness.py'), *arguments],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, expected, result.stderr + result.stdout)

    def test_aggregate_exit_precedence(self):
        for codes, expected in (([0,0],0), ([0,3],3), ([3,2],2), ([3,1],1), ([2,1],1)):
            self.assertEqual(h.combined_exit(codes), expected)

    def test_evidence_distinguishes_usage_from_unavailable(self):
        for code, status in ((2, 'usage_error'), (3, 'unavailable')):
            result = subprocess.CompletedProcess([], code, stdout='fixture', stderr='')
            with patch.object(h.subprocess, 'run', return_value=result), \
                 contextlib.redirect_stdout(io.StringIO()):
                actual, relative = h.run_gate('retrieval', root=self.root)
            self.assertEqual(actual, code)
            self.assertEqual(h.read_json(self.root / relative)['status'], status)


if __name__ == '__main__':
    unittest.main()
