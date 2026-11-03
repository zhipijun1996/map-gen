extends RefCounted
## Cooperative data-only job; no SceneTree, worker, Node, callback/service bag.
const PROTOCOL = preload("protocol.gd")
const PREPARED = preload("prepared_library.gd")
const SOLVER = preload("solver.gd")
const EXPORT = preload("runtime_export.gd")
signal _resume
var _request: Dictionary
var _config: Dictionary
var _library
var _solver
var _prepared
var _fingerprint = null
var _result: Dictionary = {}
var _credits := 0
var _operations := 0
var _started := false
var _cancelled := false
var _running := false
var _phase := "created"

static func create(request, library, config):
	var job = load("res://addons/mapgen/generation_job.gd").new()
	var error := PROTOCOL.validate(request, config)
	if not error.is_empty() or library == null or library.sha256 != PROTOCOL.PACKAGE_SHA:
		job._result = PROTOCOL.failure("INVALID_INPUT", null, error if not error.is_empty() else "library: expected locked ModuleArchive", "input")
		return job
	job._request = request.duplicate(true)
	job._config = config.duplicate(true)
	job._library = library
	job._fingerprint = PROTOCOL.fingerprint(job._request, job._config, library.sha256)
	return job

func advance(operation_budget: int = 128) -> Dictionary:
	if operation_budget < 1 or operation_budget > 4096:
		return {"ok": false, "error": "advance budget must be 1..4096", "progress": progress()}
	if _running:
		return {"ok": false, "error": "job is not reentrant", "progress": progress()}
	if not is_done():
		_credits = operation_budget
		_running = true
		if not _started:
			_started = true
			_run()
		else:
			_resume.emit()
		_running = false
	return {"ok": true, "progress": progress()}

func progress() -> Dictionary:
	return {"done": is_done(), "phase": _solver.phase if _solver != null else _phase, "operations": _operations, "expanded": _solver.expanded if _solver != null else 0, "instances": _solver.items.size() if _solver != null else 0, "request_fingerprint": _fingerprint, "implementation": PROTOCOL.IMPLEMENTATION}

func is_done() -> bool:
	return not _result.is_empty()

func result() -> Dictionary:
	return _result.duplicate(true)

func cancel() -> void:
	if is_done():
		return
	_cancelled = true
	if not _started:
		_phase = "cancelled"
		_result = PROTOCOL.failure("CANCELLED", _fingerprint, "cancelled", _phase)
	elif not _running:
		_running = true
		_resume.emit() # Unwind pending pure-data continuation; no scene callback.
		_running = false

func consume() -> bool:
	while _credits == 0 and not _cancelled:
		await _resume
	if _cancelled:
		return false
	_credits -= 1
	_operations += 1
	return true

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
	var accepted: bool = await _solver.build()
	_phase = _solver.phase
	_result = PROTOCOL.failure(_solver.error_status if not _solver.error_status.is_empty() else "ERROR", _fingerprint, _solver.error_message if not _solver.error_message.is_empty() else "IMPLEMENTATION_INCOMPLETE", _phase, _solver.metrics(), _solver.diagnostics())
	# This staged candidate never publishes a partial map. Full export is gated.
	if accepted:
		var exported: Array = EXPORT.export_map(_solver.final_source, _solver, _fingerprint)
		_result.status = "PASS"
		_result.map = exported[0]
		_result.content_store = exported[1]
		_result.diagnostics.error = null
		_result.diagnostics.independent_audit = _solver.final_source.independent_audit
		_result.diagnostics.quality = _solver.final_source.quality
		_result.diagnostics.physical_notes = _solver.final_source.physical_notes
		_result.diagnostics.blockers = _solver.final_source.blockers
