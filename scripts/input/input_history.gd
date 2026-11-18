class_name InputHistory
extends RefCounted
## Training-mode input history (spec §4.5): consecutive identical inputs are
## merged into one entry with a tick count, newest last.

const MAX_ENTRIES: int = 12

var _entries: Array[Dictionary] = []   # {move_x, buttons, ticks}


func record(frame: FighterInputFrame) -> void:
	var mx: int = frame.move_x if frame != null else 0
	var bt: int = frame.buttons if frame != null else 0
	if not _entries.is_empty():
		var last: Dictionary = _entries[-1]
		if last.move_x == mx and last.buttons == bt:
			last.ticks = mini(last.ticks + 1, 999)
			return
	_entries.append({"move_x": mx, "buttons": bt, "ticks": 1})
	if _entries.size() > MAX_ENTRIES:
		_entries.pop_front()


func clear() -> void:
	_entries.clear()


func size() -> int:
	return _entries.size()


## Newest first, e.g. "→ L      3".
func lines(n: int = MAX_ENTRIES) -> PackedStringArray:
	var out: PackedStringArray = []
	for k: int in range(_entries.size() - 1, maxi(-1, _entries.size() - 1 - n), -1):
		var e: Dictionary = _entries[k]
		out.append("%s %-7s %3d" % [_dir_text(e.move_x), _button_text(e.buttons), e.ticks])
	return out


static func _dir_text(mx: int) -> String:
	return "←" if mx < 0 else ("→" if mx > 0 else "·")


static func _button_text(b: int) -> String:
	var s: String = ""
	if b & FighterInputFrame.BUTTON_LIGHT:
		s += "L"
	if b & FighterInputFrame.BUTTON_HEAVY:
		s += "H"
	if b & FighterInputFrame.BUTTON_KICK:
		s += "K"
	if b & FighterInputFrame.BUTTON_BLOCK:
		s += "B"
	if b & FighterInputFrame.BUTTON_SPECIAL:
		s += "S"
	if b & FighterInputFrame.BUTTON_ULTIMATE:
		s += "U"
	return s if not s.is_empty() else "-"
