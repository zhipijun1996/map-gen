#!/usr/bin/env python3
"""Validate archived evidence; optionally replay all seeds without changing it."""
import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'experiments/seed-study'
OUT = STUDY / 'output'
sys.path.insert(0, str(STUDY))
import run_batch
from generate import connection_groups, prepare_library
from model import LIB, OPPOSITE, permitted

def read(path):
    return json.loads(path.read_text())

def verify_failed_candidate(items):
    occupied = set()
    graph = defaultdict(list)
    for item in items:
        x, y = item['origin']
        w, h = item['size_blocks']
        assert all(type(n) is int for n in (x, y, w, h))
        for bx in range(x, x + w):
            for by in range(y, y + h):
                assert (bx, by) not in occupied
                occupied.add((bx, by))
        for p in item['ports'].values():
            u, v = p['local2']
            if p['face'] in ('LEFT', 'RIGHT'):
                assert u == (0 if p['face'] == 'LEFT' else 2 * w) and v % 2 == 1 and 0 < v < 2 * h
            else:
                assert v == (0 if p['face'] == 'TOP' else 2 * h) and u % 2 == 1 and 0 < u < 2 * w
            assert p['world2'] == [2 * x + u, 2 * y + v]
        for route in item['actual_routes']:
            a = item['id'] + '.' + route['from_port'] + ':arrive'
            b = item['id'] + '.' + route['to_port'] + ':depart'
            if item['reward']:
                node = item['id'] + ':reward:' + route['id']
                graph[a].append(node)
                graph[node].append(b)
            else:
                graph[a].append(b)
    for (a, ap, p), (b, bp, q) in connection_groups(items):
        assert p['world2'] == q['world2'] and OPPOSITE[p['face']] == q['face']
        if permitted(p, 'out') and permitted(q, 'in'):
            graph[a['id'] + '.' + ap + ':depart'].append(b['id'] + '.' + bp + ':arrive')
        if permitted(q, 'out') and permitted(p, 'in'):
            graph[b['id'] + '.' + bp + ':depart'].append(a['id'] + '.' + ap + ':arrive')
    boss = next(i for i in items if i['module_id'] == 'BOSS')
    graph['START'].append('M01.R:depart')
    graph[boss['id'] + '.L:arrive'].append('BOSS')

    def reach(source):
        seen = {source}
        queue = deque([source])
        while queue:
            for node in graph[queue.popleft()]:
                if node not in seen:
                    seen.add(node)
                    queue.append(node)
        return seen

    seen = reach('START')
    assert 'BOSS' in seen
    failures = []
    for item in items:
        if item['reward']:
            nodes = [n for n in seen if n.startswith(item['id'] + ':reward:')]
            if not nodes:
                failures.append((item['id'], 'unreachable'))
            elif any('BOSS' not in reach(n) for n in nodes):
                failures.append((item['id'], 'no_return_to_boss'))
    assert failures, 'Archived rejection must have a real static-graph failure'
    return failures

def verify_proposal():
    proposal = read(OUT / 'recommended-60-library.json')
    tasks = proposal['modules']
    assert proposal['status'] == 'PROPOSED_OFFLINE_AUTHORING_TASKS_NOT_TESTED'
    assert len(tasks) == len({t['id'] for t in tasks}) == 60
    assert sum(t['count'] for t in proposal['shape_counts']) == 60
    assert Counter(t['primary_role'] for t in tasks) == Counter(proposal['role_counts'])
    for task in tasks:
        w, h = task['size_blocks']
        ports = {p['id']: p for p in task['ports']}
        assert len(ports) == len(task['ports'])
        assert len({tuple(p['local2']) for p in ports.values()}) == len(ports)
        for p in ports.values():
            u, v = p['local2']
            bx, by = p['edge_block']
            assert 0 <= bx < w and 0 <= by < h
            if p['face'] in ('LEFT', 'RIGHT'):
                assert u == (0 if p['face'] == 'LEFT' else 2 * w) and v == 2 * by + 1
                assert bx == (0 if p['face'] == 'LEFT' else w - 1)
            else:
                assert v == (0 if p['face'] == 'TOP' else 2 * h) and u == 2 * bx + 1
                assert by == (0 if p['face'] == 'TOP' else h - 1)
            assert p['surface'] != 'ROCK' or p['face'] in ('LEFT', 'RIGHT')
            assert not (p['surface'] == 'AIR' and p['face'] == 'BOTTOM' and permitted(p, 'in'))
        for route in task['route_targets']:
            assert route['validation'] == 'DESIGN_TARGET_NOT_CERTIFIED'
            assert permitted(ports[route['from_port']], 'in')
            assert permitted(ports[route['to_port']], 'out')
        if task['primary_role'] == 'traverse':
            assert 2 <= len(ports) <= 3
    print('PASS: proposed 60 authoring tasks, shape/role counts and exact boundary-Block port/permission rules')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replay', action='store_true', help='Recreate all 20 maps or rejections in a temporary directory')
    args = parser.parse_args()
    archive = read(OUT / 'results.json')
    rows = archive['results']
    assert archive['retry_count'] == 0
    assert [r['seed'] for r in rows] == list(range(271028, 271048)) == archive['seeds']
    assert Counter(r['status'] for r in rows) == {'PASS': 16, 'FAIL': 4}
    for name, digest in archive['source_sha256'].items():
        assert hashlib.sha256((STUDY / 'source' / name).read_bytes()).hexdigest() == digest
    diagnosis = {d['seed']: d for d in read(OUT / 'failure-diagnosis.json')}
    prepare_library()
    assert len(LIB) == 52
    for row in rows:
        folder = OUT / f'seed-{row["seed"]}'
        if row['status'] == 'PASS':
            data = read(folder / 'map.json')
            assert data['seed'] == row['seed'] and data['certified_for_game'] is False
            metrics = run_batch.verify(data)
            for key, value in data['summary'].items():
                assert row[key] == value, (row['seed'], key)
            for key, value in metrics.items():
                assert row[key] == value, (row['seed'], key)
            assert row['main_paths'] == 3 and row['rewards'] == 6
            assert row['reachable_instances'] == row['instances']
        else:
            candidate = read(folder / 'failed-candidate.json')
            actual = verify_failed_candidate(candidate['instances'])
            expected = [(f['reward'], f['reason']) for f in diagnosis[row['seed']]['failures']]
            assert actual == expected
            assert not (folder / 'map.json').exists(), 'Rejected candidate must not be published as a valid map'
    summary = read(OUT / 'summary.json')
    assert summary['tested'] == 20 and summary['passed'] == 16 and summary['failed'] == 4
    print('PASS: source hashes, 16 complete accepted maps and all 4 independently confirmed reward rejections')
    verify_proposal()
    if args.replay:
        previous_out = run_batch.OUT
        try:
            with tempfile.TemporaryDirectory(prefix='map-gen-replay-') as temp:
                run_batch.OUT = Path(temp)
                for row in rows:
                    replay = run_batch.worker(row['seed'])
                    assert replay['status'] == row['status'], (row['seed'], replay)
                    name = 'map.json' if row['status'] == 'PASS' else 'failed-candidate.json'
                    assert read(Path(temp) / f'seed-{row["seed"]}' / name) == read(OUT / f'seed-{row["seed"]}' / name), row['seed']
                    print(f'REPLAY {row["seed"]}: {replay["status"]} matches original')
        finally:
            run_batch.OUT = previous_out
        print('PASS: all 20 fixed seeds reproduce the exact archived map or rejected candidate; no archive files changed')

if __name__ == '__main__':
    main()
