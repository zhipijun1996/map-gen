extends "work_gate.gd"
## Explicit resumable I/O adapter. Never executes ZIP scripts or scenes.
const DATA = preload("data_json.gd")
const ARCHIVE = preload("module_archive.gd")
const PROTOCOL = preload("protocol.gd")
var json_number_cache: Dictionary = {}
var _path := ""
var _expected := ""
var _archive
var _zip: ZIPReader
var _file: FileAccess

static func create(path: String, expected_sha256: String):
	var job = load("res://addons/mapgen/preload_job.gd").new()
	job._path = path
	job._expected = expected_sha256
	return job

func _close() -> void:
	if _zip != null:
		_zip.close()
		_zip = null
	_file = null

func _fail(message: String) -> void:
	_close()
	_result = {"status": "CANCELLED" if _cancelled else "INVALID_INPUT", "error": message}
	_archive = null

func _cancel_created() -> void:
	_fail("cancelled")

func _run() -> void:
	_phase = "zip_hash"
	if _expected != PROTOCOL.PACKAGE_SHA:
		_fail("only locked module package 1.1.0 is supported")
		return
	_file = FileAccess.open(_path,FileAccess.READ)
	if _file == null:
		_fail("missing ZIP")
		return
	var hash := HashingContext.new()
	hash.start(HashingContext.HASH_SHA256)
	while _file.get_position() < _file.get_length():
		if not await consume():
			_fail("cancelled")
			return
		hash.update(_file.get_buffer(16384))
	_file = null
	if hash.finish().hex_encode() != _expected:
		_fail("archive SHA-256 mismatch")
		return
	_phase = "zip_entries"
	if not await consume():
		_fail("cancelled")
		return
	_zip = ZIPReader.new()
	if _zip.open(_path) != OK:
		_fail("invalid ZIP")
		return
	_archive = ARCHIVE.new()
	_archive.sha256 = _expected
	_archive.version = "1.1.0"
	var seen: Dictionary = {}
	for name in _zip.get_files():
		if not await consume_heavy():
			_fail("cancelled")
			return
		if name.begins_with("/") or "\\" in name or ".." in name.split("/") or seen.has(name):
			_fail("unsafe/duplicate ZIP path")
			return
		seen[name] = true
		if not name.ends_with("/"):
			_archive._files[name] = _zip.read_file(name)
	_close()
	_phase = "manifest_json"
	var manifest: Dictionary = await DATA.parse_incremental(_archive._files["manifest.json"].get_string_from_utf8(),self)
	if not manifest.ok or manifest.value.get("schema") != "map-edit/module-package/v1" or manifest.value.get("version") != "1.1.0":
		_fail("invalid manifest or cancelled")
		return
	_phase = "file_hashes"
	for name in manifest.value.files:
		if not _archive._files.has(name):
			_fail("missing file:"+name)
			return
		var bytes: PackedByteArray = _archive._files[name]
		hash = HashingContext.new()
		hash.start(HashingContext.HASH_SHA256)
		for offset in range(0,bytes.size(),16384):
			if not await consume_heavy():
				_fail("cancelled")
				return
			hash.update(bytes.slice(offset,mini(offset+16384,bytes.size())))
		if hash.finish().hex_encode() != manifest.value.files[name]:
			_fail("file checksum mismatch:"+name)
			return
	_phase = "catalog_json"
	var catalog: Dictionary = await DATA.parse_incremental(_archive._files["catalog.json"].get_string_from_utf8(),self)
	if not catalog.ok or catalog.value.get("schema") != "map-edit/delivery-catalog/v1":
		_fail("invalid catalog or cancelled")
		return
	_archive._json["catalog.json"] = catalog.value
	var paths: Dictionary = {"reward-association-gaps.json": true}
	for entry in catalog.value.modules:
		paths[entry.compiled] = true
		paths[entry.scene.replace("module.tscn","module.mapnote.json")] = true
	_phase = "module_json"
	for name in paths:
		if not _archive._files.has(name):
			_fail("missing JSON:"+name)
			return
		var decoded: Dictionary = await DATA.parse_incremental(_archive._files[name].get_string_from_utf8(),self)
		if not decoded.ok:
			_fail("invalid JSON or cancelled:"+name)
			return
		_archive._json[name] = decoded.value
	if not await consume():
		_fail("cancelled")
		return
	_phase = "ready"
	_result = {"status": "PASS", "library": _archive, "checked_files": manifest.value.files.size()}

func consume_heavy() -> bool:
	for _i in range(QUANTUM):
		if not await consume():
			return false
	return true
