extends RefCounted
const DATA=preload("data_json.gd")
const IMPLEMENTATION="mapgen/additions-gdscript-0.1.0"
static func sha(value) -> String:return DATA.canonical(value).sha256_text()
static func finite_point(p) -> bool:return p is Array and p.size()==2 and p.all(func(x):return (x is float or x is int) and is_finite(float(x)))
static func validate(source,config,destinations) -> String:
	if not source is Dictionary or source.get("status")!="PASS" or not source.get("map") is Dictionary or not source.get("content_store") is Dictionary:return "source: successful complete generation result required"
	var m: Dictionary=source.map
	if m.get("schema")!="mapgen/runtime-map/v2" or not m.get("coordinates",{}).get("content_transform_applied",false):return "source: materialized runtime-map/v2 required"
	if not m.get("instances") is Array or not m.get("graph") is Dictionary or not m.graph.get("nodes") is Array or not m.graph.get("edges") is Array or not m.graph.get("main_paths") is Array or not m.get("inputs",{}).get("request",{}).get("player",{}).get("clearance_half_extents_pixels") is Array:return "source: incomplete map graph/instances/player"
	if not config is Dictionary or config.get("schema")!="mapgen/map-additions-config/v1" or config.keys().size()!=4 or not config.has("signage") or not config.has("moving_saws") or not config.has("budget"):return "config: exact signage/moving_saws/budget configuration required"
	if not config.budget is Dictionary or config.budget.size()!=1 or not config.budget.get("max_work_units") is int or config.budget.max_work_units<1:return "config.budget: positive integer max_work_units required"
	for section in ["signage","moving_saws"]:
		if not config[section] is Dictionary or not config[section].get("enabled") is bool:return "config.enabled: boolean required"
	var required: Dictionary={"signage":["enabled","allow_suspended","board_size_pixels","sample_step_pixels","interact_radius_pixels","search_radius_pixels","merge_radius_pixels","branch_separation_pixels"],"moving_saws":["enabled","max_groups","radius_pixels","min_travel_pixels","max_travel_pixels","min_spacing_pixels","density_radius_pixels","max_local_groups","margin_pixels","period_seconds","random_keep_probability","candidate_limit"]}
	for section in required:
		if config[section].size()!=required[section].size():return "config: missing/unknown properties"
		for key in required[section]:
			if not config[section].has(key):return "config: missing "+key
			var value=config[section][key]
			if key in ["enabled","board_size_pixels","allow_suspended"]:continue
			if not (value is int or value is float) or not is_finite(float(value)) or value<0:return "config: invalid nonnegative number "+key
	if not finite_point(config.signage.board_size_pixels) or config.signage.board_size_pixels.min()<=0 or config.signage.sample_step_pixels<1 or config.signage.search_radius_pixels<1 or config.signage.interact_radius_pixels<1:return "config.signage: positive dimensions/radii required"
	if not config.signage.allow_suspended is bool:return "config.signage.allow_suspended: boolean required"
	var c: Dictionary=config.moving_saws
	for key in ["max_groups","max_local_groups","candidate_limit"]:
		if not c[key] is int:return "config: integer required "+key
	if c.radius_pixels<=0 or c.min_travel_pixels<=0 or c.max_travel_pixels<c.min_travel_pixels or c.period_seconds<=0 or c.random_keep_probability>1 or c.max_local_groups<1 or c.candidate_limit<1:return "config.moving_saws: invalid range"
	if not destinations is Array:return "destinations: array required"
	var seen: Dictionary={}
	for d in destinations:
		if not d is Dictionary or d.size()!=5 or not d.has("id") or not d.has("kind") or not d.has("instance_id") or not d.has("node_id") or not d.has("position_pixels"):return "destination: exact id/kind/instance_id/node_id/position_pixels required"
		if not d.id is String or d.id.is_empty() or seen.has(d.id) or d.kind!="shop" or not finite_point(d.position_pixels):return "destination: invalid/duplicate shop"
		seen[d.id]=true
	return ""
