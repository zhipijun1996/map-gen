"""Audit actual Web outputs against frozen native results and branch paths."""
import copy
import gzip
import json
from pathlib import Path
from branch_routes.tools.native_perf import normalized
from branch_routes.tools.audit_branches import inspect
from branch_routes.tools.setup import ROOT


def main():
    base=ROOT/"validation/reward-branches-20261104"
    selection=json.loads((ROOT/"branch_routes/selection.json").read_text())
    checks={};records=[]
    for folder,label in (("web-baseline-final","old"),("web-final","new"),("web-cancel","cancel"),("web-failure","failure")):
        summary=json.loads((base/folder/"summary.json").read_text())
        report=json.loads(gzip.decompress((base/folder/"report.json.gz").read_bytes()))
        checks[folder+":browser_errors_empty"]=not summary["errors"]
        for row in report["records"]:
            if row["stage"]!="generate":
                checks[folder+":preload"]=row["status"]=="PASS"
                continue
            result=row["result"]
            record=dict(folder=folder,seed=row["seed"],status=result["status"],wall_seconds=row["wall_usec"]/1e6,active_seconds=row["advance_cpu_usec"]/1e6,host_and_yield_seconds=row["host_and_yield_usec"]/1e6,snapshot_usec=row["snapshot_usec"],canonical_serialize_usec=row["canonical_serialize_usec"],advance_distribution_usec=row["advance_distribution_usec"],cancel=row["cancel"])
            if label in ("old","new","failure"):
                if label=="old":reference=ROOT/"validation/runtime-iteration-20261104/varied-v3"/("validation-"+str(row["seed"])+".json.gz")
                else:reference=base/selection["regression_run"]/(("failure" if label=="failure" else "seed-"+str(row["seed"]))+".json.gz")
                frozen=json.loads(gzip.decompress(reference.read_bytes()))["result"]
                checks[folder+":"+str(row["seed"])+":full_native_equal"]=normalized(result)==normalized(frozen)
                if label=="new":record["branch_audit"]=inspect(result)
                if label=="failure":checks[folder+":failure_empty"]=result["status"]=="SEARCH_EXHAUSTED" and result["map"] is None and result["content_store"]=={}
            else:
                cancel=row["cancel"]
                checks[folder+":actual_input"]=cancel["trusted"] and cancel["finished_ms"]>=cancel["handler_ms"]>=cancel["intent_ms"]
                checks[folder+":cancel_empty"]=result["status"]=="CANCELLED" and result["map"] is None and result["content_store"]=={}
                checks[folder+":correct_phase"]=result["diagnostics"]["error"]["phase"]=="reward_branches"
            records.append(record)
    report=dict(status="PASS" if all(checks.values()) else "FAIL",checks=checks,records=records,scope="actual threaded Web/Compatibility/software Chromium; DOM trusted input timestamp to completed cancelled result; standalone data host, no game or physics")
    (base/"web-audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(dict(status=report["status"],checks=len(checks),records=[{k:v for k,v in r.items() if k not in ("branch_audit","advance_distribution_usec")} for r in records]),ensure_ascii=False,indent=2))
    assert report["status"]=="PASS"


if __name__=="__main__":main()
