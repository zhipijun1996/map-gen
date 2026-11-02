"""File adapter for the explicit-input API; no downloads or hidden presets."""
import argparse
import json
from pathlib import Path
import sys

from . import generate, GenerationRequest, GeneratorConfig, ModuleLibrary, InputError


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--library', type=Path, required=True)
    p.add_argument('--library-sha256', required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        p.error('refusing to overwrite existing output; choose a new --out')
    try:
        request = GenerationRequest.from_dict(json.loads(args.request.read_text()))
        config = GeneratorConfig.from_dict(json.loads(args.config.read_text()))
        library = ModuleLibrary.from_zip(args.library, expected_sha256=args.library_sha256)
        result = generate(request, library, config)
    except (InputError, ValueError, KeyError, OSError) as exc:
        from . import GenerationResult
        result = GenerationResult('INVALID_INPUT', diagnostics=dict(error=dict(type=type(exc).__name__, message=str(exc))))
    args.out.mkdir(parents=True)
    write(args.out / 'result.json', result.to_dict())
    if result.map is not None:
        write(args.out / 'map.json', result.map)
        for name, value in result.content_store.items():
            write(args.out / name, value)
    print(json.dumps(dict(status=result.status, request_fingerprint=result.fingerprint, metrics=result.metrics), ensure_ascii=False))
    return 0 if result.status == 'PASS' else 2


if __name__ == '__main__':
    sys.exit(main())
