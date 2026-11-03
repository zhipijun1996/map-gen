import argparse,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--source',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
shutil.copytree(a.source,a.out/'addons/mapgen')
(a.out/'inputs').mkdir();up=ROOT/'performance_revision/upstream'
for n in ['conformance_request.json','gears_request_930007.json','generator_config.json']:shutil.copyfile(up/n,a.out/'inputs'/n)
shutil.copyfile(ROOT/'validation/runtime-reward-B/replay/inputs/failure/request.json',a.out/'inputs/failure_request.json')
shutil.copyfile(ROOT/'.cache/legacy-real-v2/modules.zip',a.out/'inputs/modules.zip')
shutil.copyfile(ROOT/'performance_revision/bench.gd',a.out/'bench.gd')
(a.out/'main.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://bench.gd" id="1"]\n[node name="DataBench" type="Node"]\nscript = ExtResource("1")\n')
(a.out/'project.godot').write_text('config_version=5\n[application]\nconfig/name="Mapgen data performance"\nrun/main_scene="res://main.tscn"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\nrenderer/rendering_method.mobile="gl_compatibility"\n')
(a.out/'export_presets.cfg').write_text('[preset.0]\nname="Web"\nplatform="Web"\nrunnable=true\nexport_filter="all_resources"\ninclude_filter="inputs/*.json,inputs/modules.zip"\nexport_path="build/index.html"\n[preset.0.options]\nvariant/thread_support=true\nvariant/extensions_support=false\n')
(a.out/'build').mkdir()
