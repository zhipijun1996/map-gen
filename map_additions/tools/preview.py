"""Build a standalone review harness; frozen map input, live GDScript additions."""
import argparse,json,shutil
from pathlib import Path
from map_additions.tools.setup import assemble,ROOT
from route_construction.tools.report import source,read
p=argparse.ArgumentParser(__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assemble(a.out);(a.out/'inputs').mkdir()
for algo in ['v5','v6returns','v6merge','v7']:(a.out/'inputs'/(algo+'.json')).write_text(json.dumps(read(source(algo,930001)),ensure_ascii=False)+'\n')
shutil.copyfile(ROOT/'map_additions/profiles/default.json',a.out/'inputs/config.json')
(a.out/'main.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://tests/preview.gd" id="1"]\n[node name="Preview" type="Node2D"]\nscript=ExtResource("1")\n')
p=a.out/'project.godot';p.write_text(p.read_text().replace('config/name=', 'run/main_scene="res://main.tscn"\nconfig/name=')+'[display]\nwindow/size/viewport_width=1300\nwindow/size/viewport_height=850\n')
(a.out/'export_presets.cfg').write_text('[preset.0]\nname="Web"\nplatform="Web"\nrunnable=true\nexport_filter="all_resources"\nexclude_filter="build/*"\ninclude_filter="inputs/*.json"\nexport_path="build/index.html"\n[preset.0.options]\nvariant/thread_support=true\nvariant/extensions_support=false\n')
(a.out/'build').mkdir()
