class_name AIDecisionLog
extends RefCounted
## Bounded log of AI decisions for tuning (spec §5: record decisions in
## debug builds). Each entry: tick, state, action and the reason.

const MAX_ENTRIES: int = 200

var echo_to_stdout: bool = false
var label: String = "AI"
var _lines: PackedStringArray = []
var _total: int = 0


func add(tick: int, state: String, text: String) -> void:
	var line: String = "t%d %s %-8s %s" % [tick, label, state, text]
	_lines.append(line)
	_total += 1
	if _lines.size() > MAX_ENTRIES:
		_lines.remove_at(0)
	if echo_to_stdout:
		print("[AI] ", line)


func recent(n: int) -> PackedStringArray:
	return _lines.slice(maxi(0, _lines.size() - n))


func total_count() -> int:
	return _total


func to_text() -> String:
	return "\n".join(_lines)
