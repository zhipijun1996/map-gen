"""Assemble an independent v4 experiment; old 0.4.2 runtime stays frozen."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION = "mapgen/gdscript-candidate-0.5.0"
ALGORITHM = "stable-v4-reward-branches"


def assemble(out):
    out.mkdir(parents=True, exist_ok=False)
    addon = out / "addons/mapgen"
    addon.mkdir(parents=True)
    for source in (ROOT / "godot_runtime/addons/mapgen").glob("*.gd"):
        shutil.copyfile(source, addon / source.name)
    for source in (ROOT / "branch_routes/runtime").glob("*.gd"):
        shutil.copyfile(source, addon / source.name)
    identity = hashlib.sha256(b"".join(p.name.encode()+p.read_bytes() for p in sorted((ROOT / "branch_routes/runtime").glob("*.gd"))) + (ROOT / "branch_routes/schemas/config.schema.json").read_bytes()).hexdigest()[:12]
    implementation = IMPLEMENTATION + "+" + identity
    protocol = addon / "protocol.gd"
    protocol.write_text(protocol.read_text().replace(IMPLEMENTATION, implementation))
    derived = addon / "derived_library.gd"
    derived.write_text(derived.read_text().replace('const IMPLEMENTATION="mapgen/gdscript-candidate-0.4.2"', f'const IMPLEMENTATION="{implementation}"'))
    schemas = {}
    (out / "schemas").mkdir()
    for source in (ROOT / "schemas").glob("*.json"):
        value = json.loads(source.read_text())
        if source.name == "config.schema.json":
            value = json.loads((ROOT / "branch_routes/schemas/config.schema.json").read_text())
        if source.name == "runtime-map.schema.json":
            props = value["properties"]["generator"]["properties"]
            props["algorithm"]["enum"].append(ALGORITHM)
            props["implementation"]["enum"].append(implementation)
        schemas[source.stem.split(".")[0]] = value
        (out / "schemas" / source.name).write_text(json.dumps(value, indent=2) + "\n")
    encoded = "extends RefCounted\n# Candidate-specific schema; old public/reference schemas remain unchanged.\n"
    for name in ("request", "config"):
        # GDScript literal shares this subset with JSON except booleans/null, supported verbatim.
        encoded += "const " + name.upper() + " = " + json.dumps(schemas[name], indent=2) + "\n"
    (addon / "schema_data.gd").write_text(encoded)
    (out / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Mapgen reward branch candidate"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
    (out / "tests").mkdir()
    for source in (ROOT / "branch_routes/tests").glob("*.gd"):
        shutil.copyfile(source, out / "tests" / source.name)
    shutil.copyfile(ROOT / "godot_runtime/tests/request.json", out / "tests/request.json")
    shutil.copyfile(ROOT / "branch_routes/profiles/stable-v4-reward-branches.json", out / "tests/config.json")
    shutil.copyfile(ROOT / "performance_revision/tests/regression.gd", out / "suite.gd")
    (out / "source-lock.json").write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(addon.glob("*.gd"))}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--out", type=Path, required=True)
    assemble(parser.parse_args().out)
