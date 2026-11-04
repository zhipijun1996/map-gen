"""Count every catalog source module in pre-existing, explicitly fixed cohorts.

Run from repository root; no generation or selection of successful seeds occurs.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import html
import json
from pathlib import Path

from mapgen import ModuleLibrary

SHA = "5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723"
ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "validation/runtime-iteration-20261104"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(roles):
    if any(v.get("bound_terminal") for v in roles.values()):
        return "fixed_terminal"
    if any(v["passing_subsets"] for v in roles.values()):
        return "locally_feasible"
    if any(v["checked_subsets"] for v in roles.values()):
        return "all_local_subsets_rejected"
    return "no_candidate_route"


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--modules", type=Path, required=True)
    parser.add_argument("--census", type=Path, required=True)
    args = parser.parse_args()
    entries = ModuleLibrary.from_zip(args.modules, expected_sha256=SHA).read("catalog.json")["modules"]
    catalog = {e["id"]: e for e in entries}
    census = json.loads(args.census.read_text())
    assert census["module_sha256"] == SHA
    contexts = census["contexts"]
    for ctx in contexts.values():
        assert set(ctx["modules"]) == set(catalog)
    cases40 = [f"calibration-{s}" for s in range(271028, 271048)] + [f"validation-{s}" for s in range(930001, 930021)]
    cases20 = [f"unseen-{s}" for s in range(930021, 930041)]
    sources = {
        "default40": (BASE / "default", cases40),
        "varied40": (BASE / "varied-v3", cases40),
        "default20": (BASE / "unseen-baseline", cases20),
        "varied20": (BASE / "unseen-varied", cases20),
    }
    cohorts = {}
    provenance = []
    for name, (folder, cases) in sources.items():
        maps = []
        for case in cases:
            path = folder / (case + ".json.gz")
            result = json.loads(gzip.decompress(path.read_bytes()))["result"]
            assert result["status"] == "PASS", (name, case, result["status"])
            assert result["map"] is not None
            maps.append(result["map"]["instances"])
            provenance.append(dict(cohort=name, case=case, path=str(path.relative_to(ROOT)), sha256=digest(path)))
        cohorts[name] = maps
    for profile in ("default", "varied"):
        cohorts[profile + "60"] = cohorts[profile + "40"] + cohorts[profile + "20"]
    rows = []
    for mid, entry in sorted(catalog.items()):
        row = dict(module_id=mid, title=entry["title"], region=entry["region"], ports=len(entry["ports"]), routes=len(entry["routes"]), reward_sites=len(entry["reward_sites"]))
        row["regression_eligibility"] = classify(contexts["regression_four_abilities"]["modules"][mid])
        row["controller_eligibility"] = classify(contexts["controller_two_abilities"]["modules"][mid])
        for name, maps in cohorts.items():
            instances = [i for items in maps for i in items if i["module_id"] == mid]
            role_counts = collections.Counter(i["role"] for i in instances)
            row[name + "_instances"] = len(instances)
            row[name + "_seed_coverage"] = sum(any(i["module_id"] == mid for i in items) for items in maps)
            row[name + "_coverage_percent"] = round(row[name + "_seed_coverage"] / len(maps) * 100, 3)
            row[name + "_placement_percent"] = round(len(instances) / sum(len(m) for m in maps) * 100, 3)
            row[name + "_mirrored"] = sum(i["transform"]["mirror_x"] for i in instances)
            for role in ("start", "boss", "traversal", "target_reward"):
                row[name + "_" + role] = role_counts[role]
            assert sum(role_counts.values()) == sum(row[name + "_" + role] for role in ("start", "boss", "traversal", "target_reward"))
        rows.append(row)
    summary = {}
    for name, maps in cohorts.items():
        assert all(i["module_id"] in catalog for items in maps for i in items)
        assert sum(r[name + "_instances"] for r in rows) == sum(len(m) for m in maps)
        assert all(0 <= r[name + "_seed_coverage"] <= len(maps) for r in rows)
        zero = [r for r in rows if not r[name + "_instances"]]
        ordinary = sum(r[name + "_traversal"] for r in rows)
        top5 = sorted((r[name + "_traversal"] for r in rows), reverse=True)[:5]
        summary[name] = dict(seeds=len(maps), instances=sum(map(len, maps)), modules_used=len(rows)-len(zero), zero_use=len(zero), zero_use_eligibility=dict(collections.Counter(r["regression_eligibility"] for r in zero)), ordinary_instances=ordinary, top5_ordinary_share=round(sum(top5)/ordinary, 6))
    out = ROOT / "runtime_iteration/module_usage"
    out.mkdir(exist_ok=True)
    (out / "local-census.json").write_bytes(args.census.read_bytes())
    constraints = {e["id"]: [{"id":r["id"], "from":r["from"], "to":r["to"], "availableAbilities":r["validation"]["availableAbilities"], "testNeighborFixtures":r["validation"].get("testNeighborFixtures", [])} for r in e["routes"]] for e in entries}
    implementation = {str(p.relative_to(ROOT)): digest(p) for p in sorted((ROOT / "godot_runtime/addons/mapgen").glob("*.gd"))}
    payload = dict(module_version="1.1.0", module_sha256=SHA, algorithm="stable-v3-reward-space", implementation_files=implementation, route_constraints=constraints, scope="Source IDs merged across mirrors and traversal/reward aliases; all 115 modules retained", denominator="40 known regression seeds + 20 predeclared extra seeds; default40 from 0.4.2, default20 from 0.4.1, varied60 from 0.4.2 varied-v1. Only four-ability request cohort counted; controller two-ability context is local eligibility only.", census_sha256=digest(args.census), summary=summary, sources=provenance, modules=rows)
    (out / "usage.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    with (out / "usage.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    columns = ["module_id", "title", "ports", "routes", "regression_eligibility", "controller_eligibility"]
    for profile in ("default60", "varied60"):
        columns += [profile + "_instances", profile + "_seed_coverage", profile + "_coverage_percent", profile + "_traversal", profile + "_target_reward"]
    head = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>115 个模块使用频率</title><style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse}td,th{padding:7px;border:1px solid #ddd;text-align:left}th{position:sticky;top:0;background:#eee;cursor:pointer}tr.zero{background:#fff0df}input,select{padding:8px;margin:8px}td:first-child{max-width:360px;overflow-wrap:anywhere}</style><h1>115 个模块使用频率</h1><p>同一批60 seed。default40=0.4.2默认、default20=0.4.1默认；varied60=0.4.2可选repeat=8。实例次数与出现地图数分别统计，镜像合并，起点/Boss为固定绑定。橙色=新配置60图零使用。</p><p>四能力回归并非主游戏两能力频率。locally_feasible仅证明存在局部Route/封口组合，不代表真实全图可放置或物理认证。</p><input id="q" placeholder="搜索名称或ID"><select id="filter"><option value="all">全部115模块</option><option value="zero">新配置零使用</option><option value="rare">新配置出现≤3张地图</option></select><span id="count"></span><table><thead><tr>"""
    table = head + "".join("<th>" + html.escape(c) + "</th>" for c in columns) + "</tr></thead><tbody></tbody></table>"
    # Source strings are escaped before inclusion in a script element.
    encoded = json.dumps(rows, ensure_ascii=False).replace("<", "\\u003c")
    table += "<script>const data=" + encoded + ";const cols=" + json.dumps(columns) + ";"
    table += """let key='varied60_instances',dir=-1;const q=document.querySelector('#q'),f=document.querySelector('#filter'),body=document.querySelector('tbody');function draw(){const rows=data.filter(r=>(r.module_id+' '+r.title).toLowerCase().includes(q.value.toLowerCase())&&(f.value==='all'||(f.value==='zero'?r.varied60_instances===0:r.varied60_seed_coverage<=3))).sort((a,b)=>dir*(typeof a[key]==='number'?a[key]-b[key]:String(a[key]).localeCompare(String(b[key]))));body.replaceChildren();for(const r of rows){const tr=document.createElement('tr');if(!r.varied60_instances)tr.className='zero';for(const c of cols){const td=document.createElement('td');td.textContent=r[c];tr.append(td)}body.append(tr)}document.querySelector('#count').textContent=rows.length+' modules'}document.querySelectorAll('th').forEach((th,i)=>th.onclick=()=>{dir=key===cols[i]?-dir:-1;key=cols[i];draw()});q.oninput=draw;f.onchange=draw;draw();</script>"""
    (out / "index.html").write_text(table)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
