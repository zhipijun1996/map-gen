"""Independent actual Godot/Web data harness; no game rendering or host types."""
import argparse,shutil,json
from pathlib import Path
from role_growth.tools.setup import assemble,ROOT
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();assemble(a.out,ROOT/'role_growth/profiles/default.json')
shutil.copyfile(ROOT/'runtime_iteration/bench.gd',a.out/'bench.gd');inp=a.out/'inputs';inp.mkdir()
req=json.load(open(ROOT/'runtime_iteration/upstream/controller-request.json'))
for name,seed in [('conformance_request.json',930001),('gears_request_930007.json',930007)]:
 r=dict(req);r['seed']=seed;(inp/name).write_text(json.dumps(r,indent=2)+'\n')
shutil.copyfile(ROOT/'validation/runtime-reward-B/replay/inputs/failure/request.json',inp/'failure_request.json')
for name in ['generator_config.json','varied_config.json']:shutil.copyfile(ROOT/'role_growth/profiles/default.json',inp/name)
shutil.copyfile(ROOT/'.cache/legacy-real-v2/modules.zip',inp/'modules.zip')
(a.out/'main.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://bench.gd" id="1"]\n[node name="DataBench" type="Node"]\nscript = ExtResource("1")\n')
p=a.out/'project.godot';p.write_text(p.read_text().replace('[application]','[application]\nrun/main_scene="res://main.tscn"'))
(a.out/'export_presets.cfg').write_text('[preset.0]\nname="Web"\nplatform="Web"\nrunnable=true\nexport_filter="all_resources"\nexclude_filter="build/*,tests/*,suite.gd"\ninclude_filter="inputs/*.json,inputs/modules.zip"\nexport_path="build/index.html"\n[preset.0.options]\nvariant/thread_support=true\nvariant/extensions_support=false\n');(a.out/'build').mkdir()
