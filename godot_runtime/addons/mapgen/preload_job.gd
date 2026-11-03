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
var use_derived := true
var cache_status := "not_attempted"

static func create(path: String, expected_sha256: String, allow_derived := true):
	var job = load("res://addons/mapgen/preload_job.gd").new()
	job._path = path
	job._expected = expected_sha256
	job.use_derived = allow_derived
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
	var cached: Dictionary = await _derived() if use_derived else {}
	if _cancelled:
		_fail("cancelled")
		return
	var manifest: Dictionary = {"ok":true,"value":cached.manifest} if cached.has("manifest") else await DATA.parse_incremental(_archive._files["manifest.json"].get_string_from_utf8(),self)
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
	if cached.has("json"):
		_archive._json = cached.json
		if not await consume():
			_fail("cancelled")
			return
		_phase = "ready"
		_result = {"status":"PASS","library":_archive,"checked_files":manifest.value.files.size(),"cache_status":cache_status}
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
	_result = {"status": "PASS", "library": _archive, "checked_files": manifest.value.files.size(),"cache_status":cache_status}

func _derived() -> Dictionary:
	# Source ZIP and EVERY manifest member are still verified. This reconstructs
	# only source JSON values, not requests, prepared templates, RNG, or maps.
	_phase = "derived_json"
	var path := "res://addons/mapgen/derived_library.gd"
	if not ResourceLoader.exists(path):
		cache_status="missing_rebuilt"
		return {}
	var cache = load(path)
	return await _decode_derived(cache.SCHEMA,cache.MODULE_SHA,cache.IMPLEMENTATION,cache.ROWS)

func _decode_derived(schema: String,module_sha: String,implementation: String,rows: Array) -> Dictionary:
	if schema!="mapgen/derived-library/v1" or module_sha!=_expected or implementation!=PROTOCOL.IMPLEMENTATION:
		cache_status="binding_rejected_rebuilt"
		return {}
	var json: Dictionary={}
	var catalog: Dictionary={}
	var modules: Array=[]
	var manifest: Dictionary={}
	for row in rows:
		if not await consume_heavy():return {}
		var packed:=Marshalls.base64_to_raw(row[3])
		var hash:=HashingContext.new();hash.start(HashingContext.HASH_SHA256);hash.update(packed)
		if hash.finish().hex_encode()!=row[2] or row[1]<1 or row[1]>16777216:
			cache_status="payload_rejected_rebuilt"
			return {}
		var raw:=packed.decompress(row[1],FileAccess.COMPRESSION_DEFLATE)
		if raw.size()!=row[1]:
			cache_status="payload_rejected_rebuilt"
			return {}
		var value=bytes_to_var(raw) # No object decoding/execution.
		if not value is Dictionary:
			cache_status="payload_rejected_rebuilt"
			return {}
		if row[0]=="manifest":manifest=value
		elif row[0]=="catalog_header":catalog=value
		elif row[0]=="catalog_module":modules.append(value)
		elif row[0].begins_with("json:"):json[row[0].substr(5)]=value
	if manifest.is_empty() or catalog.is_empty() or modules.size()!=115:
		cache_status="structure_rejected_rebuilt"
		return {}
	catalog.modules=modules
	json["catalog.json"]=catalog
	cache_status="bound_source_json"
	return {"manifest":manifest,"json":json}

func consume_heavy() -> bool:
	for _i in range(QUANTUM):
		if not await consume():
			return false
	return true
