"""Directional entry/closure counterexamples and independent study verification."""
import copy
import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest

from solver import HERE, ROOT, BudgetExhausted, Optimized, RealLibrary, audit, legacy, model, package, read
from run import actual_paths, worker, payload_path, read_payload
from adapter import sha


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p,_=package();cls.library=RealLibrary(p);cls.cfg=read(HERE/'config.json')
        cls.study=Path(os.environ.get('MAPGEN_STUDY_OUT',str(HERE/'output')))
        if not cls.study.exists():cls.study=HERE/'pilot-02'

    def setUp(self):self.library.install()

    def gen(self,variant='route',seed=910001):return Optimized(seed,self.library,variant,self.cfg)

    def test_actual_entry_rejects_reverse_single_route(self):
        g=self.gen();g.add(legacy.make('START',0,0));source=g.frontier()[0]
        mid='T:game-plains-micro-landing'
        raw=list(g.raw_candidates(source,{mid},g.items));filtered=list(g.candidates(source,{mid},g.items))
        self.assertEqual({p for _,p in raw},{'entry','exit'})
        self.assertEqual({p for _,p in filtered},{'entry'})
        self.assertGreater(g.rejections['no_route_from_actual_entry'],0)

    def test_geometrical_frontier_cannot_invent_departure_after_wrong_arrival(self):
        g=self.gen();g.add(legacy.make('START',0,0));source=g.frontier()[0]
        item=next(i for i,p in g.raw_candidates(source,{'T:game-plains-micro-landing'},g.items)if p=='exit')
        g.add(item)
        self.assertTrue(g.frontier())
        self.assertEqual(g.reachable_frontier(g.items),[])

    def test_real_seal_intrusion_configuration_is_rejected(self):
        g=self.gen();mid='T:game-plains-ferry-gears'
        for mx in (False,True):
            item=legacy.make(mid,0,0,mx)
            self.assertFalse(g.configuration_ok(item,{'entry','exit'}))
            self.assertTrue(g.configuration_ok(item,{'entry','exit','C'}))

    def test_no_reward_node_for_nonclaiming_return_route(self):
        g=self.gen();item=legacy.make('Q:b31-n08-reward-return-interface0',20,0,iid='M02')
        _,rewards,_=g.graph([item],potential=True)
        self.assertEqual([n for _,n in rewards],['M02:reward:reward-outbound'])

    def test_budget_stops_without_reducing_targets(self):
        cfg=dict(self.cfg,candidate_expansion_budget=1)
        g=Optimized(910001,self.library,'backtrack',cfg)
        with self.assertRaisesRegex(BudgetExhausted,'candidate_expansion_budget'):g.build()
        self.assertEqual(g.config['growth_target'],32);self.assertEqual(g.config['reward_target'],6)

    def test_preregistered_variants_seeds_and_protected_sources(self):
        self.assertEqual(self.cfg['seeds'],list(range(271028,271048)))
        self.assertEqual(self.cfg['variants'],['route','expansion','backtrack'])
        expected=read(ROOT/'experiments/seed-study/output/results.json')['source_sha256']
        source=ROOT/'experiments/seed-study/source'
        self.assertEqual(expected,{p.name:sha(p)for p in source.glob('*.py')})

    def test_all_recorded_successes_pass_independent_checks_and_actual_paths(self):
        data=read(self.study/'results.json');self.assertEqual(len(data['results']),len(data['seeds'])*3)
        for row in data['results']:
            self.assertNotIn(row['status'],('ERROR','TIMEOUT'))
            folder=self.study/row['variant']/f'seed-{row["seed"]}'
            name='map.json'if row['status']=='STATIC_PASS'else 'failed-candidate.json'
            with self.subTest(variant=row['variant'],seed=row['seed']):
                self.assertEqual(sha(payload_path(folder/name)),row['file_sha256'])
                raw=read_payload(folder/'solver-state.json')['instances'];notes,blockers=self.library.decorate(raw)
                checked=audit(raw);actual=read_payload(folder/name)
                self.assertEqual(checked,actual['independent_audit'])
                if row['status']=='STATIC_PASS':
                    self.assertEqual(blockers+checked['blockers'],[])
                    self.assertEqual(row['rewards'],6);self.assertGreaterEqual(row['instances'],39)
                    self.assertEqual(row['reachable_instances'],row['instances'])
                    self.assertEqual(actual['validation']['original_assembly'],'PASS')
                    self.assertFalse(actual['certified_for_game'])
                    edges={tuple(e)for e in checked['edges']}
                    self.assertTrue(actual['main_paths'])
                    self.assertLessEqual(len(actual['main_paths']),3)
                    for path in actual['main_paths']:
                        self.assertEqual(path[0],'START');self.assertEqual(path[-1],'BOSS')
                        self.assertTrue(all((a,b)in edges for a,b in zip(path,path[1:])))
                else:
                    self.assertFalse((folder/'map.json').exists())
                    with gzip.open(folder/'search-failures.jsonl.gz','rt',encoding='utf-8')as stream:failures=[json.loads(line)for line in stream]
                    self.assertEqual(len(failures),row['recorded_failures']);self.assertTrue(failures)

    def test_replay_each_variant_success_and_failure_without_timing_fields(self):
        data=read(self.study/'results.json');picked={}
        for row in data['results']:picked.setdefault((row['variant'],row['status']),row)
        with tempfile.TemporaryDirectory()as temp:
            for (variant,status),expected in picked.items():
                with self.subTest(variant=variant,status=status):
                    folder=Path(temp)/variant/f'seed-{expected["seed"]}'
                    got=worker(expected['seed'],variant,folder)
                    self.assertEqual(got['status'],status)
                    self.assertEqual(got['structural_sha256'],expected['structural_sha256'])
                    original=self.study/variant/f'seed-{expected["seed"]}'/'solver-state.json'
                    self.assertEqual(read_payload(folder/'solver-state.json'),read_payload(original))


if __name__=='__main__':unittest.main(verbosity=2)
