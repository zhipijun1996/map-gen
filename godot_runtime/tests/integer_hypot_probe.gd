extends SceneTree
func _initialize():
	var vectors = preload("res://addons/mapgen/data_json.gd").parse(FileAccess.get_file_as_string("res://tests/hypot-vectors.json")).value
	var failures: Array = []
	for row in vectors:
		if preload("res://addons/mapgen/numeric.gd").binary64_be(preload("res://addons/mapgen/numeric.gd").integer_hypot(row.x,row.y)) != row.bits:
			failures.append(row)
	print({"vectors":vectors.size(),"failures":failures})
	quit(0 if failures.is_empty() else 1)
