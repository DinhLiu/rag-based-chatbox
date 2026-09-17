#!/usr/bin/env python3
"""Repository control plane and staged application verification gates."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
GATES = ('harness', 'unit', 'integration', 'dataset', 'retrieval', 'generation',
         'abstention', 'isolation', 'regression', 'system')
GATE_TIMEOUTS = dict(harness=120, unit=60, integration=300, dataset=120,
                     retrieval=600, generation=900, abstention=900,
                     isolation=300, regression=900, system=900)
UNAVAILABLE = 3
STATES = {'not_started', 'in_progress', 'implemented', 'verified', 'blocked'}
REQUIRED = ('AGENTS.md', 'PROJECT_SPEC.md', 'ARCHITECTURE.md', 'README.md',
            'feature_list.json', 'progress.md', 'session-handoff.md', 'init.sh',
            'requirements.txt', 'docs/DEVELOPMENT.md', 'docs/DEFINITION_OF_DONE.md',
            'docs/EVALUATION.md')


def read_json(path):
    return json.loads(path.read_text())


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def children(task_id, features):
    return [f for f in features if f.get('parent') == task_id]


def prerequisites(task, by_id):
    # Parent links group work; children inherit the phase's entry prerequisites.
    return task['dependencies'] + (by_id[task['parent']]['dependencies'] if task.get('parent') else [])


def status_view(features):
    """Render a bounded view; eligibility means entry prerequisites, not verification."""
    by_id = {f['id']: f for f in features}
    active = next((f for f in features if f['status'] == 'in_progress'
                   and not children(f['id'], features)), None)
    pending = [f for f in features if not f.get('parent') and f['status'] != 'verified']
    if not pending:
        return 'All milestones verified. No eligible task.'
    current = (by_id[active.get('parent', active['id'])] if active else
               next((f for f in pending if f['status'] in {'in_progress', 'implemented', 'blocked'}),
                    next((f for f in pending if all(by_id[d]['status'] == 'verified'
                                                   for d in f['dependencies'])), pending[0])))
    rows = children(current['id'], features) or [current]
    lines = [f"Current milestone: {current['id']} — {current['name']} [{current['status']}]",
             'Eligibility is for starting work, not proof that verification gates are available.']
    if current['status'] == 'blocked':
        lines.append(f"Milestone blocker: {current['blocker']}")
    groups = {'Active': [], 'Eligible task': [], 'Awaiting verification': [], 'Blocked': []}
    for task in rows:
        if task['status'] == 'verified':
            continue
        reasons = []
        waiting = list(dict.fromkeys(d for d in prerequisites(task, by_id)
                                    if by_id[d]['status'] != 'verified'))
        if waiting:
            reasons.append('waiting for ' + ', '.join(waiting))
        for item in (current, task) if task is not current else (task,):
            if item['status'] == 'blocked':
                reasons.append(f"{item['id']}: {item['blocker']}")
        if active and task['id'] != active['id']:
            reasons.append('waiting for active task ' + active['id'])
        if reasons:
            groups['Blocked'].append(task['id'] + ' → ' + '; '.join(reasons))
        elif task['status'] == 'in_progress':
            groups['Active'].append(task['id'])
        elif task['status'] == 'implemented':
            groups['Awaiting verification'].append(task['id'])
        else:
            suffix = f" (open {current['id']} first)" if current['status'] == 'not_started' and task is not current else ''
            groups['Eligible task'].append(task['id'] + suffix)
    for title, entries in groups.items():
        if entries:
            lines += ['', title + ':', *('  ' + entry for entry in entries)]
    if current['status'] != 'blocked' and rows != [current] and all(f['status'] == 'verified' for f in rows):
        lines += ['', f"All children verified; set {current['id']} implemented and run verify-task {current['id']}."]
    lines += ['', 'Inspect one record with: .venv/bin/python scripts/harness.py task <id>',
              'A roadmap entry is not authorization to start implementation.']
    return '\n'.join(lines)


def combined_exit(codes):
    if any(code not in (0, 2, UNAVAILABLE) for code in codes):
        return 1
    return 2 if 2 in codes else UNAVAILABLE if UNAVAILABLE in codes else 0


def check(root=ROOT, state=None):
    errors = []
    if not __debug__:
        return ['Optimized Python mode is unsupported: validation assertions must run.']
    for name in REQUIRED:
        if not (root / name).is_file() or not (root / name).read_text().strip():
            errors.append(f'Missing or empty: {name}')
    try:
        if state is None:
            state = read_json(root / 'feature_list.json')
        assert state['schema_version'] == 1
        assert state['source_of_truth'] == 'PROJECT_SPEC.md'
        features = state['features']
        assert isinstance(features, list) and features
        ids = [f['id'] for f in features]
        assert len(set(ids)) == len(ids)
        assert all(f'phase-{i}' in ids for i in range(10))
        by_id = {f['id']: f for f in features}
        assert sum(f['status'] == 'in_progress' and not children(f['id'], features) for f in features) <= 1, 'Only one active leaf task allowed'
        for f in features:
            assert f['status'] in STATES, f"{f['id']}: invalid status"
            for field in ('name', 'description', 'spec_sections', 'acceptance_criteria'):
                assert f[field], f"{f['id']}: empty {field}"
            gates = f['required_gates']
            assert isinstance(gates, list) and gates and len(gates) == len(set(gates))
            assert set(gates) <= set(GATES)
            assert 'harness' in gates
            assert isinstance(f['evidence'], list)
            assert isinstance(f['dependencies'], list)
            assert all(d in by_id and d != f['id'] for d in f['dependencies'])
            if 'parent' in f:
                parent = f['parent']
                assert isinstance(parent, str) and parent in by_id and parent != f['id'], f"{f['id']}: invalid parent"
                assert parent.startswith('phase-') and 'parent' not in by_id[parent], 'Parent must be a top-level phase'
                if f['status'] in {'in_progress', 'implemented', 'verified'}:
                    assert by_id[parent]['status'] in {'in_progress', 'implemented', 'verified', 'blocked'}, f"{f['id']}: parent must be opened first"
            if f['status'] == 'blocked':
                assert isinstance(f['blocker'], str) and f['blocker'].strip()
            if f['status'] in {'in_progress', 'implemented', 'verified'}:
                assert all(by_id[d]['status'] == 'verified' for d in prerequisites(f, by_id)), f"{f['id']}: unverified dependency"
            if f['status'] == 'verified':
                assert all(c['status'] == 'verified' for c in children(f['id'], features)), f"{f['id']}: unverified child"
                found = set()
                fingerprints = set()
                for relative in f['evidence']:
                    path = (root / relative).resolve()
                    assert path.is_relative_to((root / 'verification/evidence').resolve())
                    record = read_json(path)
                    assert record['task_id'] == f['id']
                    assert record['status'] == 'passed' and record['exit_code'] == 0
                    assert record['command'] and record['timestamp'] and record['stdout'].strip()
                    assert len(record['snapshot_sha256']) == 64
                    fingerprints.add(record['snapshot_sha256'])
                    found.add(record['gate'])
                assert set(gates) <= found and len(fingerprints) == 1, f"{f['id']}: missing/inconsistent successful evidence"
        visited = set()
        def visit(task, stack):
            assert task not in stack, 'Dependency cycle'
            if task in visited:
                return
            for dependency in prerequisites(by_id[task], by_id) + [c['id'] for c in children(task, features)]:
                visit(dependency, stack | {task})
            visited.add(task)
        for task in ids:
            visit(task, set())
    except (AssertionError, KeyError, TypeError, ValueError, OSError) as exc:
        errors.append(f'Invalid task state/evidence: {exc}')
    return errors


def snapshot(root=ROOT):
    digest = hashlib.sha256()
    excluded = {'.git', '__pycache__', '.venv', 'node_modules', '.pytest_cache'}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if not path.is_file() or excluded.intersection(relative.parts):
            continue
        if relative.parts[:2] == ('verification', 'evidence') or str(relative) in {
                'feature_list.json', 'progress.md', 'session-handoff.md'}:
            continue
        digest.update(str(relative).encode() + b'\0' + path.read_bytes() + b'\0')
    definitions = read_json(root / 'feature_list.json')
    for feature in definitions['features']:
        for mutable in ('status', 'blocker', 'evidence'):
            feature.pop(mutable, None)
    digest.update(json.dumps(definitions, sort_keys=True).encode())
    return digest.hexdigest()


def invalidate_dependents(features):
    """Reach a valid fixed point after a task loses verification."""
    by_id = {f['id']: f for f in features}
    while True:
        changed = False
        for task in features:
            if task['status'] not in {'in_progress', 'implemented', 'verified'}:
                continue
            waiting = list(dict.fromkeys(d for d in prerequisites(task, by_id)
                                         if by_id[d]['status'] != 'verified'))
            if waiting:
                task.update(status='blocked', evidence=[],
                            blocker='Needs revalidation after prerequisites are verified: ' + ', '.join(waiting))
                changed = True
            elif task['status'] == 'verified' and any(
                    c['status'] != 'verified' for c in children(task['id'], features)):
                task.update(status='implemented', evidence=[], blocker=None)
                changed = True
        if not changed:
            return


def run_gate(gate, task_id=None, root=ROOT):
    command = [sys.executable, 'scripts/harness.py', '_run', gate]
    timeout = GATE_TIMEOUTS[gate]
    timed_out = False
    try:
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        # TimeoutExpired may contain bytes even when text=True.
        stdout = exc.stdout or ''
        stderr = exc.stderr or ''
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors='replace')
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors='replace')
        result = subprocess.CompletedProcess(command, 1, stdout,
                    stderr + f'\nFAIL: {gate} timed out after {timeout} seconds.\n')
    record = dict(task_id=task_id, gate=gate, command=command,
                  timeout_seconds=timeout, timed_out=timed_out,
                  timestamp=datetime.now(timezone.utc).isoformat(),
                  snapshot_sha256=snapshot(root), exit_code=result.returncode,
                  status='passed' if result.returncode == 0 else 'unavailable' if result.returncode == UNAVAILABLE else 'usage_error' if result.returncode == 2 else 'failed',
                  stdout=result.stdout, stderr=result.stderr)
    relative = f'verification/evidence/{uuid4().hex}-{gate}.json'
    save_json(root / relative, record)
    print(f"{gate}: {record['status']} ({relative})")
    if result.returncode:
        print(result.stdout + result.stderr, end='')
    return result.returncode, relative


APPLICATION_SUITES = {
    'unit': ROOT / 'tests/unit',
    'integration': ROOT / 'tests/integration',
    'isolation': ROOT / 'tests/isolation',
}


def run_unittest_tree(gate, directory, extra_compile=()):
    files = sorted(Path(directory).glob('test_*.py'))
    if not files:
        print(f'FAIL: no {gate} tests collected')
        return 1
    for path in [*extra_compile, *files]:
        compile(path.read_text(), str(path), 'exec')
    suite = unittest.defaultTestLoader.discover(str(directory), pattern='test_*.py')
    collected = suite.countTestCases()
    if collected == 0:
        print(f'FAIL: no {gate} tests collected')
        return 1
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    skipped = len(result.skipped)
    failed = len(result.failures) + len(result.errors)
    executed = result.testsRun - skipped
    passed = result.wasSuccessful() and skipped != result.testsRun
    if skipped == result.testsRun:
        print(f'FAIL: all {gate} tests skipped')
    print(json.dumps(dict(gate=gate, collected=collected, executed=executed, skipped=skipped,
                          failed=failed, status='passed' if passed else 'failed'), indent=2))
    return 0 if passed else 1


def execute(gate):
    if gate == 'dataset':
        paths = [ROOT / 'scripts/validate_dataset.py',
                 *sorted((ROOT / 'tests/dataset').glob('test_*.py'))]
        if len(paths) == 1:
            print('FAIL: no dataset tests collected')
            return 1
        for path in paths:
            compile(path.read_text(), str(path), 'exec')
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests/dataset'), pattern='test_*.py')
        if suite.countTestCases() == 0:
            print('FAIL: no dataset tests collected')
            return 1
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        if len(result.skipped) == result.testsRun:
            print('FAIL: all dataset tests skipped')
            return 1
        if not result.wasSuccessful():
            return 1
        validation = subprocess.run(
            [sys.executable, 'scripts/validate_dataset.py'], cwd=ROOT, text=True, capture_output=True)
        print(validation.stdout, end='')
        if validation.stderr:
            print(validation.stderr, file=sys.stderr, end='')
        return validation.returncode
    if gate == 'retrieval':
        paths = [ROOT / 'scripts/evaluate_retrieval.py',
                 *sorted((ROOT / 'tests/retrieval').glob('test_*.py'))]
        if len(paths) == 1:
            print('FAIL: no retrieval tests collected')
            return 1
        for path in paths:
            compile(path.read_text(), str(path), 'exec')
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests/retrieval'), pattern='test_*.py')
        if suite.countTestCases() == 0:
            print('FAIL: no retrieval tests collected')
            return 1
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        if len(result.skipped) == result.testsRun:
            print('FAIL: all retrieval tests skipped')
            return 1
        if not result.wasSuccessful():
            return 1
        evaluation = subprocess.run(
            [sys.executable, 'scripts/evaluate_retrieval.py'], cwd=ROOT,
            text=True, capture_output=True)
        print(evaluation.stdout, end='')
        if evaluation.stderr:
            print(evaluation.stderr, file=sys.stderr, end='')
        return evaluation.returncode
    if gate in APPLICATION_SUITES:
        extra = sorted((ROOT / 'src').glob('*.py')) if gate == 'unit' else ()
        return run_unittest_tree(gate, APPLICATION_SUITES[gate], extra)
    if gate != 'harness':
        print(f'UNAVAILABLE: {gate} has no implemented application runner/fixtures. No checks passed.')
        return UNAVAILABLE
    errors = check()
    if errors:
        print('\n'.join(errors))
        return 1
    # Compile in memory so startup does not create source-tree cache artifacts.
    for path in [ROOT / 'scripts/harness.py', *sorted((ROOT / 'tests/harness').glob('test_*.py'))]:
        compile(path.read_text(), str(path), 'exec')
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests/harness'), pattern='test_*.py')
    if suite.countTestCases() == 0:
        print('FAIL: no harness tests collected')
        return 1
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if len(result.skipped) == result.testsRun:
        print('FAIL: all harness tests skipped')
        return 1
    if result.wasSuccessful():
        print('PASS: harness structure/state, static compilation and behavioral tests. No application behavior verified.')
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('check')
    sub.add_parser('status')
    sub.add_parser('task').add_argument('task_id')
    for name in ('verify', '_run'):
        sub.add_parser(name).add_argument('gate', choices=GATES + (('all',) if name == 'verify' else ()))
    sub.add_parser('verify-task').add_argument('task_id')
    args = parser.parse_args()
    if args.action == 'check':
        errors = check()
        print('\n'.join(errors) if errors else 'PASS: harness structure and task/evidence state')
        return int(bool(errors))
    if args.action == '_run':
        return execute(args.gate)
    if args.action == 'verify':
        codes = [run_gate(g)[0] for g in (GATES if args.gate == 'all' else (args.gate,))]
        return combined_exit(codes)
    errors = check()
    if errors:
        print('\n'.join(errors))
        return 1
    state = read_json(ROOT / 'feature_list.json')
    if args.action == 'status':
        print(status_view(state['features']))
        return 0
    task = next((f for f in state['features'] if f['id'] == args.task_id), None)
    if task is None:
        parser.error(f'Unknown task: {args.task_id}')
    if args.action == 'task':
        by_id = {f['id']: f for f in state['features']}
        print(json.dumps(dict(task, effective_dependencies=list(dict.fromkeys(prerequisites(task, by_id)))),
                         indent=2, ensure_ascii=False))
        return 0
    if task['status'] not in {'implemented', 'verified'}:
        print('Task must exist and be implemented before verification.')
        return 1
    if any(c['status'] != 'verified' for c in children(task['id'], state['features'])):
        print('All child tasks must be verified before verifying their phase.')
        return 1
    before = snapshot()
    results = [run_gate(g, task['id']) for g in task['required_gates']]
    success = all(code == 0 for code, _ in results) and snapshot() == before
    task['status'] = 'verified' if success else 'implemented'
    task['evidence'] = [path for _, path in results] if success else []
    if not success:
        invalidate_dependents(state['features'])
    errors = check(ROOT, state=state)
    if errors:
        print('Refusing to save invalid task state:\n' + '\n'.join(errors))
        return 1
    save_json(ROOT / 'feature_list.json', state)
    print(f"{task['id']}: {task['status']}")
    return 0 if success else combined_exit([code for code, _ in results]) or 1


if __name__ == '__main__':
    sys.exit(main())
