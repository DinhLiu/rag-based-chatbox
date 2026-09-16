"""Real CLI recovery fixtures and bounded gate execution; no product evidence."""
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
spec = importlib.util.spec_from_file_location('recovery_harness', REPO / 'scripts/harness.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for name in (*h.REQUIRED, 'scripts/harness.py'):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / name, target)
        self.tests = self.root / 'tests/harness'
        self.tests.mkdir(parents=True)
        (self.tests / 'test_fixture.py').write_text(
            'import unittest\nclass Fixture(unittest.TestCase):\n'
            ' def test_fixture(self): self.assertEqual(2 + 2, 4)\n')
        state = h.read_json(self.root / 'feature_list.json')
        state['features'] = [f for f in state['features'] if not f.get('parent')]
        for task in state['features']:
            task.update(status='not_started', evidence=[], required_gates=['harness'], blocker=None)
        state['features'][0]['status'] = 'in_progress'
        for name, deps in (('a', []), ('b', ['a']), ('c', ['b'])):
            state['features'].append(dict(state['features'][0], id=name, parent='phase-0',
                                          status='not_started', dependencies=deps))
        h.save_json(self.root / 'feature_list.json', state)

    def cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, 'scripts/harness.py', *args],
                                cwd=self.root, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def edit(self, task_id, **changes):
        state = h.read_json(self.root / 'feature_list.json')
        next(f for f in state['features'] if f['id'] == task_id).update(changes)
        h.save_json(self.root / 'feature_list.json', state)

    def verified_chain(self):
        for name in ('a', 'b', 'c', 'phase-0', 'phase-1'):
            self.edit(name, status='implemented')
            self.cli('verify-task', name)
        self.edit('phase-2', status='in_progress')
        state = h.read_json(self.root / 'feature_list.json')
        state['features'].append(dict(state['features'][2], id='p2-active', parent='phase-2',
                                      dependencies=[], status='in_progress'))
        h.save_json(self.root / 'feature_list.json', state)
        self.cli('check')

    def test_failed_child_cascades_and_recovers_through_cli(self):
        self.verified_chain()
        history = {p: p.read_bytes() for p in (self.root / 'verification/evidence').glob('*.json')}
        failing = self.tests / 'test_failure.py'
        failing.write_text('import unittest\nclass Failure(unittest.TestCase):\n'
                           ' def test_failure(self): self.fail("injected failure")\n')
        self.cli('verify-task', 'a', expected=1)
        self.cli('check')
        self.cli('status')
        tasks = {f['id']: f for f in h.read_json(self.root / 'feature_list.json')['features']}
        for name in ('a', 'phase-0'):
            self.assertEqual(tasks[name]['status'], 'implemented')
        for name in ('b', 'c', 'phase-1', 'phase-2', 'p2-active'):
            self.assertEqual(tasks[name]['status'], 'blocked')
            self.assertIn('revalidation', tasks[name]['blocker'])
        for name in ('a', 'b', 'c', 'phase-0', 'phase-1', 'phase-2'):
            self.assertEqual(tasks[name]['evidence'], [])
        self.assertEqual(tasks['phase-3']['status'], 'not_started')
        for path, content in history.items():
            self.assertEqual(path.read_bytes(), content)
        failing.unlink()
        self.cli('verify-task', 'a')
        # Blocked dependents require explicit resume and fresh verification.
        for name in ('b', 'c', 'phase-0', 'phase-1'):
            self.edit(name, status='implemented', blocker=None)
            self.cli('verify-task', name)
        self.edit('phase-2', status='in_progress', blocker=None)
        self.cli('check')
        self.cli('status')

    def test_unavailable_parent_recheck_leaves_valid_recoverable_state(self):
        runner = self.root / 'scripts/harness.py'
        original = runner.read_text()
        # A temporary fixture runner supplies unit until it becomes unavailable.
        runner.write_text(original.replace('def execute(gate):',
            'def execute(gate):\n    if gate == "unit":\n        print("fixture unit pass")\n        return 0'))
        self.edit('phase-0', required_gates=['harness', 'unit'])
        self.verified_chain()
        runner.write_text(original)
        self.cli('verify-task', 'phase-0', expected=3)
        self.cli('check')
        tasks = {f['id']: f for f in h.read_json(self.root / 'feature_list.json')['features']}
        self.assertEqual(tasks['phase-1']['status'], 'blocked')
        self.assertEqual(tasks['p2-active']['status'], 'blocked')
        runner.write_text(original.replace('def execute(gate):',
            'def execute(gate):\n    if gate == "unit":\n        print("fixture unit restored")\n        return 0'))
        self.cli('verify-task', 'phase-0')

    def test_invalid_candidate_is_not_saved(self):
        self.edit('a', status='implemented')
        before = (self.root / 'feature_list.json').read_bytes()
        # Gate claims success but the referenced report does not exist.
        with patch.object(h, 'ROOT', self.root), \
             patch.object(h, 'snapshot', return_value='a' * 64), \
             patch.object(h, 'run_gate', return_value=(0, 'verification/evidence/missing.json')), \
             patch('sys.argv', ['harness.py', 'verify-task', 'a']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(h.main(), 1)
        self.assertEqual((self.root / 'feature_list.json').read_bytes(), before)

    def test_timed_out_gate_cannot_promote_through_cli(self):
        runner = self.root / 'scripts/harness.py'
        runner.write_text(runner.read_text().replace('generation=900', 'generation=0.2').replace(
            'def execute(gate):', 'def execute(gate):\n    if gate == "generation":\n'
            '        import time\n        print("fixture generation started", flush=True)\n'
            '        time.sleep(30)'))
        self.edit('a', status='implemented', required_gates=['harness', 'generation'])
        self.cli('verify-task', 'a', expected=1)
        self.cli('check')
        task = next(f for f in h.read_json(self.root / 'feature_list.json')['features'] if f['id'] == 'a')
        self.assertEqual(task['status'], 'implemented')
        self.assertEqual(task['evidence'], [])
        records = list((self.root / 'verification/evidence').glob('*-generation.json'))
        self.assertEqual(len(records), 1)
        self.assertTrue(h.read_json(records[0])['timed_out'])

    def test_invalidation_handles_reverse_order_and_unrelated_tasks(self):
        self.verified_chain()
        state = h.read_json(self.root / 'feature_list.json')
        tasks = {f['id']: f for f in state['features']}
        unrelated = dict(tasks['a'], id='unrelated', status='implemented', evidence=[], dependencies=[])
        state['features'].append(unrelated)
        tasks['a'].update(status='implemented', evidence=[])
        state['features'].reverse()
        h.invalidate_dependents(state['features'])
        self.assertEqual(h.check(self.root, state), [])
        self.assertEqual(unrelated['status'], 'implemented')
        self.assertEqual(tasks['c']['status'], 'blocked')
        previous = json.dumps(state)
        h.invalidate_dependents(state['features'])
        self.assertEqual(json.dumps(state), previous)


class TimeoutTests(unittest.TestCase):
    def test_each_gate_has_positive_finite_budget(self):
        self.assertEqual(set(h.GATE_TIMEOUTS), set(h.GATES))
        for seconds in h.GATE_TIMEOUTS.values():
            self.assertIsInstance(seconds, int)
            self.assertGreater(seconds, 0)
        self.assertLess(h.GATE_TIMEOUTS['unit'], h.GATE_TIMEOUTS['integration'])
        self.assertLess(h.GATE_TIMEOUTS['integration'], h.GATE_TIMEOUTS['generation'])

    def test_real_timeout_records_partial_output_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            (root / 'scripts/harness.py').write_text(
                'import sys, time\nprint("started", flush=True)\n'
                'print("diagnostic", file=sys.stderr, flush=True)\ntime.sleep(30)\n')
            h.save_json(root / 'feature_list.json', {'features': []})
            with patch.dict(h.GATE_TIMEOUTS, generation=0.2), \
                 contextlib.redirect_stdout(io.StringIO()):
                code, relative = h.run_gate('generation', 'fixture', root)
            record = h.read_json(root / relative)
            self.assertEqual(code, 1)
            self.assertEqual(record['status'], 'failed')
            self.assertTrue(record['timed_out'])
            self.assertEqual(record['timeout_seconds'], 0.2)
            self.assertIn('started', record['stdout'])
            self.assertIn('diagnostic', record['stderr'])
            self.assertIn('timed out', record['stderr'])


if __name__ == '__main__':
    unittest.main()
