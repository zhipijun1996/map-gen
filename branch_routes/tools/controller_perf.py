"""Separate two-ability measurements against BOTH old default and old varied."""
import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from branch_routes.tools.setup import ROOT
from branch_routes.tools.native_perf import normalized


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument("--old",type=Path,required=True);p.add_argument("--new",type=Path,required=True);p.add_argument("--godot",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);rows=[]
    request=json.loads((ROOT/"runtime_iteration/upstream/controller-request.json").read_text())
    with tempfile.TemporaryDirectory(prefix="mapgen-controller-perf-") as tmp:
        for label,source,config in (("old-default",a.old,ROOT/"profiles/stable-v3-reward-space.json"),("old-varied",a.old,ROOT/"profiles/stable-v3-varied-v1.json"),("new",a.new,ROOT/"branch_routes/profiles/stable-v4-reward-branches.json")):
            project=Path(tmp)/label;project.mkdir();shutil.copytree(source/"addons",project/"addons")
            for name in ("bench.gd","main.tscn","project.godot"):shutil.copyfile(source/name,project/name)
            (project/"inputs").mkdir()
            shutil.copyfile(ROOT/".cache/legacy-real-v2/modules.zip",project/"inputs/modules.zip")
            shutil.copyfile(config,project/"inputs/generator_config.json")
            for seed,name in ((930001,"conformance_request.json"),(930007,"gears_request_930007.json")):
                req=dict(request,seed=seed);(project/"inputs"/name).write_text(json.dumps(req,indent=2)+"\n")
            output=a.out/(label+".json")
            with (a.out/(label+".log")).open("w") as log:
                run=subprocess.run([str(a.godot.resolve()),"--headless","--path",str(project),"--",str(output.resolve()),"cpu","default"],stdout=log,stderr=subprocess.STDOUT,timeout=240)
            assert run.returncode==0 and "SCRIPT ERROR" not in (a.out/(label+".log")).read_text()
            report=json.loads(output.read_text())
            for row in report["records"]:
                if row["stage"]!="generate":continue
                result=row["result"]
                if label=="new":
                    expected=json.loads(gzip.decompress((ROOT/"validation/reward-branches-20261104/controller8"/("seed-"+str(row["seed"])+".json.gz")).read_bytes()))["result"]
                    assert normalized(result)==normalized(expected)
                elif row["seed"]==930001:
                    expected=json.loads(gzip.decompress((ROOT/"validation/runtime-iteration-20261104/live-controller/042"/("default.json.gz" if label=="old-default" else "varied.json.gz")).read_bytes()))["result"]
                    assert normalized(result)==normalized(expected)
                rows.append(dict(label=label,seed=row["seed"],status=result["status"],wall_seconds=row["wall_usec"]/1e6,active_seconds=row["advance_cpu_usec"]/1e6,expansions=result["metrics"].get("expansions")))
            output.with_suffix(".json.gz").write_bytes(gzip.compress(output.read_bytes(),mtime=0));output.unlink()
    summary=dict(status="PASS",scope="dedicated sequential native controller jump/shot_recoil, clearance 12.0/18.0; n=1 per label/seed, no statistical speed guarantee",engine_sha256=hashlib.sha256(a.godot.read_bytes()).hexdigest(),rows=rows)
    (a.out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n");print(json.dumps(rows),flush=True)


if __name__=="__main__":main()
