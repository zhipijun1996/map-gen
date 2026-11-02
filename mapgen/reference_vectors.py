"""Executable CPython RNG/numeric compatibility vectors; no engine implementation."""
import random
import struct
from types import SimpleNamespace

from .solver import StableSolver


def _number(value):
    return dict(value=value, binary64_be=struct.pack('>d', value).hex())


def generate_vectors(config):
    streams = []
    for seed in (0, -1, 930001, 2**63 + 7, 2**128 + 123):
        rng = random.Random(seed)
        values = dict(seed=str(seed), random=[_number(rng.random()) for _ in range(8)],
                      getrandbits=[dict(bits=n, value=str(rng.getrandbits(n))) for n in (0, 1, 31, 32, 64, 127)],
                      randrange=[dict(stop=str(n), value=str(rng.randrange(n))) for n in (1, 5, 22, 2**32 + 1)])
        array = list(range(22)); rng.shuffle(array); values['shuffle_22'] = array
        values['uniform_minus3_plus3'] = [_number(rng.uniform(-3, 3)) for _ in range(8)]
        state = rng.getstate(); values['saved_state'] = state
        branch = [rng.randrange(5), rng.random(), rng.getrandbits(32)]
        rng.setstate(state); restored = [rng.randrange(5), rng.random(), rng.getrandbits(32)]
        if branch != restored:
            raise RuntimeError('CPython state restoration mismatch')
        values['restored_branch'] = branch; streams.append(values)
    context = SimpleNamespace(config=config.solver_parameters())
    shapes = [dict(bounds=b, cost=_number(StableSolver.shape_cost(context, b))) for b in
              ([0, 0, 100, 10], [0, 0, 102, 10], [0, 0, 100, 12], [0, 0, 60, 40],
               [0, 0, 81, 40], [-37, -26, 42, 15], [0, 0, 40, 60])]
    tied = [['first', 1], ['second', 1], ['third', 2], ['fourth', 1]]
    return dict(random_algorithm='python-mt19937-v1', state_version=3, streams=streams,
                shape_cost=shapes, stable_sort=dict(input=tied, descending=sorted(tied, key=lambda row: row[1], reverse=True)))
