extends RefCounted
## One owner, cooperative data work. A unit is 16 checkpoints, NOT milliseconds.
signal _resume
const QUANTUM := 16
var _result: Dictionary = {}
var _credits := 0
var _microsteps := 0
var _started := false
var _cancelled := false
var _running := false
var _phase := "created"
var _samples: Dictionary = {}
var _created_usec := Time.get_ticks_usec()

func phase_name() -> String:
	return _phase

func advance(budget: int = 1) -> Dictionary:
	if budget < 1 or budget > 4096 or _running:
		return {"ok": false, "error": "budget must be 1..4096; one non-reentrant owner", "progress": progress()}
	var phase := phase_name()
	var start := Time.get_ticks_usec()
	if not is_done():
		_credits = budget*QUANTUM
		_running = true
		if not _started:
			_started = true
			_run()
		else:
			_resume.emit()
		_running = false
	var elapsed := Time.get_ticks_usec()-start
	if not _samples.has(phase):
		_samples[phase] = []
	_samples[phase].append(elapsed)
	return {"ok": true, "progress": progress()}

func consume() -> bool:
	while _credits == 0 and not _cancelled:
		await _resume
	if _cancelled:
		return false
	_credits -= 1
	_microsteps += 1
	return true

func cancel() -> void:
	if is_done():
		return
	_cancelled = true
	if not _started:
		_cancel_created()
	elif not _running:
		_running = true
		_resume.emit()
		_running = false

func _cancel_created() -> void:
	_result = {"status": "CANCELLED"}

func _run() -> void:
	_result = {"status": "ERROR", "error": "abstract work gate"}

func is_done() -> bool:
	return not _result.is_empty()

func result() -> Dictionary:
	return _result.duplicate(true)

func progress() -> Dictionary:
	return {"done": is_done(), "phase": phase_name(), "operations": (_microsteps+QUANTUM-1)/QUANTUM, "microsteps": _microsteps}

func profile() -> Dictionary:
	var phases: Dictionary = {}
	for phase in _samples:
		var values: Array = _samples[phase].duplicate()
		values.sort()
		var total := 0
		for value in values:
			total += value
		phases[phase] = {"calls": values.size(), "total_usec": total, "max_usec": values[-1], "p50_usec": values[int((values.size()-1)*0.50)], "p95_usec": values[int((values.size()-1)*0.95)], "p99_usec": values[int((values.size()-1)*0.99)]}
	return {"wall_usec": Time.get_ticks_usec()-_created_usec, "phases": phases, "classification": "phase at advance entry; boundary call charged to entry phase", "quantum_checkpoints": QUANTUM}
