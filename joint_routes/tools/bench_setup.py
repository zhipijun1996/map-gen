"""Create a standalone, explicit two-ability data host for native and Web."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from branch_routes.tools.setup import ROOT

def prepare(source,out,config):
    out.mkdir(parents=True,exist_ok=False)
    shutil.copytree(source/'addons',out/'addons')
    (out/'inputs').mkdir();(out/'build').mkdir()
    request=json.loads((ROOT/'runtime_iteration/upstream/controller-request.json').read_text())
    for seed,name in [(930001,'conformance_request.json'),(930007,'gears_request_930007.json')]:
        (out/'inputs'/name).write_text(json.dumps(dict(request,seed=seed),indent=2)+'\n')
    for name in ['generator_config.json','varied_config.json']:shutil.copyfile(config,out/'inputs'/name)
    shutil.copyfile(ROOT/'.cache/legacy-real-v2/modules.zip',out/'inputs/modules.zip')
    shutil.copyfile(ROOT/'validation/runtime-reward-B/replay/inputs/failure/request.json',out/'inputs/failure_request.json')
    shutil.copyfile(ROOT/'runtime_iteration/bench.gd',out/'bench.gd')
    (out/'main.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://bench.gd" id="1"]\n[node name="DataBench" type="Node"]\nscript = ExtResource("1")\n')
    (out/'project.godot').write_text('config_version=5\n[application]\nconfig/name="Two ability mapgen experiment"\nrun/main_scene="res://main.tscn"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\nrenderer/rendering_method.mobile="gl_compatibility"\n')
    (out/'export_presets.cfg').write_text('[preset.0]\nname="Web"\nplatform="Web"\nrunnable=true\nexport_filter="all_resources"\nexclude_filter="build/*,tests/*,suite.gd"\ninclude_filter="inputs/*.json,inputs/modules.zip"\nexport_path="build/index.html"\n[preset.0.options]\nvariant/thread_support=true\nvariant/extensions_support=false\n')
    (out/'source-lock.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((out/'addons/mapgen').glob('*.gd'))},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--config',type=Path,required=True);a=p.parse_args();prepare(a.source,a.out,a.config)
