#!/usr/bin/env python3
"""Reproduce the frozen experiment, then compare all identical seeds, no retry."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

from adapter import HERE, ROOT, SOURCE, RealLibrary, audit, configured_connections, legacy, model, package, placement_diagnosis, read, sha

OUT = HERE / 'output'
SEEDS = list(range(271028, 271048))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


class Observed(legacy.Generator):
    # Instrumentation only: no generation override changes a return value,
    # candidate order, RNG calls, search budget, constraint, or exception.
    phase = 'init'

    def grow(self, *a, **kw):
        self.phase = 'growth'; return super().grow(*a, **kw)

    def close_one(self, *a, **kw):
        self.phase = 'closure_search'; return super().close_one(*a, **kw)

    def add_air_loop(self, *a, **kw):
        self.phase = 'air_loop'; return super().add_air_loop(*a, **kw)

    def finish(self, *a, **kw):
        self.phase = 'boss_rewards_and_graph_validation'; return super().finish(*a, **kw)


def baseline(seed, output):
    sys.path.insert(0, str(ROOT / 'experiments/seed-study'))
    import run_batch
    original = ROOT / 'experiments/seed-study/output'
    expected = next(r for r in read(original / 'results.json')['results'] if r['seed'] == seed)
    with tempfile.TemporaryDirectory(prefix='legacy-reproduce-') as temp:
        run_batch.OUT = Path(temp)
        row = run_batch.worker(seed)
        name = 'map.json' if row['status'] == 'PASS' else 'failed-candidate.json'
        path = Path(temp) / f'seed-{seed}' / name
        assert row['status'] == expected['status']
        assert read(path) == read(original / f'seed-{seed}' / name)
        # JSON semantic equality is the historical replay contract; both raw
        # hashes are also recorded, so serialization differences stay visible.
        return dict(seed=seed, status=row['status'], exact_json_match=True,
                    archive_path=str((original / f'seed-{seed}' / name).relative_to(ROOT)),
                    archive_sha256=sha(original / f'seed-{seed}' / name), replay_sha256=sha(path),
                    summary={k: row[k] for k in ('instances', 'connections', 'cycles', 'rewards', 'main_paths') if k in row})


def real(seed, output, bindings):
    root, manifest = package()
    library = RealLibrary(root, bindings)
    library.install()
    gen = Observed(seed)
    folder = output / f'seed-{seed}'
    folder.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    built = None
    try:
        built = gen.build()
        generation = dict(status='LEGACY_STATIC_PASS', summary=built['summary'])
    except Exception as err:
        generation = dict(status='REJECTED', phase=gen.phase, error=type(err).__name__ + ': ' + str(err))
        (folder / 'failure.txt').write_text(traceback.format_exc())
    write(folder / 'legacy-state.json', dict(seed=seed, phase=gen.phase, instances=copy.deepcopy(gen.items)))
    if generation.get('error') in ('RuntimeError: reward cannot fit','RuntimeError: boss cannot fit'):
        write(folder/'placement-diagnosis.json', placement_diagnosis(gen,
            'reward' if 'reward cannot fit' in generation['error'] else 'boss'))
    items = copy.deepcopy(gen.items)
    notes, blockers = library.decorate(items)
    checked = audit(items)
    blockers += checked['blockers']
    if built is None:
        blockers.insert(0, dict(reason='legacy_generator_rejected', **generation))
    status = 'STATIC_PASS' if not blockers else 'REJECTED'
    candidate = dict(schema='mapgen/legacy-real-study/2', seed=seed,
        status=status, certified_for_game=False,
        package=read(HERE / 'package-lock.json'), bindings=bindings,
        available_abilities=sorted(model.ABILITIES), generation=generation,
        instances=items, connections=[dict(a=a['id']+'.'+ap, b=b['id']+'.'+bp, world2=p['world2'], surface=p['surface'])
            for (a, ap, p), (b, bp, _) in configured_connections(items)],
        air_connected=getattr(gen, 'air_connected', None),
        blockers=blockers, physical_notes=notes, legacy_map=built, independent_audit=checked,
        validation=dict(whole_map_physics='NOT_RUN', gear_seal_physics='NOT_RUN',
                        acceptance=status, no_retry=True))
    write(folder / ('map.json' if status == 'STATIC_PASS' else 'failed-candidate.json'), candidate)
    return dict(seed=seed, status=status, generation=generation,
        instances=len(items), connections=len(candidate['connections']),
        mirrored=sum(i['mirror_x'] for i in items),
        sealed_ports=sum(len(i['sealed_ports']) for i in items),
        rewards=sum(i['reward'] for i in items), reward_sites=checked['all_reward_sites'],
        boss_reachable=checked['boss_reachable'], unreachable_instances=len(checked['unreachable_instances']),
        air_connected=candidate['air_connected'], blockers=len(blockers),
        blocker_reasons=sorted({b['reason'] for b in blockers}),
        seconds=round(time.perf_counter()-started, 4))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=OUT)
    p.add_argument('--bindings', type=Path, default=HERE/'bindings.json', help='Explicit boundary start and package-declared Boss entry')
    p.add_argument('--worker', choices=['baseline', 'real'])
    p.add_argument('--seed', type=int)
    p.add_argument('--baseline-from', type=Path, help='Reuse an already replayed exact baseline, verifying every archived hash')
    args = p.parse_args()
    if args.worker:
        result = baseline(args.seed, args.out) if args.worker == 'baseline' else real(args.seed, args.out, read(args.bindings) if args.bindings else {})
        print(json.dumps(result, ensure_ascii=False)); return
    if args.out.exists():
        raise SystemExit('Refusing to overwrite an existing experiment; choose a new --out')
    args.out.mkdir(parents=True)
    hashes = {p.name: sha(p) for p in SOURCE.glob('*.py')}
    assert hashes == read(ROOT / 'experiments/seed-study/output/results.json')['source_sha256']
    evidence = dict(base_commit='c2ac2c3625f659364b187592c836c5ff2bceb892', source_sha256=hashes,
        seeds=SEEDS, retry_count=0, per_seed_timeout_seconds=90,
        unchanged_defaults=dict(grow_count=32, close_attempts=3, close_max_depth=3, frontier_limit=22,
            closure_sources=24, beam_width=18, rewards=6, main_paths_max=3,
            abilities=sorted(model.ABILITIES)),
        bindings=read(args.bindings) if args.bindings else {}, baseline=[], real=[])
    source_files=[HERE/n for n in ['adapter.py','transform.py','run.py','bindings.json','package-lock.json']]
    generation_hashes={p.name:sha(p) for p in source_files}
    evidence['adapter_source_sha256']=generation_hashes
    kinds=('baseline','real')
    if args.baseline_from:
        previous=read(args.baseline_from)
        assert previous['source_sha256']==hashes
        assert [r['seed'] for r in previous['baseline']]==SEEDS
        for row in previous['baseline']:
            assert row['exact_json_match'] and row['archive_sha256']==row['replay_sha256']==sha(ROOT/row['archive_path'])
        evidence['baseline']=previous['baseline']
        evidence['baseline_reuse_results_sha256']=sha(args.baseline_from)
        kinds=('real',)
    # Complete and verify the original batch before adapting any data.
    for kind in kinds:
        for seed in SEEDS:
            command = [sys.executable, str(Path(__file__).resolve()), '--worker', kind,
                       '--seed', str(seed), '--out', str(args.out.resolve())]
            if args.bindings: command.extend(['--bindings', str(args.bindings.resolve())])
            try:
                process = subprocess.run(command, capture_output=True, text=True, timeout=90)
                if process.returncode:
                    raise RuntimeError(process.stderr)
                row = json.loads(process.stdout)
            except subprocess.TimeoutExpired:
                row = dict(seed=seed, status='TIMEOUT', seconds=90)
            evidence[kind].append(row)
            write(args.out / 'results.json', evidence)
            print(kind, seed, row['status'], row.get('instances', ''), flush=True)
    assert generation_hashes=={p.name:sha(p)for p in source_files}, 'generation source or configuration changed during batch'
    root, manifest = package()
    library = RealLibrary(root, evidence['bindings'])
    write(args.out / 'library-feedback.json', dict(package=read(HERE/'package-lock.json'),
        verified_files=len(manifest['files']), source=manifest['source'],
        imported_modules=len(library.entries), adapted_templates=len(library.templates),
        reward_templates=[t['source_module_id'] for t in library.templates.values() if t['reward']],
        reward_module_count=sum(bool(e['reward_sites']) for e in library.entries.values()),
        declared_reward_sites=sum(len(e['reward_sites']) for e in library.entries.values()),
        reward_association_gaps=library.reward_gaps, adapter_feedback=library.feedback,
        missing_air_roles=library.air_roles, upstream_excluded=library.catalog['excluded']))


if __name__ == '__main__':
    main()
