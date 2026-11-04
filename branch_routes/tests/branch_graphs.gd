extends SceneTree
const PLANNER=preload("res://addons/mapgen/reward_branch_planner.gd")
class Fake extends RefCounted:
	var config: Dictionary={"diversity":{}}
	var reward_core: Dictionary={"A":true,"B":true}
	var reward_core_rank: Dictionary={"A":0,"B":10}
	var items: Array=[]
	var templates: Dictionary={}
	var g: Dictionary={}
	var cancelled:=false
	func checkpoint():return not cancelled
	func graph(_trial):return [g,[["Q","Q:reward:r"]],{}]
	func reverse_reachable(_graph,target):
		var reverse: Dictionary={}
		for a in g:
			for b in g[a]:
				if not reverse.has(b):reverse[b]=[]
				reverse[b].append(a)
		var queue: Array=[target];var seen: Dictionary={target:true}
		for n in queue:
			for m in reverse.get(n,[]):
				if not seen.has(m):seen[m]=true;queue.append(m)
		return seen

func _initialize():
	var fake=Fake.new()
	var planner=PLANNER.new(fake)
	var root: Array=[{"id":"A"},"exit",{}]
	var x: Dictionary={"id":"X","reward":false}
	var q: Dictionary={"id":"Q","reward":true}
	var y: Dictionary={"id":"Y","reward":false}
	fake.g={"A.exit:depart":["X.in:arrive"],"X.in:arrive":["X.out:depart"],"X.out:depart":["Q.in:arrive"],"Q.in:arrive":["Q:reward:r"],"Q:reward:r":["Q.out:depart"],"Q.out:depart":["Y.in:arrive"],"Y.in:arrive":["Y.out:depart"],"Y.out:depart":["B.in:arrive"],"B.in:arrive":["BOSS"]}
	var merged: Dictionary=await planner.prove([x,q,y],root,[])
	var checks: Dictionary={"three_room_forward_merge":merged.get("kind")=="forward_merge" and merged.instance_ids.size()==3}
	fake.g.erase("Y.out:depart")
	fake.g["B.in:arrive"]=["Y.out:depart","BOSS"]
	checks.no_implicit_reverse=(await planner.prove([x,q,y],root,[])).is_empty()
	fake.g["Q.out:depart"]=["X.return:arrive"]
	fake.g["X.return:arrive"]=["X.back:depart"]
	fake.g["X.back:depart"]=["A.return:arrive"]
	fake.g["A.return:arrive"]=["BOSS"]
	var folded: Dictionary=await planner.prove([x,q],root,[])
	checks.two_room_return=folded.get("kind")=="multi_return"
	checks.unused_padding_rejected=(await planner.prove([x,q,y],root,[])).is_empty()
	fake.g["A.exit:depart"]=["B.transit:arrive"]
	fake.g["B.transit:arrive"]=["Q.in:arrive"]
	checks.cannot_cross_core_before_reward=(await planner.prove([q],root,[])).is_empty()
	fake.cancelled=true
	checks.cancelled_path_empty=(await planner.prove([q],root,[])).is_empty()
	var ok: bool=checks.values().all(func(v):return v)
	print(JSON.stringify({"status":"PASS" if ok else "FAIL","checks":checks,"scope":"synthetic graph unit checks, not module physics"}))
	quit(0 if ok else 1)
