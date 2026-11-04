"""Assemble isolated v5 experiments without changing the delivered 0.5.0."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from branch_routes.tools.setup import assemble as assemble_v4, ROOT

ALGORITHM = "stable-v5-joint-reward-plans"
IMPLEMENTATION = "mapgen/gdscript-experiment-0.6.0"


def assemble(out):
    assemble_v4(out)
    addon = out / "addons/mapgen"
    for source in (ROOT / "joint_routes/runtime").glob("*.gd"):
        shutil.copyfile(source, addon / source.name)
    schema = json.loads((ROOT / "branch_routes/schemas/config.schema.json").read_text())
    schema["properties"]["algorithm"] = {"const": ALGORITHM}
    schema["required"].append("planning")
    profile = json.loads((ROOT / "joint_routes/profiles/joint-v1.json").read_text())
    props = {k:{"type":"integer", "minimum":1} for k in profile["planning"]}
    schema["properties"]["planning"] = {"type":"object","additionalProperties":False,"required":list(props),"properties":props}
    identity = hashlib.sha256(b"".join(p.name.encode()+p.read_bytes() for p in sorted(addon.glob("*.gd")))+json.dumps(schema,sort_keys=True).encode()).hexdigest()[:12]
    implementation = IMPLEMENTATION+"+"+identity
    path = addon / "protocol.gd"
    path.write_text(path.read_text().replace(IMPLEMENTATION,implementation))
    path = addon / "derived_library.gd"
    lines=path.read_text().splitlines()
    lines=[f'const IMPLEMENTATION="{implementation}"' if line.startswith("const IMPLEMENTATION=") else line for line in lines]
    path.write_text("\n".join(lines)+"\n")
    request=json.loads((ROOT/"schemas/request.schema.json").read_text())
    (addon/"schema_data.gd").write_text("extends RefCounted\nconst REQUEST = "+json.dumps(request,indent=2)+"\nconst CONFIG = "+json.dumps(schema,indent=2)+"\n")
    (out/"schemas/config.schema.json").write_text(json.dumps(schema,indent=2)+"\n")
    path=out/"schemas/runtime-map.schema.json";value=json.loads(path.read_text());g=value["properties"]["generator"]["properties"];g["algorithm"]["enum"].append(ALGORITHM);g["implementation"]["enum"].append(implementation);path.write_text(json.dumps(value,indent=2)+"\n")
    (out/"tests/config.json").write_text(json.dumps(profile,indent=2)+"\n")
    for source in (ROOT/"joint_routes/tests").glob("*.gd"):shutil.copyfile(source,out/"tests"/source.name)
    (out/"source-lock.json").write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(addon.glob("*.gd"))},indent=2)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser(__doc__);p.add_argument("--out",type=Path,required=True);assemble(p.parse_args().out)
