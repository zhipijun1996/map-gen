#!/usr/bin/env python3
"""Run every preregistered seed/variant once; retain complete failures and traces."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from solver import HERE, ROOT, Optimized, audit, legacy, model, package, read, RealLibrary
from adapter import configured_connections, sha


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(path)


def sources():
    paths=list(HERE.glob('*.py'))+[HERE/'config.json',HERE/'PLAN.md']
    paths+=list((ROOT/'experiments/legacy-real-v2').glob('*.py'))
    paths+=[ROOT/'experiments/legacy-real-v2'/n for n in ['bindings.json','package-lock.json']]
    paths+=list((ROOT/'experiments/seed-study/source').glob('*.py'))
    return {str(p.relative_to(ROOT)):sha(p)for p in sorted(paths)}


def worker(seed,variant,folder):
    folder.mkdir(parents=True,exist_ok=True);cfg=read(HERE/'config.json')
    pack,manifest=package();library=RealLibrary(pack);library.install()
    gen=Optimized(seed,library,variant,cfg);started=time.perf_counter();assembled=None;error=None
    failures_path=folder/'search-failures.jsonl.gz'
    def retain_failure(row):
        with gzip.open(failures_path,'at',encoding='utf-8')as stream:
            stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    gen.on_failure=retain_failure
    def checkpoint(g):
        write(folder/'checkpoint.json',dict(seed=seed,variant=variant,phase=g.phase,
            expanded=g.expanded,instances=g.items))
    gen.on_checkpoint=checkpoint
    try:assembled=gen.build()
    except Exception as exc:
        error=dict(type=type(exc).__name__,message=str(exc),phase=gen.phase)
        gen.record_failure(str(exc));(folder/'failure.txt').write_text(traceback.format_exc())
    generation_seconds=time.perf_counter()-started
    write(folder/'solver-state.json',dict(seed=seed,variant=variant,phase=gen.phase,instances=gen.items))
    items=copy.deepcopy(gen.items);notes,blockers=library.decorate(items)
    checked=audit(items);blockers+=checked['blockers']
    if error:blockers.insert(0,dict(reason='search_rejected',**error))
    if assembled is None and not error:blockers.insert(0,dict(reason='missing_original_assembly_result'))
    status='STATIC_PASS'if not blockers else 'REJECTED'
    summary=assembled['summary']if assembled else {}
    stats=dict(expansions=gen.expanded,backtracks=gen.backtracks,layout_repairs=gen.repairs,
        terminal_states=gen.terminal_states,recorded_failures=len(gen.failures),
        closed_loops_across_search=gen.closed_loops,pruning=dict(gen.rejections),generation_seconds=round(generation_seconds,6))
    result=dict(schema='mapgen/optimization-layout/1',seed=seed,variant=variant,status=status,
        certified_for_game=False,package=read(ROOT/'experiments/legacy-real-v2/package-lock.json'),
        bindings=library.bindings,config=cfg,instances=items,
        connections=[dict(a=a['id']+'.'+ap,b=b['id']+'.'+bp,world2=p['world2'],surface=p['surface'])for(a,ap,p),(b,bp,_)in configured_connections(items)],
        independent_audit=checked,blockers=blockers,physical_notes=notes,
        original_assembly=assembled,summary=summary,search=stats,
        main_paths=assembled['main_paths']if assembled else [],
        validation=dict(acceptance=status,original_assembly='PASS'if assembled else 'REJECTED',
            true_reward_route_graph='PASS'if not checked['blockers']else 'REJECTED',
            whole_map_physics='NOT_RUN',fallback_used=False,seed_replaced=False))
    name='map.json'if status=='STATIC_PASS'else 'failed-candidate.json'
    write(folder/name,result);write(folder/'decisions.json',gen.decisions)
    connections=len(result['connections']);n=len(items)
    row=dict(seed=seed,variant=variant,status=status,error=error,instances=n,
        used_base_modules=len({i['source_module_id']for i in items}),
        rewards=sum(i['reward']for i in items),reward_sites=checked['all_reward_sites'],
        connections=connections,cycles=connections-n+1,main_paths=len(result['main_paths']),
        mirrored=sum(i['mirror_x']for i in items),seals=sum(len(i['sealed_ports'])for i in items),
        reachable_instances=n-len(checked['unreachable_instances']),
        blocker_reasons=sorted({b['reason']for b in blockers}),
        bounds_blocks=legacy.bounds(items),**stats,
        file_sha256=sha(folder/name),state_sha256=sha(folder/'solver-state.json'))
    write(folder/'result.json',row)
    return row


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=HERE/'output')
    p.add_argument('--stage',choices=['pilot','benchmark'],default='benchmark')
    p.add_argument('--worker',action='store_true');p.add_argument('--seed',type=int)
    p.add_argument('--variant',choices=['route','expansion','backtrack'])
    args=p.parse_args()
    if args.worker:
        print(json.dumps(worker(args.seed,args.variant,args.out),ensure_ascii=False));return
    if args.out.exists():raise SystemExit('Refusing to overwrite an experiment; use a new --out')
    args.out.mkdir(parents=True);cfg=read(HERE/'config.json');frozen=sources()
    for rel in frozen:
        target=args.out/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target)
    baseline_path=ROOT/'experiments/legacy-real-v2/output/results.json';baseline=read(baseline_path)
    for row in baseline['real']:
        folder=baseline_path.parent/f'seed-{row["seed"]}'
        assert read(folder/'failed-candidate.json')['status']=='REJECTED'
    baseline_manifest=read(baseline_path.parent/'SHA256.json')
    for rel,digest in baseline_manifest['source_sha256'].items():assert sha(ROOT/rel)==digest,rel
    for rel,digest in baseline_manifest['artifact_sha256'].items():assert sha(baseline_path.parent/rel)==digest,rel
    seeds=cfg['pilot_seeds']if args.stage=='pilot'else cfg['seeds']
    data=dict(schema='mapgen/optimization-results/1',stage=args.stage,seeds=seeds,
        variants=cfg['variants'],config=cfg,source_sha256=frozen,
        baseline_results_sha256=sha(baseline_path),baseline=baseline['real'],
        fallback_count=0,seed_replacement_count=0,results=[])
    write(args.out/'results.json',data)
    for variant in cfg['variants']:
        for seed in seeds:
            folder=args.out/variant/f'seed-{seed}';folder.mkdir(parents=True)
            command=[sys.executable,str(Path(__file__).resolve()),'--worker','--seed',str(seed),'--variant',variant,'--out',str(folder.resolve())]
            try:
                proc=subprocess.run(command,capture_output=True,text=True,timeout=cfg['per_seed_timeout_seconds'])
                (folder/'worker.log').write_text(proc.stdout+proc.stderr)
                if proc.returncode:row=dict(seed=seed,variant=variant,status='ERROR',error=proc.stderr[-4000:])
                else:row=json.loads(proc.stdout)
            except subprocess.TimeoutExpired as exc:
                row=dict(seed=seed,variant=variant,status='TIMEOUT',seconds=cfg['per_seed_timeout_seconds'])
                (folder/'worker.log').write_bytes((exc.stdout or b'')+(exc.stderr or b''))
                write(folder/'timeout.json',row)
            data['results'].append(row);write(args.out/'results.json',data)
            print(variant,seed,row['status'],row.get('instances'),row.get('error'),flush=True)
            assert frozen==sources(),'implementation/config changed during experiment'


if __name__=='__main__':main()
