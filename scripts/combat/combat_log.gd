class_name CombatLog
extends RefCounted
## Bounded combat event history (spec §9.4: record events with tick numbers).

const MAX_EVENTS: int = 300

## Print each event to stdout as it happens (debug aid).
var echo_to_stdout: bool = false

var _events: Array[CombatEvent] = []
## Total events ever added (monotonic, survives ring-buffer trimming).
var _total: int = 0


func add(event: CombatEvent) -> void:
	_events.append(event)
	_total += 1
	if _events.size() > MAX_EVENTS:
		_events.pop_front()
	if echo_to_stdout:
		print("[CombatLog] ", event.to_text())


func total_count() -> int:
	return _total


## Events added after the log had [param count] total events.
func events_since(count: int) -> Array[CombatEvent]:
	var missing: int = _total - count
	if missing <= 0:
		return []
	var start: int = maxi(0, _events.size() - missing)
	return _events.slice(start)


func recent(n: int) -> Array[CombatEvent]:
	return _events.slice(maxi(0, _events.size() - n))


func all_events() -> Array[CombatEvent]:
	return _events.duplicate()


func clear() -> void:
	_events.clear()
	_total = 0


## Exact text of the whole log — used to prove determinism.
func to_text() -> String:
	var lines: PackedStringArray = []
	for e: CombatEvent in _events:
		lines.append(e.to_text())
	return "\n".join(lines)
