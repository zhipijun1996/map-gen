#!/usr/bin/env python3
"""Explicit API example; run from an extracted Python reference package."""
import argparse
import hashlib
import json
from pathlib import Path

from mapgen import generate, GenerationRequest, GeneratorConfig, ModuleLibrary
from mapgen.artifacts import input_hashes, validate_result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('request', 'config', 'module-lock', 'module-zip'):
        p.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args()
    request = GenerationRequest.from_dict(json.loads(args.request.read_text()))
    config = GeneratorConfig.from_dict(json.loads(args.config.read_text()))
    lock = json.loads(args.module_lock.read_text())
    library = ModuleLibrary.from_zip(args.module_zip, expected_sha256=lock['sha256'])
    if library.version != lock['version'] or hashlib.sha256(library._files['catalog.json']).hexdigest() != lock['catalog_sha256']:
        raise ValueError('module version/catalog differs from the explicit lock')
    result = generate(request, library, config)
    validation = validate_result(result.to_dict(), request, config, library)
    print(json.dumps(dict(status=result.status, validation=validation, fingerprints=input_hashes(request, config, library)), indent=2))
    # A host receives BOTH result.map and result.content_store. Never discard
    # the store, reroll entities, or interpret failure diagnostics as a map.
    return 0 if result.status == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
