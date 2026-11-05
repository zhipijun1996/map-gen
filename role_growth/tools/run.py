"""Freeze inputs, run actual GDScript jobs, retain failures, audit original data."""
import argparse
import copy
import gzip
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "runtime_packages/tools"))
from mapgen import ModuleLibrary
from validity import inspect_result
from branch_routes.tools.audit_branches import inspect as inspect_branches


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "role_growth/profiles/default.json")
    parser.add_argument("--controller", action="store_true")
    parser.add_argument("--expected-status",choices=["PASS","BUDGET_EXHAUSTED"],default="PASS")
    parser.add_argument("--failure", action="store_true")
    parser.add_argument("--contract", action="store_true")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--baseline-failure", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    request_path = ROOT / ("runtime_iteration/upstream/controller-request.json" if args.controller else "godot_runtime/tests/request.json")
    template = json.loads(request_path.read_text())
    cases = []
    for seed in args.seeds.split(","):
        if not seed: continue
        req = copy.deepcopy(template)
        req["seed"] = int(seed)
        cases.append(dict(id="seed-" + seed, request_data=req, batch=1))
    if args.failure:
        cases.append(dict(id="failure", request_data=json.loads((ROOT / "validation/runtime-reward-B/replay/inputs/failure/request.json").read_text()), batch=1))
    if args.contract:
        assert cases
        for batch in (17, 128, 4096):
            cases.append(dict(id=f"batch-{batch}", request_data=copy.deepcopy(cases[0]["request_data"]), batch=batch))
        for phase in ("transit_catalog", "motif_catalog", "growth", "joint_merge", "demand_core_routes", "structure_domains", "reward_branches", "final_audit", "export"):
            cases.append(dict(id="cancel-" + phase, request_data=copy.deepcopy(cases[0]["request_data"]), batch=1, cancel_phase=phase, cancel_delay_usec=1))
    for case in cases:
        folder = args.out / "inputs" / case["id"]
        folder.mkdir(parents=True)
        (folder / "request.json").write_text(json.dumps(case.pop("request_data"), indent=2) + "\n")
        (folder / "config.json").write_bytes(args.config.read_bytes())
        case.update(request=str((folder / "request.json").resolve()), config=str((folder / "config.json").resolve()))
    (args.out / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
    lock = json.loads((args.project / "source-lock.json").read_text())
    protocol=(args.project/"addons/mapgen/protocol.gd").read_text()
    expected_impl=re.search(r'const IMPLEMENTATION := "([^"]+)"',protocol).group(1)
    expected_algorithm=re.search(r'const ALGORITHM := "([^"]+)"',protocol).group(1)
    (args.out / "source-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    snapshot = args.out / "runtime-source"
    snapshot.mkdir()
    for name in lock:
        if name == "derived_library.gd": continue
        source = args.project / "addons/mapgen" / name
        if source.exists():
            (snapshot / (name + ".gz")).write_bytes(gzip.compress(source.read_bytes(), mtime=0))
    module = ROOT / ".cache/legacy-real-v2/modules.zip"
    compile_result = subprocess.run([str(args.godot.resolve()), "--headless", "--path", str(args.project), "--check-only", "--script", "res://suite.gd"], capture_output=True, text=True, timeout=30)
    (args.out / "compile.log").write_text(compile_result.stdout + compile_result.stderr)
    with (args.out / "godot.log").open("w") as log:
        if compile_result.returncode != 0 or "SCRIPT ERROR" in compile_result.stdout + compile_result.stderr:
            log.write(compile_result.stdout + compile_result.stderr)
            run = compile_result
        else:
            run = subprocess.run([str(args.godot.resolve()), "--headless", "--quit-after", "1", "--path", str(args.project), "--script", "res://suite.gd", "--", str(module), str(args.out.resolve()), str((args.out / "cases.json").resolve())], stdout=log, stderr=subprocess.STDOUT, timeout=3600)
    library = ModuleLibrary.from_zip(module, expected_sha256="5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723")
    rows = []
    primary = None
    for case in cases:
        path = args.out / (case["id"] + ".json")
        if not path.exists():
            rows.append(dict(case=case["id"], status="MISSING_RESULT", checks={"produced_result":False}))
            continue
        record = json.loads(path.read_text())
        actual = record["result"]
        checks = {"expected_status":actual["status"] == ("CANCELLED" if case["id"].startswith("cancel-") else "SEARCH_EXHAUSTED" if case["id"] == "failure" else args.expected_status), "failure_empty":actual["status"] == "PASS" or actual["map"] is None and actual["content_store"] == {}}
        if case["id"]=="failure":checks["expected_status"]=actual["status"] in ["SEARCH_EXHAUSTED","BUDGET_EXHAUSTED"]
        audit = None
        branch_audit = None
        if actual["status"] == "PASS":
            # Reuse independent source/geometry/graph/all-reward auditor on an
            # identity-projected copy. Never alter source actual or old oracle.
            projected = copy.deepcopy(actual)
            projected["map"]["generator"]["implementation"] = "mapgen/gdscript-candidate-0.4.0"
            projected["map"]["inputs"]["config"].pop("diversity", None)
            projected["map"]["inputs"]["config"].pop("planning", None)
            projected["map"]["inputs"]["config"].pop("topology", None)
            projected["map"]["inputs"]["config"].pop("construction", None)
            projected["map"]["inputs"]["config"].pop("growth_roles", None)
            projected["map"]["inputs"]["config"]["algorithm"] = "stable-v3-reward-space"
            try:
                audit = inspect_result(projected, library)
                checks["independent_source_graph_all_rewards"] = audit["status"] == "PASS"
            except Exception as error:
                audit = {"status":"FAIL", "error":repr(error)}
                checks["independent_source_graph_all_rewards"] = False
            checks["identity"] = actual["map"]["generator"]["implementation"]==expected_impl and actual["map"]["generator"]["algorithm"]==expected_algorithm
            checks["snapshot_inputs"] = actual["map"]["inputs"] == dict(request=json.loads(Path(case["request"]).read_text()), config=json.loads(Path(case["config"]).read_text()))
            try:
                branch_audit = inspect_branches(actual)
                checks["exported_branch_witnesses"] = branch_audit["status"] == "PASS"
                from collections import Counter
                details=actual["diagnostics"]["details"]
                checks["planned_branch_modes"]=Counter(b["kind"] for b in details["reward_branches"])==Counter(details["structure_plan"]["reward_modes"])
                checks["growth_target"]=details["growth_target_reached"]

            except Exception as error:
                branch_audit = {"status":"FAIL", "error":repr(error)}
                checks["exported_branch_witnesses"] = False
        if actual["status"]=="PASS":
            from route_construction.tools.audit import inspect as inspect_structure
            try:
                structural=inspect_structure(actual)
                checks["structure_proof"]=structural["status"]=="PASS"
            except Exception as error:
                checks["structure_proof"]=False
                audit["structure_error"]=repr(error)
        normalized = copy.deepcopy(actual)
        normalized["metrics"].pop("generation_seconds", None)
        if primary is None: primary = normalized
        if case["id"].startswith("batch-"): checks["batch_equal"] = normalized == primary
        if args.baseline and not case["id"].startswith(("batch-","cancel-")):
            baseline_path=args.baseline_failure if case["id"]=="failure" and args.baseline_failure else args.baseline/path.with_suffix(".json.gz").name
            previous=json.loads(gzip.decompress(baseline_path.read_bytes()))["result"]
            def behavior(value):
                value=copy.deepcopy(value);value['metrics'].pop('generation_seconds',None);value.pop('request_fingerprint');value['diagnostics'].pop('implementation',None)
                if value['map']:
                    value['map'].pop('map_id');value['map']['generator'].pop('implementation');value['map']['generator'].pop('request_fingerprint')
                return value
            checks['complete_baseline_behavior']=behavior(previous)==behavior(actual)
            checks['expected_status']=actual['status']==previous['status']
        rows.append(dict(case=case["id"], status=actual["status"], checks=checks, metrics=actual["metrics"], profile=record["profile"], cancel=record["cancel"], audit=audit, branch_audit=branch_audit))
        path.with_suffix(".json.gz").write_bytes(gzip.compress(path.read_bytes(), mtime=0))
        path.unlink()
    errors = "SCRIPT ERROR" in (args.out / "godot.log").read_text()
    summary = dict(status="PASS" if run.returncode == 0 and not errors and all(all(r["checks"].values()) for r in rows) else "FAIL", engine_sha256=hashlib.sha256(args.godot.read_bytes()).hexdigest(), source_sha256=lock, rows=rows, audit_scope="Independent static source/graph/seal/all-reward audit, identity-projected copy; no physics", returncode=run.returncode)
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(summary["status"], [(r["case"],r["status"]) for r in rows], flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
