"""Real frozen results, native content fidelity and failure consumption contracts."""
import copy
import hashlib
import json
import os
from pathlib import Path
import unittest

from mapgen import generate, GenerationRequest, GeneratorConfig, ModuleLibrary, GenerationHooks
from mapgen.artifacts import validate_result, input_hashes, result_hashes

ROOT = Path(__file__).resolve().parents[2]


class ReferenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = os.environ.get('MAPGEN_REFERENCE_MODULE_ZIP')
        if not source:
            raise RuntimeError('Set MAPGEN_REFERENCE_MODULE_ZIP to the explicit locked real module ZIP.')
        cls.lock = json.loads((ROOT / 'examples/library-lock.json').read_text())
        cls.library = ModuleLibrary.from_zip(source, expected_sha256=cls.lock['sha256'])
        cls.cases = {}
        for name in ('success', 'failure'):
            p = ROOT / 'reference_package/fixtures' / name
            cls.cases[name] = dict(result=json.loads((p / 'result.json').read_text()),
                                   request=GenerationRequest.from_dict(json.loads((p / 'request.json').read_text())),
                                   config=GeneratorConfig.from_dict(json.loads((p / 'config.json').read_text())),
                                   provenance=json.loads((p / 'provenance.json').read_text()))

    def test_real_success_and_failure_are_valid_and_keep_same_default_goals(self):
        for name, case in self.cases.items():
            with self.subTest(case=name):
                receipt = validate_result(case['result'], case['request'], case['config'], self.library)
                self.assertEqual(receipt['status'], 'PASS')
                self.assertEqual(input_hashes(case['request'], case['config'], self.library), case['provenance']['fingerprints'])
                self.assertEqual(result_hashes(case['result']), case['provenance']['result_hashes'])
                self.assertEqual(case['request'].to_dict()['seed'], 930001)
                self.assertEqual(case['config'].to_dict()['goals'], dict(growth_target=32, reward_target=6, main_paths_required=3))
        self.assertEqual(self.cases['failure']['result']['status'], 'SEARCH_EXHAUSTED')
        self.assertIsNone(self.cases['failure']['result']['map'])
        self.assertEqual(self.cases['failure']['result']['content_store'], {})

    def test_result_and_map_json_schemas_reuse_existing_versions(self):
        try:
            import jsonschema
            from referencing import Registry, Resource
        except ImportError:
            self.skipTest('Optional development Schema check requires jsonschema/referencing.')
        schemas = [json.loads(p.read_text()) for p in (ROOT / 'schemas').glob('*.json')]
        registry = Registry().with_resources((s['$id'], Resource.from_contents(s)) for s in schemas)
        schema = next(s for s in schemas if s['$id'] == 'urn:mapgen:generation-result:v1')
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema, registry=registry)
        for case in self.cases.values():
            validator.validate(case['result'])

    def test_dangling_duplicate_or_changed_content_is_rejected(self):
        c = self.cases['success']
        for mutation in ('dangling', 'shared', 'monster', 'reward', 'route', 'edge', 'physics'):
            with self.subTest(mutation=mutation):
                result = copy.deepcopy(c['result']); data = result['map']
                if mutation == 'dangling':
                    result['content_store'].pop(data['instances'][0]['content_ref'])
                elif mutation == 'shared':
                    data['instances'][1]['content_ref'] = data['instances'][0]['content_ref']
                elif mutation in ('monster', 'reward'):
                    field = 'enemies' if mutation == 'monster' else 'reward_sites'
                    next(v for v in result['content_store'].values() if v[field])[field].pop()
                elif mutation == 'route':
                    r = next(r for i in data['instances'] for r in i['routes'] if r['from_port'] != r['to_port'])
                    r['from_port'], r['to_port'] = r['to_port'], r['from_port']
                elif mutation == 'edge':
                    data['graph']['edges'].pop()
                else:
                    data['validation']['whole_map_physics'] = 'PASS'
                with self.assertRaises(ValueError):
                    validate_result(result, c['request'], c['config'], self.library)

    def test_failure_cannot_publish_a_map_or_content(self):
        c = self.cases['failure']
        for key, value in [('map', self.cases['success']['result']['map']), ('content_store', {'content/M01.json': {}})]:
            result = copy.deepcopy(c['result']); result[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                validate_result(result, c['request'], c['config'], self.library)

    def test_deterministic_hash_excludes_only_measured_seconds(self):
        original = self.cases['success']['result']; result = copy.deepcopy(original)
        result['metrics']['generation_seconds'] += 10
        self.assertEqual(result_hashes(result), result_hashes(original))
        result['metrics']['expansions'] += 1
        self.assertNotEqual(result_hashes(result)['deterministic_result_sha256'], result_hashes(original)['deterministic_result_sha256'])

    def test_budget_cancellation_and_progress_keep_failure_and_copy_semantics(self):
        c = self.cases['success']; cfg = c['config'].to_dict(); cfg['search']['candidate_expansion_budget'] = 1
        snapshots = []
        def checkpoint(event):
            snapshots.append(copy.deepcopy(event)); event['instances'].clear()
        config = GeneratorConfig.from_dict(cfg)
        result = generate(c['request'], self.library, config, hooks=GenerationHooks(on_checkpoint=checkpoint)).to_dict()
        self.assertEqual(result['status'], 'BUDGET_EXHAUSTED'); self.assertTrue(snapshots)
        self.assertEqual(result['diagnostics']['solver_state']['instances'][0]['id'], 'M01')
        validate_result(result, c['request'], config, self.library)
        result = generate(c['request'], self.library, c['config'], hooks=GenerationHooks(cancelled=lambda: True)).to_dict()
        self.assertEqual(result['status'], 'CANCELLED'); validate_result(result, c['request'], c['config'], self.library)

    def test_whole_package_input_and_configuration_fingerprints_are_distinct(self):
        c = self.cases['success']; hashes = input_hashes(c['request'], c['config'], self.library)
        self.assertEqual(len(set(hashes.values())), 4)
        self.assertNotEqual(hashes['request_fingerprint'], self.cases['failure']['provenance']['fingerprints']['request_fingerprint'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
