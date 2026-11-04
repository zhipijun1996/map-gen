extends SceneTree
const PLANNER=preload("res://addons/mapgen/reward_branch_planner.gd")
const NUM=preload("res://addons/mapgen/numeric.gd")
class Fake extends RefCounted:
	var config: Dictionary={"diversity":{},"scoring":{"reward_near_radius":8.0}}
	var reward_core: Dictionary={}
	var reward_core_rank: Dictionary={}
	var items: Array=[]
	var templates: Dictionary={}
	var invalid:=false
	func origin_distance(a: Array,b: Array):
		var value: float=NUM.integer_hypot(a[0]-b[0],a[1]-b[1])
		if not is_finite(value):invalid=true;return 0.0
		return value

func _initialize():
	var fake=Fake.new();var planner=PLANNER.new(fake);var checks:=0;var failures: Array=[]
	for radius in [0.0,0.25,1.0,1.414213562373095,1.4142135623730951,1.4142135623730954,8.0,8.000000000000002,3000000000.0]:
		fake.config.scoring.reward_near_radius=radius
		var points: Array=[]
		for x in range(-16,17):
			for y in range(-16,17):points.append([x,y])
		points.append_array([[2000000000,2000000000],[2000000001,0],[-2000000001,2]])
		for xy in points:
			fake.invalid=false
			var expected: bool=fake.origin_distance(xy,[0,0])<radius
			var error_before: bool=fake.invalid;fake.invalid=false
			var actual: bool=planner.near_reward(xy,[0,0])
			if actual!=expected or fake.invalid!=error_before:failures.append([xy,radius])
			checks+=1
	print(JSON.stringify({"status":"PASS" if failures.is_empty() else "FAIL","checks":checks,"failed":failures,"scope":"old correctly-rounded hypot comparison vs fast bounds; ULP boundaries, negative coordinates, zero radius and original domain errors"}))
	quit(0 if failures.is_empty() else 1)
