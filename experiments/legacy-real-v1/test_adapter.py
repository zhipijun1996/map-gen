"""Contract, rejection, geometry and deterministic replay tests (stdlib only)."""
import copy
from pathlib import Path
import tempfile
import unittest

from adapter import HERE, ROOT, SOURCE, RealLibrary, audit, gear_seal, legacy, model, package, read, segment_hits_rect, sha
from run import real


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack, cls.manifest = package()
        cls.bindings = read(HERE/'proposed-bindings.json')
        cls.library = RealLibrary(cls.pack, cls.bindings)

    def setUp(self):
        self.library.install()

    def test_frozen_sources_and_default_abilities(self):
        hashes = read(ROOT/'experiments/seed-study/output/results.json')['source_sha256']
        self.assertEqual(hashes, {p.name: sha(p) for p in SOURCE.glob('*.py')})
        self.assertEqual(model.ABILITIES, {'jump', 'double_jump', 'recoil', 'grapple'})
        self.assertEqual(Path(legacy.__file__).resolve(), SOURCE/'generate.py')

    def test_corrupted_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp)/'modules.zip'; archive.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'package_sha256_mismatch'):
                package(archive)

    def test_exact_real_ports_routes_and_versions(self):
        self.assertEqual(len(self.library.templates), 115)
        for t in self.library.templates.values():
            source = self.library.entries[t['source_module_id']]
            self.assertEqual(len(t['ports']), len(source['ports']))
            self.assertFalse(t['allow_mirror_x'])
            self.assertEqual(t['content_version'], source['contentVersion'])
            self.assertEqual({r['id'] for r in t['routes']}, {r['id'] for r in source['routes']})
            for r in t['routes']:
                self.assertEqual(r['source_route'], next(s for s in source['routes'] if s['id'] == r['id']))

    def test_owned_rectangle_offset_and_alias_preserve_positions(self):
        t = self.library.templates['BOSS']
        ports = model.placed_ports(t, 7, -3, False)
        self.assertEqual(t['source_bounds']['y'], 120)
        self.assertEqual(t['scene_origin_offset'], [0, -120])
        self.assertEqual(ports['L']['source_port_id'], 'entry')
        self.assertEqual(ports['L']['world2'], [14, 1])

    def test_no_invented_reward_or_air_role(self):
        self.assertFalse(any(k.startswith('Q') for k in model.LIB))
        self.assertNotIn('AIR_A', model.LIB)
        self.assertNotIn('AIR_B', model.LIB)
        missing = {f['module_id'] for f in self.library.feedback if f['reason'] == 'single_port_reward_route_has_no_explicit_requiredRewards'}
        self.assertEqual(missing, {'idea-plains-hq04-001', 'idea-spec02-s13-001'})

    def test_missing_role_bindings_fail_without_placeholder(self):
        library = RealLibrary(self.pack)
        self.assertNotIn('START', library.templates)
        self.assertNotIn('BOSS', library.templates)
        with tempfile.TemporaryDirectory() as temp:
            row = real(271028, Path(temp), {})
            self.assertEqual(row['instances'], 0)
            self.assertIn('missing_explicit_START_or_BOSS_binding', row['generation']['error'])

    def test_four_face_seals_and_path_collision(self):
        expected = {'LEFT': [0,128,32,128], 'RIGHT':[480,128,32,128],
                    'TOP':[128,0,128,32], 'BOTTOM':[128,352,128,32]}
        for face, rect in expected.items():
            p = dict(id='p', face=face, local2={'LEFT':[0,3], 'RIGHT':[8,3], 'TOP':[3,0], 'BOTTOM':[3,6]}[face])
            self.assertEqual(gear_seal(p, [4,3])['rect_pixels'], rect)
        self.assertTrue(segment_hits_rect([-2,0], [4,0], [0,0,2,2]))
        self.assertTrue(segment_hits_rect([1,1], [1,1], [0,0,2,2]))
        self.assertFalse(segment_hits_rect([-2,-1], [4,-1], [0,0,2,2]))

    def test_all_real_seeds_reproduce_exact_rejected_state_and_overlay(self):
        archive = HERE/'output'; results = read(archive/'results.json')
        self.assertEqual(len(results['real']), 20)
        with tempfile.TemporaryDirectory() as temp:
            for expected in results['real']:
                seed = expected['seed']
                with self.subTest(seed=seed):
                    replay = real(seed, Path(temp), self.bindings)
                    self.assertEqual(replay['generation'], expected['generation'])
                    for name in ('legacy-state.json', 'failed-candidate.json'):
                        self.assertEqual(read(Path(temp)/f'seed-{seed}'/name), read(archive/f'seed-{seed}'/name))
                    self.assertFalse((Path(temp)/f'seed-{seed}'/'map.json').exists())
                    data = read(archive/f'seed-{seed}/failed-candidate.json')
                    original = copy.deepcopy(data['instances'])
                    self.library.install()
                    check = audit(data['instances'])
                    self.assertEqual(data['instances'], original)
                    self.assertEqual(check, read(archive/f'audits/seed-{seed}.json'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
