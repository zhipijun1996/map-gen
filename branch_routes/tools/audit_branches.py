"""Independently reconstruct branch witnesses from exported runtime-map/v2."""
from collections import deque


def inspect(result):
    if result["status"] != "PASS":
        assert result["map"] is None and result["content_store"] == {}
        return {"status":"NOT_APPLICABLE", "usable_map":False}
    data = result["map"]
    nodes = {n["id"]:n for n in data["graph"]["nodes"]}
    graph = {n:[] for n in nodes}
    for a,b in data["graph"]["edges"]:
        graph[a].append(b)
    named = {}
    for nid,n in nodes.items():
        if n["kind"].startswith("port_"):
            key = n["instance_id"] + "." + n["port_id"] + ":" + n["kind"].removeprefix("port_")
        elif n["kind"] == "reward":
            key = n["instance_id"] + ":reward:" + n["route_id"]
            if not n["target"]: key += ":" + n["reward_ids"][0]
        else:
            key = "START" if n["kind"] == "start" else "BOSS"
        named[key] = nid

    def check_named_path(path):
        for a,b in zip(path,path[1:]):
            assert a in named and b in named, (a,b)
            left,right = named[a],named[b]
            if right in graph[left]: continue
            # Solver's cheap ordinary Route graph omits intermediate ordinary
            # reward nodes. Export must realize that SAME module-local edge.
            iid = nodes[left]["instance_id"]
            assert iid == nodes[right]["instance_id"]
            queue = deque([left]); seen = {left}
            while queue:
                node = queue.popleft()
                for nxt in graph[node]:
                    if nxt not in seen and (nxt == right or nodes[nxt]["kind"] == "reward" and nodes[nxt]["instance_id"] == iid):
                        seen.add(nxt); queue.append(nxt)
            assert right in seen, (a,b)
    details = result["diagnostics"]["details"]
    core = set(details["reward_core_ids"])
    rank = details["reward_core_rank"]
    branches = details["reward_branches"]
    by_id = {i["id"]:i for i in data["instances"]}
    goal_instances = set(data["anchors"]["target_reward_instances"])
    assert len(branches) == data["inputs"]["config"]["goals"]["reward_target"]
    assert {b["reward_instance_id"] for b in branches} == goal_instances
    allocated = set()

    def walk(start, goals, allowed):
        queue = deque([start])
        parent = {start:None}
        while queue:
            node = queue.popleft()
            if node in goals:
                path = []
                while node is not None:
                    path.append(node)
                    node = parent[node]
                return path[::-1]
            for nxt in graph[node]:
                if nxt not in parent and (nodes[nxt]["instance_id"] in allowed or nxt in goals):
                    parent[nxt] = node
                    queue.append(nxt)
        return []

    boss = next(n for n,v in nodes.items() if v["kind"] == "boss")
    proofs = []
    for branch in branches:
        allowed = set(branch["instance_ids"])
        assert allowed and not allowed & core and not allowed & allocated
        allocated |= allowed
        assert allowed <= by_id.keys()
        reward_id = branch["reward_instance_id"]
        assert {i for i in allowed if by_id[i]["role"] == "target_reward"} == {reward_id}
        entry_id = branch["entry_instance_id"]
        assert entry_id in core
        entry = next(n for n,v in nodes.items() if v["kind"] == "port_depart" and v["instance_id"] == entry_id and v["port_id"] == branch["entry_port_id"])
        rewards = {n for n,v in nodes.items() if v["kind"] == "reward" and v["instance_id"] == reward_id and v["target"]}
        outward = walk(entry,rewards,allowed)
        assert outward, branch
        targets = {n for n,v in nodes.items() if v["kind"] == "port_arrive" and v["instance_id"] in core}
        if branch["kind"] == "forward_merge":
            targets = {n for n in targets if nodes[n]["instance_id"] != entry_id and rank.get(nodes[n]["instance_id"],-1)>rank[entry_id]}
        elif branch["kind"] == "core_merge":
            targets = {n for n in targets if nodes[n]["instance_id"] != entry_id}
        else:
            assert branch["kind"] in ("single_return","multi_return")
            targets = {n for n in targets if nodes[n]["instance_id"] == entry_id}
        onward = walk(outward[-1],targets,allowed)
        assert onward, branch
        assert walk(onward[-1],{boss},set(by_id)), branch
        # Separate exported-graph BFS may select another shortest path; verify
        # actual module participation against the producer's named witness too.
        participating = {n.split(".")[0].split(":")[0] for n in branch["outbound_path"] + branch["onward_path"]} & allowed
        assert participating == allowed
        check_named_path(branch["outbound_path"])
        check_named_path(branch["onward_path"])
        assert branch["kind"] != "single_return" or len(allowed) == 1
        assert branch["kind"] != "multi_return" or len(allowed) > 1
        if branch["kind"] in ("single_return","multi_return"):
            external = set()
            for connection in data["connections"]:
                a,b = connection["a"]["instance_id"],connection["b"]["instance_id"]
                if a in allowed and b not in allowed: external.add(b)
                if b in allowed and a not in allowed: external.add(a)
            assert external == {entry_id}, ("return branch must attach only to its root",external,branch)
        proofs.append(dict(kind=branch["kind"], instance_ids=branch["instance_ids"], reward_instance_id=reward_id, exported_outbound_path=outward, exported_onward_path=onward, scope="actual exported directed graph, core-boundary constrained; no physics or irreversibility proof"))
    return {"status":"PASS", "branches":proofs}
