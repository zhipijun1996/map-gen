"""Build and independently verify the explicitly selected v4 candidate."""
import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from branch_routes.tools.setup import ROOT, ALGORITHM, assemble


def enc(value): return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
def sha(raw): return hashlib.sha256(raw).hexdigest()


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--godot",type=Path,required=True)
    args=p.parse_args()
    commit=subprocess.check_output(["git","rev-parse",args.source_commit],cwd=ROOT,text=True).strip()
    selection=json.loads((ROOT/"branch_routes/selection.json").read_text())
    # All package sources must already belong to the reviewable source commit.
    checked={}
    paths=subprocess.check_output(["git","ls-tree","-r","--name-only",commit,"--","branch_routes","godot_runtime/addons/mapgen","schemas","performance_revision/upstream","godot_runtime/tests/verify_bundle.gd","validation/reward-branches-20261104"],cwd=ROOT,text=True).splitlines()
    for rel in paths:
        path=ROOT/rel
        assert subprocess.check_output(["git","show",commit+":"+rel],cwd=ROOT)==path.read_bytes(),rel
        checked[rel]=sha(path.read_bytes())
    args.out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="mapgen-v4-build-") as temp:
        project=Path(temp)/"assembled"
        assemble(project)
        implementation=next(line.split('"')[1] for line in (project/"addons/mapgen/protocol.gd").read_text().splitlines() if line.startswith("const IMPLEMENTATION"))
        files={}
        for folder in ("addons","schemas","tests"):
            for path in (project/folder).rglob("*"):
                if path.is_file():files[path.relative_to(project).as_posix()]=path.read_bytes()
        files["project.godot"]=(project/"project.godot").read_bytes()
        for name in ("README.md","REPORT.md","HANDOFF.md","plan.json","selection.json"):
            files[name]=(ROOT/"branch_routes"/name).read_bytes()
        files["profiles/stable-v4-reward-branches.json"]=(ROOT/"branch_routes/profiles/stable-v4-reward-branches.json").read_bytes()
        verify=ROOT/"godot_runtime/tests/verify_bundle.gd"
        files["tests/verify_bundle.gd"]=verify.read_bytes()
        files["tests/dependencies/modules.zip"]=(ROOT/".cache/legacy-real-v2/modules.zip").read_bytes()
        for name in ("toolchain.json","godot_build.json"):
            files["dependencies/"+name]=(ROOT/"performance_revision/upstream"/name).read_bytes()
        samples=[]
        evidence=ROOT/"validation/reward-branches-20261104"
        for folder,case,label in ((selection["regression_run"],"seed-930001","four-abilities-930001"),(selection["regression_run"],"seed-930007","four-abilities-930007"),(selection["regression_run"],"failure","failure"),(selection["controller_run"],"seed-930001","controller-930001")):
            source=evidence/folder
            lock=json.loads((source/"source-lock.json").read_text())
            actual_lock={path.name:sha(path.read_bytes()) for path in (project/"addons/mapgen").glob("*.gd")}
            assert lock==actual_lock,(folder,"runtime source differs from tested source")
            prefix="samples/"+label
            result=json.loads(gzip.decompress((source/(case+".json.gz")).read_bytes()))["result"]
            for name in ("request.json","config.json"):files[prefix+"/"+name]=(source/"inputs"/case/name).read_bytes()
            files[prefix+"/result.json"]=enc(result)
            if result["map"] is not None:
                files[prefix+"/map.json"]=enc(result["map"])
                files[prefix+"/content_store.json"]=enc(result["content_store"])
                for ref,body in result["content_store"].items():
                    assert not Path(ref).is_absolute() and ".." not in Path(ref).parts
                    files[prefix+"/"+ref]=enc(body)
            samples.append(dict(id=label,request=prefix+"/request.json",config=prefix+"/config.json",result=prefix+"/result.json"))
        for path in (ROOT/"branch_routes/comparisons").iterdir():
            if path.is_file():files["comparisons/"+path.name]=path.read_bytes()
        for run in selection["evidence_runs"]:
            path=evidence/run/"summary.json"
            if path.exists():files["evidence/"+run+"/summary.json"]=path.read_bytes()
        files["source-lock.json"]=(project/"source-lock.json").read_bytes()
        manifest=dict(schema="mapgen/reference-package/v1",package=dict(version="0.5.0",algorithm=ALGORITHM,implementation=implementation),runtime_target="godot-standard-gdscript",readiness=dict(status="candidate",production_ready=False,whole_map_physics="NOT_RUN",host_integration="NOT_RUN",hard_frame_budget="NOT_GUARANTEED"),source=dict(commit=commit,baseline="65f3f151ad1de51de910922e44dc45192f2268fd",files=checked,assembly="branch_routes/tools/setup.py overlays frozen 0.4.2; parsed source cache rebind only, no source module changes"),protocol=dict(request="mapgen/generation-request/v1",config="mapgen/generator-config/v1",result="mapgen/generation-result/v1",map="mapgen/runtime-map/v2",config_compatibility="candidate-specific v1 schema and v4 algorithm; old v3 config rejected, never auto-converted"),module_package=dict(version="1.1.0",sha256="5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723",compatibility="exact SHA"),addon_files={n:sha(b) for n,b in files.items() if n.startswith("addons/")},samples=samples,files={n:sha(b) for n,b in sorted(files.items())})
        assert sha(files["tests/dependencies/modules.zip"])==manifest["module_package"]["sha256"]
        files["manifest.json"]=enc(manifest)
        name="mapgen-godot-candidate-0.5.0"
        dest=args.out/(name+".zip")
        with zipfile.ZipFile(dest,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for rel,raw in sorted(files.items()):
                info=zipfile.ZipInfo(name+"/"+rel,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;archive.writestr(info,raw,compresslevel=9)
        independent=Path(temp)/"verify"
        with zipfile.ZipFile(dest) as archive:archive.extractall(independent)
        package=independent/name
        run=subprocess.run([str(args.godot.resolve()),"--headless","--path",str(package),"--script","res://tests/verify_bundle.gd","--",str(package/"tests/dependencies/modules.zip")],cwd=temp,capture_output=True,text=True,timeout=300)
        raw=run.stdout+run.stderr;(args.out/"standalone.log").write_text(raw)
        assert run.returncode==0 and "SCRIPT ERROR" not in raw,raw[-2000:]
        verified=json.loads(next(line for line in reversed(raw.splitlines()) if line.startswith("{")))
        assert verified["status"]=="PASS"
        sample=samples[0]
        cli_out=Path(temp)/"cli-result.json"
        cli=subprocess.run([str(args.godot.resolve()),"--headless","--path",str(package),"--script","res://tests/generate.gd","--",str(package/"tests/dependencies/modules.zip"),str(package/sample["request"]),str(package/sample["config"]),str(cli_out)],cwd=temp,capture_output=True,text=True,timeout=120)
        (args.out/"standalone-cli.log").write_text(cli.stdout+cli.stderr)
        assert cli.returncode==0 and "SCRIPT ERROR" not in cli.stdout+cli.stderr
        cli_result=json.loads(cli_out.read_text());frozen=json.loads((package/sample["result"]).read_text())
        cli_result["metrics"].pop("generation_seconds",None);frozen["metrics"].pop("generation_seconds",None)
        assert cli_result==frozen
        receipt=dict(status="PASS",archive=dest.name,sha256=sha(dest.read_bytes()),source_commit=commit,implementation=implementation,addon_files=len(manifest["addon_files"]),bytes=dest.stat().st_size,independent_extract_verified=True,standalone_cli_replay=True,verify_checks=len(verified["checks"]),engine_sha256=sha(args.godot.read_bytes()),readiness="candidate")
        (args.out/"receipt.json").write_bytes(enc(receipt))
        (args.out/(dest.name+".sha256")).write_text(receipt["sha256"]+"  "+dest.name+"\n")
        print(json.dumps(receipt))


if __name__=="__main__":main()
