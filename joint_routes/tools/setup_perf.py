"""Backport only proven endpoint/distance indexes to the immutable 0.5 baseline."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from branch_routes.tools.setup import assemble as baseline, ROOT

def assemble(out):
    baseline(out)
    addon=out/"addons/mapgen"
    shutil.copyfile(ROOT/"joint_routes/performance/reward_branch_planner.gd",addon/"reward_branch_planner.gd")
    identity=hashlib.sha256(b"".join(p.name.encode()+p.read_bytes() for p in sorted(addon.glob("*.gd")))).hexdigest()[:12]
    implementation="mapgen/gdscript-candidate-0.5.1+"+identity
    path=addon/"protocol.gd";path.write_text(re.sub(r'const IMPLEMENTATION := "[^"]+"',f'const IMPLEMENTATION := "{implementation}"',path.read_text()))
    path=addon/"derived_library.gd";path.write_text(re.sub(r'const IMPLEMENTATION="[^"]+"',f'const IMPLEMENTATION="{implementation}"',path.read_text()))
    path=out/"schemas/runtime-map.schema.json";s=json.loads(path.read_text());s["properties"]["generator"]["properties"]["implementation"]["enum"].append(implementation);path.write_text(json.dumps(s,indent=2)+"\n")
    (out/"source-lock.json").write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(addon.glob("*.gd"))},indent=2)+"\n")

if __name__=="__main__":
    p=argparse.ArgumentParser(__doc__);p.add_argument("--out",type=Path,required=True);assemble(p.parse_args().out)
