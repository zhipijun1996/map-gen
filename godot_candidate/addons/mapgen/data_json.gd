extends RefCounted
const DECIMAL = preload("decimal64.gd")
## Strict JSON data reader: preserve integer tokens before Godot can round them.
## Accept signed int64 JSON integers; protocol narrows seeds to +/- (2^53-1).
var source := ""
var cursor := 0
var error := ""

static func parse(text: String) -> Dictionary:
	var reader = load("res://addons/mapgen/data_json.gd").new()
	reader.source = text
	var value = reader._value(0)
	reader._space()
	if reader.error.is_empty() and reader.cursor != text.length():
		reader.error = "trailing JSON input"
	return {"ok": reader.error.is_empty(), "value": value, "error": reader.error}

func _space() -> void:
	while cursor < source.length() and source[cursor] in [" ", "\t", "\n", "\r"]:
		cursor += 1

func _fail(message: String):
	if error.is_empty():
		error = "%s at %d" % [message, cursor]
	return null

func _string():
	var start := cursor
	cursor += 1
	while cursor < source.length():
		if source[cursor] == "\\":
			cursor += 2
			continue
		if source[cursor] == '"':
			cursor += 1
			var parser := JSON.new()
			if parser.parse(source.substr(start, cursor-start)) != OK:
				return _fail("invalid JSON string")
			return parser.data
		cursor += 1
	return _fail("unterminated JSON string")

func _value(depth: int):
	_space()
	if depth > 128 or cursor >= source.length():
		return _fail("JSON nesting/input limit")
	var ch := source[cursor]
	if ch == '"':
		return _string()
	if ch in ["{", "["]:
		var object := ch == "{"
		var end := "}" if object else "]"
		var result = {} if object else []
		cursor += 1
		_space()
		if cursor < source.length() and source[cursor] == end:
			cursor += 1
			return result
		while error.is_empty():
			_space()
			var key
			if object:
				if cursor >= source.length() or source[cursor] != '"':
					return _fail("expected object key")
				key = _string()
				if key == null or result.has(key):
					return _fail("duplicate/invalid object key")
				_space()
				if cursor >= source.length() or source[cursor] != ":":
					return _fail("expected colon")
				cursor += 1
			var item = _value(depth+1)
			if object:
				result[key] = item
			else:
				result.append(item)
			_space()
			if cursor >= source.length():
				return _fail("unterminated container")
			ch = source[cursor]
			cursor += 1
			if ch == end:
				return result
			if ch != ",":
				return _fail("expected comma")
		return null
	for word in ["true", "false", "null"]:
		if source.substr(cursor, word.length()) == word:
			cursor += word.length()
			return true if word == "true" else false if word == "false" else null
	var start := cursor
	while cursor < source.length() and source[cursor] in "-+0123456789.eE":
		cursor += 1
	var token := source.substr(start, cursor-start)
	var regex := RegEx.new()
	regex.compile("^-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?$")
	if regex.search(token) == null:
		return _fail("invalid JSON token")
	if "." in token or "e" in token.to_lower():
		var number := DECIMAL.parse(token)
		if not number.ok:
			return _fail(number.error)
		return number.value
	var magnitude := token.trim_prefix("-")
	var limit := "9223372036854775808" if token.begins_with("-") else "9223372036854775807"
	if magnitude.length() > limit.length() or magnitude.length() == limit.length() and magnitude > limit:
		return _fail("JSON integer outside int64; no truncation")
	return token.to_int()

static func canonical(value) -> String:
	# Implementation-specific, deterministic encoding; NOT Python canonical JSON.
	# Keep type distinctions, UTF-8 and stable key order. Used with a NEW identity.
	if value is Dictionary:
		var keys: Array = value.keys()
		keys.sort()
		var parts := PackedStringArray()
		for key in keys:
			parts.append(JSON.stringify(key) + ":" + canonical(value[key]))
		return "{" + ",".join(parts) + "}"
	if value is Array:
		var parts := PackedStringArray()
		for item in value:
			parts.append(canonical(item))
		return "[" + ",".join(parts) + "]"
	if value is float:
		assert(is_finite(value))
		var text := JSON.stringify(value, "", true, true)
		return text + ".0" if not "." in text and not "e" in text.to_lower() else text
	return JSON.stringify(value)
