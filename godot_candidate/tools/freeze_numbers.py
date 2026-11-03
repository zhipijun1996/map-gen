"""Supplement immutable 0.2.0 vectors without modifying them."""
import json
import random
import struct
from pathlib import Path

root = Path(__file__).resolve().parents[1]
rng = random.Random(90210)
tokens = ['0.0', '-0.0', '5e-324', '2.2250738585072014e-308',
          '2.225073858507201e-308', '1.7976931348623157e308',
          '9007199254740993.0', '0.12088995980580686', '0.35']
for _ in range(400):
    value = struct.unpack('>d', rng.getrandbits(64).to_bytes(8, 'big'))[0]
    if value == value and abs(value) != float('inf'):
        tokens.append(repr(value))
numbers = [dict(token=token, binary64_be=struct.pack('>d', float(token)).hex()) for token in tokens]
seeds = []
for seed in (-9007199254740991, 9007199254740991, 4294967296, -4294967296):
    r = random.Random(seed)
    seeds.append(dict(seed=str(seed), random_bits=[struct.pack('>d', r.random()).hex() for _ in range(32)], state=r.getstate()))
(root/'tests/number-vectors.json').write_text(json.dumps(dict(numbers=numbers, seeds=seeds), indent=2)+'\n')
