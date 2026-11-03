extends RefCounted
## Explicit I/O adapter. Loads DATA only; never loads package .gd/.tscn code.
const DATA = preload("data_json.gd")
const PROTOCOL = preload("protocol.gd")
var sha256 := ""
var version := ""
var _files: Dictionary = {}
var _json: Dictionary = {}

static func open_zip(path: String, expected_sha256: String) -> Dictionary:
	if expected_sha256 != PROTOCOL.PACKAGE_SHA:
		return {"ok": false, "error": "candidate supports only locked module package 1.1.0 SHA"}
	if not FileAccess.file_exists(path) or FileAccess.get_sha256(path) != expected_sha256:
		return {"ok": false, "error": "library: archive SHA-256 mismatch/missing file"}
	var zip := ZIPReader.new()
	if zip.open(path) != OK:
		return {"ok": false, "error": "library: invalid ZIP"}
	var files: Dictionary = {}
	for name in zip.get_files():
		if name.begins_with("/") or "\\" in name or ".." in name.split("/") or files.has(name):
			zip.close()
			return {"ok": false, "error": "library: unsafe/duplicate archive path"}
		if not name.ends_with("/"):
			files[name] = zip.read_file(name)
	zip.close()
	var manifest := DATA.parse(files.get("manifest.json", PackedByteArray()).get_string_from_utf8())
	if not manifest.ok or not manifest.value is Dictionary or manifest.value.get("schema") != "map-edit/module-package/v1" or manifest.value.get("version") != "1.1.0":
		return {"ok": false, "error": "library: unsupported manifest"}
	for name in manifest.value.files:
		if not files.has(name):
			return {"ok": false, "error": "library: missing file:" + name}
		var hash := HashingContext.new()
		hash.start(HashingContext.HASH_SHA256)
		hash.update(files[name])
		if hash.finish().hex_encode() != manifest.value.files[name]:
			return {"ok": false, "error": "library: file checksum mismatch:" + name}
	var archive = load("res://addons/mapgen/module_archive.gd").new()
	archive.sha256 = expected_sha256
	archive.version = manifest.value.version
	archive._files = files
	# Explicit preload/I/O boundary, OUTSIDE incremental search. Job advance never
	# decompresses or parses the multi-megabyte catalog. Host preloads once.
	var catalog := DATA.parse(files.get("catalog.json", PackedByteArray()).get_string_from_utf8())
	if not catalog.ok or not catalog.value is Dictionary or catalog.value.get("schema") != "map-edit/delivery-catalog/v1":
		return {"ok": false, "error": "library: unsupported catalog"}
	archive._json["catalog.json"] = catalog.value
	var paths: Dictionary = {"reward-association-gaps.json": true}
	for entry in catalog.value.modules:
		paths[entry.compiled] = true
		paths[entry.scene.replace("module.tscn", "module.mapnote.json")] = true
	for name in paths:
		if not files.has(name):
			return {"ok": false, "error": "library: missing JSON:" + name}
		var decoded := DATA.parse(files[name].get_string_from_utf8())
		if not decoded.ok:
			return {"ok": false, "error": "library: invalid JSON:" + name + ":" + decoded.error}
		archive._json[name] = decoded.value
	return {"ok": true, "library": archive, "checked_files": manifest.value.files.size()}

func read_json(path: String) -> Dictionary:
	if _json.has(path):
		return {"ok": true, "value": _json[path].duplicate(true), "error": ""}
	if not _files.has(path):
		return {"ok": false, "error": "library: missing JSON:" + path}
	return DATA.parse(_files[path].get_string_from_utf8())

func _view_json(path: String) -> Dictionary:
	# Internal immutable view. PreparedLibrary never mutates source JSON.
	return {"ok":true,"value":_json[path],"error":""} if _json.has(path) else read_json(path)
