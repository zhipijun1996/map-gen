"""Real-package fidelity, affine transforms, actual reward edges, exact replays."""
import copy
from concurrent.futures import ThreadPoolExecutor
import math
from pathlib import Path
import tempfile
import unittest

from adapter import HERE, ROOT, SOURCE, RealLibrary, audit, gear_seal, legacy, model, package, read, sha
from run import real
from transform import ellipse_sample, materialize, transform_geometry


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack,cls.manifest=package();cls.library=RealLibrary(cls.pack)

    def setUp(self):self.library.install()

    def assert_tree_close(self,a,b):
        self.assertEqual(type(a),type(b))
        if isinstance(a,dict):
            self.assertEqual(set(a),set(b))
            for k in a:self.assert_tree_close(a[k],b[k])
        elif isinstance(a,list):
            self.assertEqual(len(a),len(b))
            for x,y in zip(a,b):self.assert_tree_close(x,y)
        elif isinstance(a,(int,float)) and not isinstance(a,bool):self.assertAlmostEqual(a,b,places=8)
        else:self.assertEqual(a,b)

    def test_original_sources_unchanged(self):
        expected=read(ROOT/'experiments/seed-study/output/results.json')['source_sha256']
        self.assertEqual(expected,{p.name:sha(p)for p in SOURCE.glob('*.py')})
        self.assertEqual(model.ABILITIES,{'jump','double_jump','recoil','grapple'})
        self.assertEqual(Path(legacy.__file__).resolve(),SOURCE/'generate.py')

    def test_locked_package_and_corrupt_archive_rejection(self):
        self.assertEqual(sha(ROOT/'.cache/legacy-real-v2/modules.zip'),'5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723')
        with tempfile.TemporaryDirectory()as temp:
            p=Path(temp)/'bad.zip';p.write_bytes(b'not the locked package')
            with self.assertRaisesRegex(ValueError,'package_sha256_mismatch'):package(p)

    def test_concurrent_readers_extract_atomically_and_reject_tampered_manifest(self):
        with tempfile.TemporaryDirectory()as temp:
            archive=Path(temp)/'modules.zip'
            archive.write_bytes((ROOT/'.cache/legacy-real-v2/modules.zip').read_bytes())
            with ThreadPoolExecutor(max_workers=4)as pool:
                results=list(pool.map(package,[archive]*4))
            self.assertEqual(len({str(p)for p,_ in results}),1)
            target=results[0][0]
            manifest=read(target/'manifest.json');manifest['files']={}
            (target/'manifest.json').write_text(__import__('json').dumps(manifest))
            with self.assertRaisesRegex(ValueError,'manifest_hash_mismatch'):package(archive)

    def test_all_content_bases_ports_and_routes_preserved(self):
        self.assertEqual(len(self.library.entries),115)
        self.assertEqual({t['source_module_id']for t in model.LIB.values()},set(self.library.entries))
        for t in model.LIB.values():
            e=self.library.entries[t['source_module_id']]
            self.assertEqual({p['source_port_id']for p in t['all_ports']},{p['id']for p in e['ports']})
            self.assertEqual({r['id']for r in t['all_routes']},{r['id']for r in e['routes']})
            self.assertTrue(t['allow_mirror_x'])
            self.assertNotIn('mirrorX',e)

    def test_treasure_detection_and_multirole_aliases(self):
        self.assertEqual(sum(bool(e['reward_sites'])for e in self.library.entries.values()),31)
        self.assertEqual(sum(len(e['reward_sites'])for e in self.library.entries.values()),32)
        self.assertEqual(sum(k.startswith('Q:')for k in model.LIB),26)
        for mid in ['idea-plains-hq04-001','idea-spec02-s13-001']:
            self.assertEqual(model.LIB['Q:'+mid]['routes'][0]['reward_ids'],['reward'])
        mid='b31-n08-reward-return-interface0'
        self.assertIs(model.LIB['T:'+mid]['compiled_content'],model.LIB['Q:'+mid]['compiled_content'])
        self.assertIs(model.LIB['T:'+mid]['routes'],model.LIB['Q:'+mid]['routes'])
        self.assertEqual(self.library.reward_gaps['modulesWithGaps'],5)

    def test_boss_uses_declared_entry_and_retains_exit(self):
        t=model.LIB['BOSS'];self.assertEqual(self.library.entries[t['source_module_id']]['entryPortIds'],['entry'])
        self.assertEqual({p['id']for p in t['ports']},{'L'})
        ps=model.placed_ports(dict(t,ports=t['all_ports']),7,-3,True)
        self.assertEqual(set(ps),{'L','exit'})
        self.assertEqual(ps['L']['source_port_id'],'entry')
        self.assertEqual(ps['L']['face'],'RIGHT')
        self.assertEqual(ps['L']['world2'],[32,1])
        self.assertEqual(t['scene_origin_offset'],[0,-120])

    def test_terminal_unused_ports_are_retained_and_sealed(self):
        start=legacy.make('START',0,0,iid='M01')
        notes,blockers=self.library.decorate([start])
        self.assertEqual(start['solver_port_ids'],['R'])
        self.assertEqual(set(start['ports']),{'entry','R'})
        self.assertEqual({s['port_id']for s in start['sealed_ports']},{'entry','R'})
        self.assertEqual(start['effective_routes'],[])

    def test_all_115_full_content_double_mirrors_restore_normalized_source(self):
        seen=set()
        for t in model.LIB.values():
            if t['source_module_id']in seen:continue
            seen.add(t['source_module_id'])
            source=copy.deepcopy(t['compiled_content'])
            base=materialize(t,False);base.pop('coordinate_frame');base.pop('source_affine')
            w=t['size_blocks'][0]*128
            restored=transform_geometry(transform_geometry(base,w,mirror=True),w,mirror=True)
            with self.subTest(module=t['source_module_id']):self.assert_tree_close(base,restored)
            self.assertEqual(t['compiled_content'],source)
        self.assertEqual(len(seen),115)

    def test_directional_turret_and_reward_mirror(self):
        t=model.LIB['T:idea-plains-hq05-001'];base=materialize(t,False);reflected=materialize(t,True);w=t['size_blocks'][0]*128
        a=next(x for x in base['approved_hq_cells']if x['kind']=='hit_turret')
        b=next(x for x in reflected['approved_hq_cells']if x['kind']=='hit_turret')
        self.assertAlmostEqual(b['muzzle'][0],w-a['muzzle'][0])
        self.assertEqual(b['direction'],[-a['direction'][0],a['direction'][1]])
        reward=materialize(model.LIB['Q:idea-plains-hq04-001'],True)['reward_sites'][0]
        self.assertEqual(reward['position'],[64,132]);self.assertEqual(reward['region'],[24,104,80,56])

    def test_ellipse_reflection_matches_source_at_identical_time(self):
        t=model.LIB['T:idea-spec02-s11-001'];a=materialize(t,False)['moving_platforms'][0];b=materialize(t,True)['moving_platforms'][0];w=t['size_blocks'][0]*128
        for f in [0,.125,.25,.375,.5,.75]:
            p=ellipse_sample(a,f);q=ellipse_sample(b,f)
            angle=math.pi+2*math.pi*f
            self.assertAlmostEqual(p[0],a['ellipse_center'][0]+a['ellipse_radii'][0]*math.cos(angle))
            self.assertAlmostEqual(p[1],a['ellipse_center'][1]+a['ellipse_radii'][1]*math.sin(angle))
            self.assertAlmostEqual(q[0],w-p[0]);self.assertAlmostEqual(q[1],p[1])

    def test_mirroring_never_reverses_route_ids_or_endpoints(self):
        for t in model.LIB.values():
            full=dict(t,ports=t['all_ports'])
            a=model.placed_ports(full,0,0,False);b=model.placed_ports(full,0,0,True)
            for r in t['all_routes']:
                aa=a[r['from_port']]['world2'];ab=a[r['to_port']]['world2']
                ba=b[r['from_port']]['world2'];bb=b[r['to_port']]['world2']
                self.assertEqual(bb[0]-ba[0],-(ab[0]-aa[0]));self.assertEqual(bb[1]-ba[1],ab[1]-aa[1])

    def test_four_face_seals_stay_inside_owned_rectangle(self):
        for face,loc in [('LEFT',[0,3]),('RIGHT',[8,3]),('TOP',[3,0]),('BOTTOM',[3,6])]:
            s=gear_seal(dict(id='p',face=face,local2=loc),[4,3]);x,y,w,h=s['rect_pixels']
            self.assertTrue(0<=x<x+w<=512 and 0<=y<y+h<=384)

    def test_every_reward_graph_node_has_real_route_association(self):
        for p in(HERE/'output').glob('seed-*/failed-candidate.json'):
            d=read(p);instances={i['id']:i for i in d['instances']}
            for node in d['independent_audit']['route_reward_nodes']:
                i=instances[node['instance']];r=next(r for r in i['effective_routes']if r['id']==node['route_id'])
                self.assertTrue(node['reward_ids']);self.assertLessEqual(set(node['reward_ids']),set(r['reward_ids']))

    def test_20_exact_candidate_and_raw_state_replays(self):
        out=HERE/'output';rows=read(out/'results.json')['real'];self.assertEqual(len(rows),20)
        with tempfile.TemporaryDirectory()as temp:
            for expected in rows:
                seed=expected['seed']
                with self.subTest(seed=seed):
                    actual=real(seed,Path(temp),self.library.bindings)
                    self.assertEqual(actual['generation'],expected['generation']);self.assertEqual(actual['status'],expected['status'])
                    name='map.json' if actual['status']=='STATIC_PASS'else 'failed-candidate.json'
                    for filename in ['legacy-state.json',name]:self.assertEqual(read(Path(temp)/f'seed-{seed}'/filename),read(out/f'seed-{seed}'/filename))
                    p=out/f'seed-{seed}/placement-diagnosis.json'
                    if p.exists():self.assertEqual(read(p),read(Path(temp)/f'seed-{seed}/placement-diagnosis.json'))


if __name__=='__main__':unittest.main(verbosity=2)
