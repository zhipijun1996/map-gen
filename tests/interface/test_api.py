"""Explicit parameters, pure execution, isolation and preservation of real content."""
from concurrent.futures import ThreadPoolExecutor
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mapgen import generate, GenerationRequest, GeneratorConfig, ModuleLibrary, GenerationHooks, InputError
from mapgen.contracts import request_fingerprint
from mapgen.library import PreparedLibrary

ROOT = Path(__file__).resolve().parents[2]


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request_data = json.loads((ROOT / 'examples/request-930001.json').read_text())
        cls.config_data = json.loads((ROOT / 'profiles/stable-v2.json').read_text())
        lock = json.loads((ROOT / 'examples/library-lock.json').read_text())
        cls.library = ModuleLibrary.from_zip(ROOT / '.cache/legacy-real-v2/modules.zip', expected_sha256=lock['sha256'])
        cls.request = GenerationRequest.from_dict(cls.request_data)
        cls.config = GeneratorConfig.from_dict(cls.config_data)
        cls.baseline = generate(cls.request, cls.library, cls.config)
        assert cls.baseline.status == 'PASS', cls.baseline.diagnostics

    def test_default_matches_frozen_reference_including_operation_counts(self):
        folder = ROOT / 'experiments/optimization-v2/output/validation/stable/seed-930001'
        original = json.loads(gzip.decompress((folder / 'solver-state.json.gz').read_bytes()))
        self.assertEqual(self.baseline.diagnostics['solver_state']['instances'], original['instances'])
        body = json.loads(gzip.decompress((folder / 'map.json.gz').read_bytes()))
        self.assertEqual(self.baseline.diagnostics['independent_audit'], body['independent_audit'])
        row = json.loads((folder / 'result.json').read_text())
        for key, value in self.baseline.metrics.items():
            if key != 'generation_seconds':
                self.assertEqual(value, row[key], key)

    def test_inputs_are_immutable_snapshots_and_unknown_keys_fail(self):
        request = copy.deepcopy(self.request_data); typed = GenerationRequest.from_dict(request)
        request['player']['abilities'].clear()
        self.assertEqual(typed.to_dict(), self.request_data)
        for section, change in [('request', lambda d: d.update(unknown=True)),
                                ('config', lambda d: d['search'].update(growth_choices_typo=4))]:
            with self.subTest(section=section), self.assertRaises(InputError):
                data = copy.deepcopy(self.request_data if section == 'request' else self.config_data); change(data)
                (GenerationRequest if section == 'request' else GeneratorConfig).from_dict(data)
        catalog = self.library.read('catalog.json'); catalog['modules'].clear()
        self.assertEqual(len(self.library.read('catalog.json')['modules']), 115)
        with self.assertRaises(TypeError):
            self.library._files['catalog.json'] = b'{}'

    def test_invalid_numeric_values_and_versions_fail_before_search(self):
        cases = [(['goals', 'reward_target'], True), (['goals', 'main_paths_required'], 0),
                 (['goals', 'growth_target'], 2.5), (['shape', 'target_ratio'], float('nan')),
                 (['search', 'growth_shortlist'], -1), (['search', 'per_seed_timeout_seconds'], False),
                 (['random', 'selection'], 'weighted'), (['schema'], 'future')]
        for path, value in cases:
            with self.subTest(path=path), self.assertRaises(InputError):
                data = copy.deepcopy(self.config_data); at = data
                for key in path[:-1]:
                    at = at[key]
                at[path[-1]] = value; GeneratorConfig.from_dict(data)

    def test_core_has_no_file_or_network_io_and_can_repeat(self):
        with patch('builtins.open', side_effect=AssertionError('file I/O in core')), \
             patch.object(Path, 'read_bytes', side_effect=AssertionError('file I/O in core')), \
             patch.object(Path, 'read_text', side_effect=AssertionError('file I/O in core')), \
             patch('urllib.request.urlopen', side_effect=AssertionError('network in core')):
            result = generate(self.request, self.library, self.config)
        self.assertEqual(result.status, 'PASS', result.diagnostics.get('error'))
        self.assertEqual(result.diagnostics['solver_state'], self.baseline.diagnostics['solver_state'])

    def test_reward_and_main_path_goals_are_effective_not_hardcoded(self):
        data = copy.deepcopy(self.config_data); data['goals'].update(reward_target=2, main_paths_required=4)
        result = generate(self.request, self.library, GeneratorConfig.from_dict(data))
        self.assertEqual(result.status, 'PASS', result.diagnostics.get('error'))
        self.assertEqual(len(result.map['anchors']['target_reward_instances']), 2)
        self.assertEqual(len(result.map['graph']['main_paths']), 4)
        self.assertEqual(result.diagnostics['independent_audit']['target_reward_instances'], 2)
        self.assertNotEqual(result.fingerprint, self.baseline.fingerprint)

    def test_budget_cancellation_and_callbacks_do_not_return_fallback_maps(self):
        cfg = copy.deepcopy(self.config_data); cfg['search']['candidate_expansion_budget'] = 1
        checkpoints = []
        def record(event):
            checkpoints.append(copy.deepcopy(event)); event['instances'].clear()
        result = generate(self.request, self.library, GeneratorConfig.from_dict(cfg), hooks=GenerationHooks(on_checkpoint=record))
        self.assertEqual(result.status, 'BUDGET_EXHAUSTED'); self.assertIsNone(result.map)
        self.assertEqual(result.diagnostics['solver_state']['instances'][0]['id'], 'M01')
        self.assertTrue(checkpoints)
        cancelled = generate(self.request, self.library, self.config, hooks=GenerationHooks(cancelled=lambda: True))
        self.assertEqual(cancelled.status, 'CANCELLED'); self.assertIsNone(cancelled.map)
        self.assertEqual(cancelled.content_store, {})

    def test_origin_and_binding_are_request_inputs_including_alias_collisions(self):
        data = copy.deepcopy(self.request_data); data['start_origin_blocks'] = [7, -3]
        data['terminals']['start'] = dict(module_id='idea-interface-s12-001', port_id='L')
        request = GenerationRequest.from_dict(data); prepared = PreparedLibrary(self.library, request, self.config)
        self.assertEqual(prepared.templates['START']['ports'][0]['source_port_id'], 'L')
        self.assertEqual(len(prepared.templates['START']['all_ports']), 4)
        cfg = copy.deepcopy(self.config_data); cfg['search']['candidate_expansion_budget'] = 1
        result = generate(request, self.library, GeneratorConfig.from_dict(cfg))
        self.assertEqual(result.diagnostics['solver_state']['instances'][0]['origin'], [7, -3])
        self.assertEqual(result.status, 'BUDGET_EXHAUSTED')

    def test_region_filters_and_invalid_terminal_are_not_ignored(self):
        data = copy.deepcopy(self.request_data); data['module_filter']['regions'] = ['平原']
        prepared = PreparedLibrary(self.library, GenerationRequest.from_dict(data), self.config)
        self.assertEqual(len(prepared.entries), 106)
        data['module_filter']['regions'] = ['森林']
        result = generate(GenerationRequest.from_dict(data), self.library, self.config)
        self.assertEqual(result.status, 'INVALID_INPUT'); self.assertIsNone(result.map)
        self.assertIn('filtered out', result.diagnostics['error']['message'])
        data = copy.deepcopy(self.request_data); data['air_loop']['entry_module_ids'] = ['idea-interface-s12-001']
        result = generate(GenerationRequest.from_dict(data), self.library, self.config)
        self.assertEqual(result.status, 'INVALID_INPUT')
        self.assertIn('missing declared ROCK -> AIR Route', result.diagnostics['error']['message'])

    def test_concurrent_requests_do_not_share_abilities_or_search_state(self):
        no_abilities = copy.deepcopy(self.request_data); no_abilities['player']['abilities'] = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(generate, self.request, self.library, self.config)
            b = pool.submit(generate, GenerationRequest.from_dict(no_abilities), self.library, self.config)
            good, rejected = a.result(), b.result()
        self.assertEqual(good.status, 'PASS'); self.assertEqual(rejected.status, 'SEARCH_EXHAUSTED')
        self.assertIsNone(rejected.map)
        self.assertEqual(good.diagnostics['solver_state'], self.baseline.diagnostics['solver_state'])
        self.assertNotEqual(good.fingerprint, rejected.fingerprint)

    def test_seal_geometry_and_clearance_are_explicit(self):
        request = copy.deepcopy(self.request_data); request['player']['clearance_half_extents_pixels'] = [16, 20]
        cfg = copy.deepcopy(self.config_data); cfg['seals']['thickness_pixels'] = 40
        prepared = PreparedLibrary(self.library, GenerationRequest.from_dict(request), GeneratorConfig.from_dict(cfg))
        port = prepared.templates['START']['ports'][0]
        seal = prepared.gear_seal(port, prepared.templates['START']['size_blocks'])
        self.assertEqual(seal['thickness_pixels'], 40)
        self.assertEqual(prepared.clearance_rect([0, 0, 40, 128]), [-16, -20, 72, 168])

    def test_native_runtime_output_retains_all_monsters_rewards_and_unknowns(self):
        data = self.baseline.map
        self.assertEqual(data['schema'], 'mapgen/runtime-map/v2')
        self.assertEqual(data['anchors']['start_departure']['port_id'], 'exit')
        self.assertEqual(data['anchors']['boss_arrival']['port_id'], 'entry')
        self.assertEqual(sum(len(c['enemies']) for c in self.baseline.content_store.values()), 18)
        self.assertEqual(sum(len(c['reward_sites']) for c in self.baseline.content_store.values()), 11)
        self.assertEqual(data['validation']['whole_map_physics'], 'NOT_RUN')

    def test_clock_deadline_and_disabled_deadline_are_explicit(self):
        cfg = copy.deepcopy(self.config_data); cfg['search']['per_seed_timeout_seconds'] = .5
        cfg['search']['budget_check_interval'] = 1
        clock_values = iter([0, 0])
        result = generate(self.request, self.library, GeneratorConfig.from_dict(cfg),
                          hooks=GenerationHooks(clock=lambda: next(clock_values, 1)))
        self.assertEqual(result.status, 'BUDGET_EXHAUSTED')
        self.assertEqual(result.diagnostics['error']['message'], 'wall_clock_budget')
        cfg['search']['per_seed_timeout_seconds'] = None
        cfg['search']['candidate_expansion_budget'] = 1
        result = generate(self.request, self.library, GeneratorConfig.from_dict(cfg), hooks=GenerationHooks(clock=lambda: 100))
        self.assertEqual(result.diagnostics['error']['message'], 'candidate_expansion_budget')

    def test_json_schemas_match_input_and_native_output_contracts(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('Optional schema check requires jsonschema; core API uses standard library only.')
        values = [('request', self.request_data), ('config', self.config_data), ('runtime-map', self.baseline.map)]
        cfg = copy.deepcopy(self.config_data); cfg['scoring']['aspect'] = 60.5; cfg['shape']['max_aspect'] = 3.2
        cfg['search']['per_seed_timeout_seconds'] = .5
        GeneratorConfig.from_dict(cfg); values.append(('config', cfg))
        for name, value in values:
            with self.subTest(schema=name):
                schema = json.loads((ROOT / 'schemas' / (name + '.schema.json')).read_text())
                jsonschema.Draft202012Validator.check_schema(schema)
                jsonschema.Draft202012Validator(schema).validate(value)

    def test_cli_works_after_copying_only_the_package_and_explicit_inputs(self):
        with tempfile.TemporaryDirectory(prefix='mapgen-independent-') as temp:
            temp = Path(temp); shutil.copytree(ROOT / 'mapgen', temp / 'mapgen', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copyfile(ROOT / '.cache/legacy-real-v2/modules.zip', temp / 'library.zip')
            for name, data in [('request.json', self.request_data), ('profile.json', self.config_data)]:
                (temp / name).write_text(json.dumps(data))
            env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
            cmd = [sys.executable, '-S', '-m', 'mapgen', '--request', 'request.json', '--config', 'profile.json',
                   '--library', 'library.zip', '--library-sha256', self.library.sha256, '--out', 'generated']
            result = subprocess.run(cmd, cwd=temp, env=env, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['status'], 'PASS')
            runtime = json.loads((temp / 'generated/map.json').read_text())
            self.assertEqual(runtime, self.baseline.map)
            self.assertEqual(len(list((temp / 'generated/content').glob('*.json'))), 46)


if __name__ == '__main__':
    unittest.main(verbosity=2)
