extends "work_gate.gd"
## Cooperative data-only job; no SceneTree, worker, Node, callback/service bag.
const PROTOCOL = preload("protocol.gd")
const PREPARED = preload("prepared_library.gd")
const SOLVER = preload("solver.gd")
const EXPORT = preload("runtime_export.gd")
const ARCHIVE = preload("module_archive.gd")
var _request: Dictionary
var _config: Dictionary
var _library
var _solver
var _prepared
var _fingerprint = null
var work_phase := ""

static func create(request, library, config):
	var job = load("res://addons/mapgen/generation_job.gd").new()
	var error := PROTOCOL.validate(request, config)
	if not error.is_empty() or not library is ARCHIVE or library.sha256 != PROTOCOL.PACKAGE_SHA:
		job._result = PROTOCOL.failure("INVALID_INPUT", null, error if not error.is_empty() else "library: expected locked ModuleArchive", "input")
		return job
	job._request = request.duplicate(true)
	job._config = config.duplicate(true)
	job._library = library
	job._fingerprint = PROTOCOL.fingerprint(job._request, job._config, library.sha256)
	return job

func phase_name() -> String:
	return work_phase if not work_phase.is_empty() else _phase if _phase == "export" else _solver.phase if _solver != null else _phase

func progress() -> Dictionary:
	return {"done":is_done(),"phase":phase_name(),"operations":(_microsteps+QUANTUM-1)/QUANTUM,"microsteps":_microsteps,"expanded":_solver.expanded if _solver!=null else 0,"instances":_solver.items.size() if _solver!=null else 0,"request_fingerprint":_fingerprint,"implementation":PROTOCOL.IMPLEMENTATION}

func _cancel_created() -> void:
	_result = PROTOCOL.failure("CANCELLED",_fingerprint,"cancelled","created")

func _run() -> void:
	_phase = "prepare"
	if not await consume():
		_result = PROTOCOL.failure("CANCELLED", _fingerprint, "cancelled", _phase)
		return
	_prepared = PREPARED.new()
	if not _prepared.begin(_library, _request, _config):
		_result = PROTOCOL.failure("INVALID_INPUT", _fingerprint, _prepared.error, _phase)
		return
	while not _prepared.ready and _prepared.error.is_empty():
		if not await consume():
			_result = PROTOCOL.failure("CANCELLED", _fingerprint, "cancelled", _phase)
			return
		_prepared.advance_one()
	if not _prepared.error.is_empty():
		_result = PROTOCOL.failure("INVALID_INPUT", _fingerprint, _prepared.error, _phase)
		return
	_solver = SOLVER.new(self, _request, _prepared, _config)
	var accepted := false
	if await _solver.initialize():
		accepted = await _solver.build()
	_phase = _solver.phase
	var exported: Array = []
	if accepted:
		_phase = "export"
		exported = await EXPORT.export_map(_solver.final_source, _solver, _fingerprint)
	if _solver.aborted():
		# Python API records the escaping exception in addition to search-local
		# failures. Preserve that final diagnostic and its operation count.
		_solver.record_failure(_solver.error_message)
	_result = PROTOCOL.failure(_solver.error_status if not _solver.error_status.is_empty() else "ERROR", _fingerprint, _solver.error_message if not _solver.error_message.is_empty() else "IMPLEMENTATION_INCOMPLETE", _phase, _solver.metrics(), _solver.diagnostics())
	if accepted and not _solver.aborted() and exported.size() == 2:
		_result.status = "PASS"
		_result.map = exported[0]
		_result.content_store = exported[1]
		_result.diagnostics.error = null
		_result.diagnostics.independent_audit = _solver.final_source.independent_audit
		_result.diagnostics.quality = _solver.final_source.quality
		_result.diagnostics.physical_notes = _solver.final_source.physical_notes
		_result.diagnostics.blockers = _solver.final_source.blockers
