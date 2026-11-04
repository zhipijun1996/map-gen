"""Sequential paired standalone benchmarks; never overlap generation jobs."""
import argparse
import copy
import gzip
import hashlib
import json
import statistics
import subprocess
from pathlib import Path
from branch_routes.tools.setup import ROOT


def normalized(value):
    value=copy.deepcopy(value);value["metrics"].pop("generation_seconds",None);return value


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument("--old",type=Path,required=True);p.add_argument("--new",type=Path,required=True);p.add_argument("--godot",type=Path,required=True);p.add_argument("--out",type=Path,required=True);args=p.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    selected=json.loads((ROOT/"branch_routes/selection.json").read_text());records=[];counts={"old":0,"new":0}
    for label in ("old","new","new","old"):
        counts[label]+=1;name=f"native-{label}-{counts[label]}";project=args.old if label=="old" else args.new;path=args.out/(name+".json")
        with (args.out/(name+".log")).open("w") as log:
            run=subprocess.run([str(args.godot.resolve()),"--headless","--path",str(project),"--",str(path.resolve()),"cpu","varied" if label=="old" else "default"],stdout=log,stderr=subprocess.STDOUT,timeout=240)
        assert run.returncode==0 and "SCRIPT ERROR" not in (args.out/(name+".log")).read_text()
        report=json.loads(path.read_text())
        for row in report["records"]:
            if row["stage"]!="generate":continue
            seed=row["seed"]
            frozen=ROOT/"validation"/("runtime-iteration-20261104/varied-v3" if label=="old" else "reward-branches-20261104/"+selected["regression_run"])/(("validation-" if label=="old" else "seed-")+str(seed)+".json.gz")
            expected=json.loads(gzip.decompress(frozen.read_bytes()))["result"]
            assert normalized(row["result"])==normalized(expected),(name,seed)
            records.append(dict(run=name,label=label,seed=seed,wall_usec=row["wall_usec"],active_usec=row["advance_cpu_usec"],snapshot_usec=row["snapshot_usec"],serialize_usec=row["canonical_serialize_usec"],advance_distribution_usec=row["advance_distribution_usec"]))
        path.with_suffix(".json.gz").write_bytes(gzip.compress(path.read_bytes(),mtime=0));path.unlink()
    summary=dict(status="PASS",scope="dedicated sequential native standalone data benchmark; active=sum advance wall durations, not OS CPU; old/new/new/old; library reused per two seeds",engine_sha256=hashlib.sha256(args.godot.read_bytes()).hexdigest(),sources={label:{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (project/"addons/mapgen").glob("*.gd")} for label,project in (("old",args.old),("new",args.new))},records=records,medians={label:{str(seed):statistics.median(r["wall_usec"] for r in records if r["label"]==label and r["seed"]==seed)/1e6 for seed in (930001,930007)} for label in ("old","new")})
    (args.out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n");print(json.dumps(summary["medians"]),flush=True)


if __name__=="__main__":main()
