extends RefCounted
const SCHEMA = preload("schema_data.gd")
const DATA = preload("data_json.gd")
const IMPLEMENTATION := "mapgen/gdscript-experiment-0.6.0"
const ALGORITHM := "stable-v5-joint-reward-plans"
const MAX_SEED := 9007199254740991
const PACKAGE_SHA := "5ad5a7871941b2c1ffa759b18f7b1e80f2fe7e571b72f95d1e0ef26031f08723"

static func validate(request, config) -> String:
	var error := schema_error(request, SCHEMA.REQUEST, "request")
	if not error.is_empty():
		return error
	error = schema_error(config, SCHEMA.CONFIG, "config")
	if not error.is_empty():
		return error
	if config.algorithm != ALGORITHM:
		return "config.algorithm: this package supports only "+ALGORITHM
	if config.diversity.early_fraction >= config.diversity.late_fraction:
		return "config.diversity: early_fraction must precede late_fraction"
	if request.seed < -MAX_SEED or request.seed > MAX_SEED:
		return "request.seed: supported range is [-9007199254740991,9007199254740991]; no truncation"
	if "recoil" in request.player.abilities:
		return "request.player.abilities: use native shot_recoil"
	if request.terminals.start.module_id == request.terminals.boss.module_id:
		return "request.terminals: start and boss must be distinct"
	for mid in request.module_filter.include_ids:
		if mid in request.module_filter.exclude_ids:
			return "request.module_filter: include/exclude overlap"
	for extent in request.player.clearance_half_extents_pixels:
		if extent < 0.000001:
			return "request.player.clearance: below reference minimum"
	# Prevent integer overflow in subsequent doubled coordinates. This candidate
	# additionally limits origins, rather than silently narrowing through Vector2.
	for coordinate in request.start_origin_blocks:
		if coordinate < -1000000000 or coordinate > 1000000000:
			return "request.start_origin_blocks: candidate supports +/-1000000000"
	return ""

static func schema_error(value, schema: Dictionary, path: String) -> String:
	if schema.has("anyOf"):
		for branch in schema.anyOf:
			if schema_error(value, branch, path).is_empty():
				return ""
		return path + ": no supported alternative"
	if schema.has("enum") and not value in schema["enum"]:
		return path + ": unsupported enum"
	if schema.has("const") and value != schema["const"]:
		return path + ": unsupported constant"
	var kind: String = schema.get("type", "")
	var valid: bool = kind.is_empty() or (kind == "object" and value is Dictionary) or (kind == "array" and value is Array) or (kind == "integer" and value is int) or (kind == "number" and (value is int or value is float) and is_finite(float(value))) or (kind == "string" and value is String) or (kind == "boolean" and value is bool) or (kind == "null" and value == null)
	if not valid:
		return path + ": expected " + kind
	if value is Dictionary:
		for key in schema.get("required", []):
			if not value.has(key):
				return path + ": missing " + key
		var properties: Dictionary = schema.get("properties", {})
		for key in value:
			if not properties.has(key):
				if schema.get("additionalProperties", true) == false:
					return path + ": unknown " + key
			else:
				var error := schema_error(value[key], properties[key], path + "." + key)
				if not error.is_empty():
					return error
	if value is Array:
		if value.size() < schema.get("minItems", 0) or value.size() > schema.get("maxItems", 9223372036854775807):
			return path + ": array length"
		var seen: Array = []
		for item in value:
			if schema.get("uniqueItems", false) and item in seen:
				return path + ": duplicate item"
			seen.append(item)
			var error := schema_error(item, schema.get("items", {}), path + "[]")
			if not error.is_empty():
				return error
	if value is String and value.length() < schema.get("minLength", 0):
		return path + ": string length"
	if value is int or value is float:
		if schema.has("minimum") and value < schema.minimum or schema.has("maximum") and value > schema.maximum or schema.has("exclusiveMinimum") and value <= schema.exclusiveMinimum:
			return path + ": numeric range"
	return ""

static func fingerprint(request: Dictionary, config: Dictionary, library_sha: String) -> String:
	return DATA.canonical({"request": request, "config": config, "library_sha256": library_sha, "implementation": IMPLEMENTATION}).sha256_text()

static func failure(status: String, fingerprint_value, message: String, phase: String, metrics: Dictionary = {}, details: Dictionary = {}) -> Dictionary:
	return {"schema": "mapgen/generation-result/v1", "status": status, "request_fingerprint": fingerprint_value, "map": null, "content_store": {}, "metrics": metrics.duplicate(true), "diagnostics": {"error": {"type": "GDScriptCandidate", "message": message, "phase": phase}, "implementation": IMPLEMENTATION, "details": details.duplicate(true)}}
