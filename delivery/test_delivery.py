"""Verify the package in isolation and reject data loss even with refreshed hashes."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from build import build, encoded, NAME, SEED
from verify import bundle_files, verify_bundle


class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='mapgen-delivery-test-')
        cls.root = Path(cls.temp.name)
        cls.receipt = build(cls.root / 'first')
        cls.archive = cls.root / 'first' / (NAME + '.zip')
        with zipfile.ZipFile(cls.archive) as z:
            z.extractall(cls.root / 'unpacked')
        cls.bundle = cls.root / 'unpacked' / NAME

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def modified(self, change=None):
        folder = self.root / 'mutation'
        if folder.exists():
            shutil.rmtree(folder)
        shutil.copytree(self.bundle, folder)
        manifest = json.loads((folder / 'manifest.json').read_text())
        path = folder / manifest['map_ref']
        if change:
            data = json.loads(path.read_text()); change(data); path.write_bytes(encoded(data))
            manifest['files'][manifest['map_ref']] = hashlib.sha256(path.read_bytes()).hexdigest()
            (folder / 'manifest.json').write_bytes(encoded(manifest))
        return folder

    def test_build_is_reproducible_and_refuses_overwrite(self):
        other = build(self.root / 'second')
        self.assertEqual(other['archive_sha256'], self.receipt['archive_sha256'])
        self.assertEqual((self.root / 'second' / (NAME + '.zip')).read_bytes(), self.archive.read_bytes())
        with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
            build(self.root / 'first')

    def test_zip_and_extracted_package_verify(self):
        self.assertEqual(verify_bundle(self.archive), verify_bundle(self.bundle))
        self.assertEqual(self.receipt['stats']['instances'], 46)
        self.assertEqual(self.receipt['stats']['enemy_records'], 18)
        self.assertEqual(self.receipt['stats']['reward_sites'], 11)
        self.assertEqual(self.receipt['stats']['target_reward_instances'], 6)

    def test_extracted_verifier_runs_without_repository_or_site_packages(self):
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
        result = subprocess.run([sys.executable, '-I', '-S', str(self.bundle / 'verify_delivery.py')],
                                cwd=self.root, env=env, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['status'], 'PASS')

    def test_native_terminal_ids_and_mirror_are_not_reapplied(self):
        files = bundle_files(self.archive); data = json.loads(files[f'maps/seed-{SEED}.json'])
        start = next(i for i in data['instances'] if i['role'] == 'start')
        boss = next(i for i in data['instances'] if i['role'] == 'boss')
        self.assertEqual(start['connected_port_ids'], ['exit'])
        self.assertEqual(boss['connected_port_ids'], ['entry'])
        self.assertTrue(boss['transform']['mirror_x'])
        self.assertEqual(next(p['face'] for p in boss['ports'] if p['id'] == 'entry'), 'RIGHT')
        self.assertTrue(all(i['transform']['content_is_materialized'] for i in data['instances']))
        self.assertIsNone(data['anchors']['player_spawn']['position_pixels'])
        self.assertIn('entry', [s['port_id'] for s in start['seals']])
        self.assertIn('exit', [s['port_id'] for s in boss['seals']])

    def test_schema_matches_export(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('Optional JSON Schema test requires jsonschema; core builder/verifier use only the standard library.')
        files = bundle_files(self.archive); schema = json.loads(files['runtime-map.schema.json'])
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(json.loads(files[f'maps/seed-{SEED}.json']))

    def test_semantic_regressions_are_rejected_even_with_new_manifest_hash(self):
        def lost_seal(d):
            next(i for i in d['instances'] if i['seals'])['seals'].pop()
        def reverse_route(d):
            r = next(r for i in d['instances'] for r in i['routes'] if r['from_port'] != r['to_port'])
            r['from_port'], r['to_port'] = r['to_port'], r['from_port']
        def old_alias(d):
            next(i for i in d['instances'] if i['role'] == 'start')['connected_port_ids'] = ['R']
        def duplicate_path(d):
            d['graph']['main_paths'][1] = copy.deepcopy(d['graph']['main_paths'][0])
        def lost_edge(d):
            d['graph']['edges'].pop()
        def duplicate_instance(d):
            d['instances'].append(copy.deepcopy(d['instances'][0]))
        def fake_physics(d):
            d['validation']['whole_map_physics'] = 'PASS'
        def invent_spawn(d):
            d['anchors']['player_spawn']['position_pixels'] = [24, 206]
        def mirror_again(d):
            d['instances'][0]['transform']['content_is_materialized'] = False
        for change in (lost_seal, reverse_route, old_alias, duplicate_path, lost_edge,
                       duplicate_instance, fake_physics, invent_spawn, mirror_again):
            with self.subTest(change=change.__name__):
                with self.assertRaises(ValueError):
                    verify_bundle(self.modified(change))

    def test_lost_monster_or_reward_is_rejected_even_with_new_content_hash(self):
        for field in ('enemies', 'reward_sites'):
            with self.subTest(field=field):
                folder = self.modified(); manifest = json.loads((folder / 'manifest.json').read_text())
                data = json.loads((folder / manifest['map_ref']).read_text())
                for i in data['instances']:
                    path = folder / i['content_ref']; content = json.loads(path.read_text())
                    if content.get(field):
                        content[field].pop(); path.write_bytes(encoded(content))
                        manifest['files'][i['content_ref']] = hashlib.sha256(path.read_bytes()).hexdigest()
                        (folder / 'manifest.json').write_bytes(encoded(manifest))
                        break
                with self.assertRaisesRegex(ValueError, 'materialized_content_changed'):
                    verify_bundle(folder)

    def test_missing_and_damaged_files_are_rejected(self):
        folder = self.modified(); (folder / 'content/M01.json').unlink()
        with self.assertRaisesRegex(ValueError, 'manifest_inventory_mismatch'):
            verify_bundle(folder)
        folder = self.modified(); (folder / 'content/M01.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'file_sha256_mismatch'):
            verify_bundle(folder)


if __name__ == '__main__':
    unittest.main(verbosity=2)
