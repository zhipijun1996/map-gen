"""Attach the existing standalone advance(1) benchmark to an assembled project."""
import argparse
import shutil
from pathlib import Path
from branch_routes.tools.setup import ROOT

parser=argparse.ArgumentParser(__doc__)
parser.add_argument("--project",type=Path,required=True)
args=parser.parse_args()
project=args.project
(project/"inputs").mkdir(exist_ok=True)
(project/"build").mkdir(exist_ok=True)
for name in ("conformance_request.json","gears_request_930007.json"):
    shutil.copyfile(ROOT/"performance_revision/upstream"/name,project/"inputs"/name)
shutil.copyfile(ROOT/"validation/runtime-reward-B/replay/inputs/failure/request.json",project/"inputs/failure_request.json")
shutil.copyfile(ROOT/".cache/legacy-real-v2/modules.zip",project/"inputs/modules.zip")
for name in ("generator_config.json","varied_config.json"):
    shutil.copyfile(ROOT/"branch_routes/profiles/stable-v4-reward-branches.json",project/"inputs"/name)
shutil.copyfile(ROOT/"runtime_iteration/bench.gd",project/"bench.gd")
(project/"main.tscn").write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://bench.gd" id="1"]\n[node name="Bench" type="Node"]\nscript = ExtResource("1")\n')
(project/"project.godot").write_text('config_version=5\n[application]\nconfig/name="Reward branch data benchmark"\nrun/main_scene="res://main.tscn"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\nrenderer/rendering_method.mobile="gl_compatibility"\n')
(project/"export_presets.cfg").write_text('[preset.0]\nname="Web"\nplatform="Web"\nrunnable=true\nexport_filter="all_resources"\nexclude_filter="build/*,suite.gd,tests/*"\ninclude_filter="inputs/*.json,inputs/modules.zip"\nexport_path="build/index.html"\n[preset.0.options]\nvariant/thread_support=true\nvariant/extensions_support=false\n')
