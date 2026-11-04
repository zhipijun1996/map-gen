"""Compare all fixed seeds, including failures, against frozen 0.4.2 varied-v1."""
import collections
import csv
import gzip
import json
from pathlib import Path

from mapgen import ModuleLibrary
from runtime_iteration.tools.metrics import aggregate, stats
from runtime_iteration.tools.module_classes import build

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/reward-branches-20261104"


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()))["result"]


def compact(result):
    if result["status"] != "PASS": return {"status":result["status"]}
    data = result["map"]
    return dict(status="PASS", bounds=data["bounds_blocks"], instances=[dict(id=i["id"],module=i["module_id"],origin=i["origin_blocks"],size=i["size_blocks"],role=i["role"],mirror=i["transform"]["mirror_x"],seals=[s["rect_pixels"] for s in i["seals"]]) for i in data["instances"]], branches=result["diagnostics"].get("details",{}).get("reward_branches",[]))


def main():
    plan = json.loads((ROOT / "branch_routes/plan.json").read_text())
    selection = json.loads((ROOT / "branch_routes/selection.json").read_text())
    library = ModuleLibrary.from_zip(ROOT / ".cache/legacy-real-v2/modules.zip",expected_sha256="5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723")
    classes = build(library)
    maps = []
    old_stats, new_stats = [], []
    occurrences = {k:collections.Counter() for k in ("old","new")}
    coverage = {k:collections.Counter() for k in ("old","new")}
    roles = {k:collections.defaultdict(collections.Counter) for k in ("old","new")}
    kinds = collections.Counter()
    branch_lengths = collections.Counter()
    rows = []
    for seed in plan["regression"] + plan["extra_existing_seeds"]:
        case = ("calibration-" if seed<900000 else "validation-") + str(seed)
        extra = seed in plan["extra_existing_seeds"]
        old_path = ROOT / "validation/runtime-iteration-20261104" / ("unseen-varied" if extra else "varied-v3") / (("unseen-" + str(seed) if extra else case) + ".json.gz")
        new_path = EVIDENCE / selection["extra_run" if extra else "regression_run"] / ("seed-"+str(seed)+".json.gz")
        old, new = read(old_path), read(new_path)
        sa,sb = stats(old,classes),stats(new,classes)
        old_stats.append(sa);new_stats.append(sb)
        row = dict(seed=seed,cohort="extra20" if extra else "regression40",old_status=old["status"],new_status=new["status"],old_seconds=old["metrics"]["generation_seconds"],new_seconds=new["metrics"]["generation_seconds"],old_expansions=old["metrics"].get("expansions"),new_expansions=new["metrics"].get("expansions"))
        for label,result in (("old",old),("new",new)):
            if result["status"] != "PASS": continue
            instances = result["map"]["instances"]
            occurrences[label].update(i["module_id"] for i in instances)
            coverage[label].update({i["module_id"] for i in instances})
            for i in instances: roles[label][i["module_id"]][i["role"]]+=1
        if new["status"] == "PASS":
            branches = new["diagnostics"]["details"]["reward_branches"]
            kinds.update(b["kind"] for b in branches)
            branch_lengths.update(len(b["instance_ids"]) for b in branches)
            allocated = {iid for b in branches for iid in b["instance_ids"]}
            core = [i for i in new["map"]["instances"] if i["id"] not in allocated and i["role"]=="traversal"]
            row.update(new_core_ordinary=len(core),new_core_unique=len({i["module_id"] for i in core}),branch_kinds=dict(collections.Counter(b["kind"] for b in branches)))
        rows.append(row)
        maps.append(dict(seed=seed,old=compact(old),new=compact(new),old_stats={k:v for k,v in sa.items() if k not in ("mask","modules","pairs","signature")},new_stats={k:v for k,v in sb.items() if k not in ("mask","modules","pairs","signature")}))
    summary = dict(status="PASS" if all(r["new_status"]=="PASS" for r in rows) else "FAIL",seeds=len(rows),baseline="0.4.2 varied-v1 (repeat=8), not 0.4.1 default",old=aggregate(old_stats),new=aggregate(new_stats),reward_branches=dict(kinds),branch_module_counts=dict(branch_lengths),rows=rows,scope="all 40 regression + 20 existing extra seeds; all outcomes retained; pure data, no physics")
    module_rows = []
    for entry in library.read("catalog.json")["modules"]:
        mid = entry["id"]
        module_rows.append(dict(module_id=mid,title=entry["title"],ports=len(entry["ports"]),old_instances=occurrences["old"][mid],new_instances=occurrences["new"][mid],old_seed_coverage=coverage["old"][mid],new_seed_coverage=coverage["new"][mid],old_traversal=roles["old"][mid]["traversal"],new_traversal=roles["new"][mid]["traversal"],old_target_reward=roles["old"][mid]["target_reward"],new_target_reward=roles["new"][mid]["target_reward"]))
    summary["modules_used"] = {k:len(v) for k,v in occurrences.items()}
    summary["top5_ordinary_share"] = {k:sum(sorted((v["traversal"] for v in values.values()),reverse=True)[:5])/sum(v["traversal"] for v in values.values()) for k,values in roles.items()}
    out = ROOT / "branch_routes/comparisons"
    out.mkdir(exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    with (out / "module-usage.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(module_rows[0]));writer.writeheader();writer.writerows(module_rows)
    template = (ROOT / "branch_routes/tools/view.html").read_text()
    encoded = json.dumps(dict(maps=maps,summary=summary),ensure_ascii=False,separators=(",",":")).replace("<","\\u003c")
    (out / "index.html").write_text(template.replace("__DATA__",encoded))
    print(json.dumps({k:v for k,v in summary.items() if k!="rows"},indent=2,ensure_ascii=False))


if __name__ == "__main__": main()
