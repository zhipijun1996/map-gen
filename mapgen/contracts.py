"""Versioned, immutable input snapshots. No file access or implicit defaults."""
from dataclasses import dataclass
import hashlib
import json
import math


class InputError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise InputError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def keys(value, expected, path):
    require(isinstance(value, dict), path + ': expected object')
    require(set(value) == set(expected), path + ': missing=' + str(sorted(set(expected) - set(value))) +
            ', unknown=' + str(sorted(set(value) - set(expected))))


def strings(value, path):
    require(isinstance(value, list) and all(isinstance(v, str) and v for v in value), path + ': expected string array')
    require(len(value) == len(set(value)), path + ': duplicate values')


def number(value, path, minimum=None, integer=False):
    finite = type(value) is int or type(value) is float and math.isfinite(value)
    require(type(value) in ((int,) if integer else (int, float)) and finite, path + ': expected finite ' + ('integer' if integer else 'number'))
    require(minimum is None or value >= minimum, path + ': below minimum ' + str(minimum))


@dataclass(frozen=True)
class GenerationRequest:
    _json: str

    @classmethod
    def from_dict(cls, data):
        keys(data, ['schema', 'seed', 'player', 'terminals', 'start_origin_blocks', 'module_filter', 'air_loop'], 'request')
        require(data['schema'] == 'mapgen/generation-request/v1', 'request.schema: unsupported version')
        number(data['seed'], 'request.seed', integer=True)
        keys(data['player'], ['abilities', 'clearance_half_extents_pixels'], 'request.player')
        strings(data['player']['abilities'], 'request.player.abilities')
        require('recoil' not in data['player']['abilities'], 'request.player.abilities: use native shot_recoil, not internal recoil alias')
        clearance = data['player']['clearance_half_extents_pixels']
        require(isinstance(clearance, list) and len(clearance) == 2, 'request.player.clearance: expected two dimensions')
        for v in clearance:
            number(v, 'request.player.clearance', minimum=0.000001)
        keys(data['terminals'], ['start', 'boss'], 'request.terminals')
        for role, value in data['terminals'].items():
            keys(value, ['module_id', 'port_id'], 'request.terminals.' + role)
            require(all(isinstance(v, str) and v for v in value.values()), 'request.terminals: empty identity')
        require(data['terminals']['start']['module_id'] != data['terminals']['boss']['module_id'], 'request.terminals: start and boss must use distinct modules')
        origin = data['start_origin_blocks']
        require(isinstance(origin, list) and len(origin) == 2 and all(type(v) is int for v in origin), 'request.start_origin_blocks: expected two integers')
        keys(data['module_filter'], ['regions', 'include_ids', 'exclude_ids'], 'request.module_filter')
        for key, value in data['module_filter'].items():
            strings(value, 'request.module_filter.' + key)
        require(not set(data['module_filter']['include_ids']) & set(data['module_filter']['exclude_ids']), 'request.module_filter: include/exclude overlap')
        keys(data['air_loop'], ['enabled', 'entry_module_ids', 'return_module_ids'], 'request.air_loop')
        require(type(data['air_loop']['enabled']) is bool, 'request.air_loop.enabled: expected boolean')
        for key in ('entry_module_ids', 'return_module_ids'):
            strings(data['air_loop'][key], 'request.air_loop.' + key)
        return cls(canonical(data))

    def to_dict(self):
        return json.loads(self._json)


@dataclass(frozen=True)
class GeneratorConfig:
    _json: str

    @classmethod
    def from_dict(cls, data):
        keys(data, ['schema', 'algorithm', 'random', 'goals', 'shape', 'scoring', 'search', 'seals'], 'config')
        require(data['schema'] == 'mapgen/generator-config/v1' and data['algorithm'] == 'stable-v2', 'config: unsupported schema/algorithm')
        require(data['random'] == dict(algorithm='python-mt19937-v1', selection='uniform_top_k'), 'config.random: unsupported random/selection algorithm')
        sections = {
            'goals': ['growth_target', 'reward_target', 'main_paths_required'],
            'shape': ['target_ratio', 'soft_tolerance', 'max_aspect'],
            'scoring': ['auto_connection', 'repeat_module', 'growth_noise', 'perimeter', 'aspect', 'left_bias', 'height_bias', 'usable_exit', 'bidirectional_exit', 'terminal_slot', 'dead_end', 'vertical_exit', 'distinct_direction', 'reward_reserve', 'reservation_repeat', 'reservation_area', 'reward_noise', 'reward_near_radius', 'reward_near_penalty', 'closure_noise', 'boss_distance'],
            'search': ['growth_frontier_limit', 'growth_choice_count', 'close_attempts', 'close_depth', 'closure_beam_width', 'candidate_expansion_budget', 'per_seed_timeout_seconds', 'max_growth_backtracks', 'max_rewind_depth', 'max_terminal_states', 'max_layout_repairs', 'growth_shortlist', 'closure_source_limit', 'closure_target_distance2', 'closure_distance_limit2', 'boss_choice_count', 'reward_choice_count', 'budget_check_interval', 'reserve_from_growth_count'],
            'seals': ['thickness_pixels'],
        }
        for section, fields in sections.items():
            keys(data[section], fields, 'config.' + section)
            for key, value in data[section].items():
                if key == 'per_seed_timeout_seconds' and value is None:
                    continue
                integer = section == 'goals' or section == 'search' and key != 'per_seed_timeout_seconds'
                number(value, 'config.' + section + '.' + key, integer=integer)
        for key, minimum in [('growth_target', 2), ('reward_target', 0), ('main_paths_required', 1)]:
            require(data['goals'][key] >= minimum, 'config.goals.' + key + ': invalid goal')
        for key in sections['search']:
            if key == 'per_seed_timeout_seconds':
                value = data['search'][key]
                require(value is None or value > 0, 'config.search.per_seed_timeout_seconds: expected positive seconds or null')
                continue
            minimum = 0 if key in ('close_attempts', 'max_layout_repairs', 'max_growth_backtracks') else 1
            value = data['search'][key]
            require(value is None or value >= minimum, 'config.search.' + key + ': invalid limit')
        require(data['shape']['target_ratio'] > 0 and data['shape']['soft_tolerance'] >= 1 and data['shape']['max_aspect'] >= 1, 'config.shape: invalid ratio/tolerance')
        require(data['seals']['thickness_pixels'] > 0, 'config.seals: thickness must be positive')
        for key, value in data['scoring'].items():
            require(value <= 0 if key == 'dead_end' else value >= 0, 'config.scoring.' + key + ': invalid sign')
        return cls(canonical(data))

    def to_dict(self):
        return json.loads(self._json)

    def solver_parameters(self):
        data = self.to_dict(); score = data['scoring']
        params = dict(data['goals'], **data['search'])
        params['scoring'] = score
        params['shape'] = dict(data['shape'], aspect_weight=score['aspect'], perimeter_weight=score['perimeter'],
                               left_bias=score['left_bias'], height_bias=score['height_bias'], vertical_exit_weight=score['vertical_exit'],
                               distinct_direction_weight=score['distinct_direction'], reserve_weight=score['reward_reserve'],
                               reserve_from_growth_count=data['search']['reserve_from_growth_count'])
        params['expansion_weights'] = {k: score[k] for k in ('usable_exit', 'bidirectional_exit', 'terminal_slot', 'dead_end')}
        return params


def request_fingerprint(request, config, library):
    value = dict(request=request.to_dict(), config=config.to_dict(), library_sha256=library.sha256,
                 implementation='mapgen/interface-v1')
    return hashlib.sha256(canonical(value).encode()).hexdigest()
