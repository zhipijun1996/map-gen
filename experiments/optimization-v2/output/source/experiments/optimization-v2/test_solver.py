"""Shape/goal failure gates, constructive reservations and all-case replay audit."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from solver import HERE,ROOT,Spatial,create_solver,RealLibrary,audit,package,read,legacy,model
from run import worker,read_payload,payload_path
from metrics import actual_paths,quality,shape_metrics
from adapter import sha


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p,_=package();cls.library=RealLibrary(p);cls.cfg=read(HERE/'config.json')
        cls.study=Path(os.environ.get('MAPGEN_STUDY_OUT',str(HERE/'output')))
        if not cls.study.exists():cls.study=HERE/'pilot-02'

    def setUp(self):self.library.install()

    def test_shape_cost_reverses_the_long_strip_feedback(self):
        g=Spatial(920001,self.library,'shape',self.cfg)
        old=g.shape_cost([0,0,100,10]);horizontal=g.shape_cost([0,0,102,10]);vertical=g.shape_cost([0,0,100,12])
        self.assertGreater(horizontal,old);self.assertLess(vertical,old)
        self.assertLess(g.shape_cost([0,0,60,40]),g.shape_cost([0,0,120,10]))

    def test_shape_and_three_paths_are_independent_hard_gates(self):
        item=dict(origin=[0,0],size_blocks=[100,10],reward=False)
        cfg=dict(self.cfg,reward_target=0)
        q=quality([item],[['START','BOSS']]*3,True,cfg)
        self.assertTrue(q['targets_pass']);self.assertFalse(q['shape_pass']);self.assertFalse(q['effect_pass'])
        item['size_blocks']=[20,10]
        q=quality([item],[['START','BOSS']]*2,True,cfg)
        self.assertTrue(q['shape_pass']);self.assertFalse(q['targets_pass']);self.assertFalse(q['effect_pass'])
        self.assertFalse(quality([item],[['START','BOSS']]*3,False,cfg)['effect_pass'])

    def test_fixed_unseen_seeds_do_not_overlap_pilot_or_calibration(self):
        c=self.cfg['cohorts']
        self.assertEqual(c['validation'],list(range(930001,930021)))
        self.assertFalse(set(c['validation'])&set(c['calibration']))
        self.assertFalse(set(c['validation'])&set(c['pilot']))
        self.assertEqual(self.cfg['growth_target'],32);self.assertEqual(self.cfg['reward_target'],6)
        self.assertEqual(self.cfg['main_paths_required'],3);self.assertEqual(self.cfg['shape']['max_aspect'],3)

    def test_reservation_is_a_constructive_nonoverlapping_reward_witness(self):
        d=read(self.study/'results.json')
        row=next(r for r in d['results']if r['variant']=='stable'and r['status']=='PASS')
        folder=self.study/row['cohort']/'stable'/f'seed-{row["seed"]}'
        raw=read_payload(folder/'solver-state.json')['instances'];base=[i for i in raw if not i['reward']]
        g=Spatial(row['seed'],self.library,'stable',self.cfg);g.items=base
        rooms=g.reservation(base,6,True);self.assertEqual(len(rooms),6)
        trial=copy.deepcopy(base)
        for room in rooms:
            room=copy.deepcopy(room);room['id']=f'M{len(trial)+1:02}'
            self.assertFalse(any(model.overlap(room,i)for i in trial));trial.append(room)
            self.assertTrue(g.valid_reward_state(trial))

    def test_all_trials_are_present_and_passes_meet_every_gate(self):
        d=read(self.study/'results.json');expected=sum(len(s)for s in d['cohorts'].values())*4
        self.assertEqual(len(d['results']),expected)
        self.assertEqual(len({(r['cohort'],r['variant'],r['seed'])for r in d['results']}),expected)
        for row in d['results']:
            with self.subTest(cohort=row['cohort'],variant=row['variant'],seed=row['seed']):
                self.assertNotEqual(row['status'],'ERROR')
                folder=self.study/row['cohort']/row['variant']/f'seed-{row["seed"]}'
                if row['status']=='TIMEOUT':
                    self.assertTrue((folder/'timeout.json').exists());continue
                name='map.json'if row['status']=='PASS'else 'failed-candidate.json'
                self.assertEqual(sha(payload_path(folder/name)),row['file_sha256'])
                raw=read_payload(folder/'solver-state.json')['instances'];notes,blocks=self.library.decorate(raw)
                checked=audit(raw);body=read_payload(folder/name)
                self.assertEqual(checked,body['independent_audit'])
                if row['status']=='PASS':
                    self.assertEqual(blocks+checked['blockers'],[])
                    self.assertTrue(all(row['quality'][k]for k in ['static_pass','targets_pass','shape_pass','effect_pass']))
                    self.assertEqual(row['rewards'],6);self.assertEqual(row['main_paths'],3)
                    self.assertLessEqual(row['quality']['aspect'],3);self.assertGreaterEqual(row['instances'],39)
                    self.assertLessEqual(row['expansions'],self.cfg['candidate_expansion_budget'])
                    edges={tuple(e)for e in checked['edges']}
                    for path in body['main_paths']:
                        self.assertEqual((path[0],path[-1]),('START','BOSS'))
                        self.assertTrue(all((a,b)in edges for a,b in zip(path,path[1:])))
                else:self.assertFalse((folder/'map.json.gz').exists())

    def test_baseline_remains_the_original_v1_geometry(self):
        with tempfile.TemporaryDirectory()as temp:
            folder=Path(temp)/'baseline';worker(271028,'baseline',folder,'calibration')
            actual=read_payload(folder/'solver-state.json')['instances']
            expected=read_payload(ROOT/'experiments/optimization-v1/output/backtrack/seed-271028/solver-state.json')['instances']
            self.assertEqual(actual,expected)

    def test_representative_signatures_and_states_reproduce(self):
        d=read(self.study/'results.json');picked={}
        for row in d['results']:
            if row['status']not in ('ERROR','TIMEOUT'):picked.setdefault((row['cohort'],row['variant'],row['status']),row)
        # At least six independent profile/cohort representatives when available.
        chosen=list(picked.values())
        with tempfile.TemporaryDirectory()as temp:
            for row in chosen:
                with self.subTest(cohort=row['cohort'],profile=row['variant'],seed=row['seed']):
                    folder=Path(temp)/row['cohort']/row['variant']/str(row['seed'])
                    got=worker(row['seed'],row['variant'],folder,row['cohort'])
                    self.assertEqual(got['status'],row['status'])
                    self.assertEqual(got['structural_sha256'],row['structural_sha256'])
                    original=self.study/row['cohort']/row['variant']/f'seed-{row["seed"]}'/'solver-state.json'
                    self.assertEqual(read_payload(folder/'solver-state.json'),read_payload(original))


if __name__=='__main__':unittest.main(verbosity=2)
