class_name TouchControls
extends CanvasLayer
## Multi-touch fighting controls (spec §2.4).
##
##   - Floating stick: touch anywhere in the stick zone (outer ~33 % of the
##     screen, below the HUD); drag left/right to walk, up to jump and
##     down to crouch (D-087).
##   - Action cluster: Light, Heavy, Kick, Block — fire on touch-DOWN, stay
##     held while that finger stays down (even if it slides off).
##   - Special (SP; hold toward the opponent for the forward special) and
##     Ultimate (ULT, only enabled when Origin Surge / the ultimate is usable).
##   - Every finger is tracked by its touch index, so walking and attacking
##     at the same time works.
##   - Left-handed layout mirrors stick and cluster.
## Emits only logical input actions (Input.action_press/release); no combat
## logic lives here.

## Reference layout is authored for a 2400×1080 viewport and scaled to fit.
const REF_HEIGHT: float = 1080.0
const BUTTON_RADIUS: float = 100.0
const STICK_RADIUS: float = 150.0
const KNOB_RADIUS: float = 64.0
const EDGE_MARGIN: float = 60.0
## Touches within radius × this count as a button hit (generous targets).
const HIT_SLOP: float = 1.15
## A direction that is already held lets go only below this share of its dead
## zone, so a thumb resting on the edge does not flick it on and off (a
## crouch that flickers looks like shaking, D-093).
const RELEASE_FACTOR: float = 0.7
## Down (crouch) lets go much later: a thumb resting a short way down sat
## between 0.7 and 1.0 of the dead zone, so ordinary thumb movement flipped
## crouch and stand every few frames — the "shaking crouch" from the phone
## (reproduced with simulated drags, D-095). Down now holds until the thumb
## is back within 0.35 of the dead zone (about a fifth of the stick radius).
const RELEASE_FACTOR_DOWN: float = 0.35
## Touches this close to the point between Light and Kick (× button radius)
## press both: the throw (D-103).
const THROW_SPOT_RADIUS: float = 0.42
## Stick dead zone (fraction of STICK_RADIUS) for left/right; up/down need more.
const DEADZONE_X: float = 0.3
const DEADZONE_Y: float = 0.55
## Fraction of screen width / top fraction of height excluded from the stick zone.
const STICK_ZONE_WIDTH: float = 0.33
const STICK_ZONE_TOP: float = 0.30

@export var left_handed: bool = false
@export_range(0.6, 1.6) var scale_factor: float = 1.0
@export_range(0.1, 1.0) var opacity: float = 0.55
## Show even without a touchscreen (debug builds/desktop testing).
@export var show_without_touchscreen: bool = true

var _canvas: Control
var _buttons: Array[Dictionary] = []
var _stick: Dictionary = {}
var _held: Dictionary = {}   # action → true while we hold it
var _font: Font
var _disabled: Dictionary = {}  # action → true when greyed out

## Emitted on every new touch (used to skip the ultimate cinematic).
signal touched


func _ready() -> void:
	_font = UiTheme.display_font()
	_canvas = Control.new()
	_canvas.name = "TouchCanvas"
	_canvas.set_anchors_preset(Control.PRESET_FULL_RECT)
	_canvas.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_canvas.draw.connect(_draw_controls)
	add_child(_canvas)
	visible = show_without_touchscreen or DisplayServer.is_touchscreen_available()
	get_viewport().size_changed.connect(_layout)
	_layout()


func _exit_tree() -> void:
	release_all()


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT or what == NOTIFICATION_APPLICATION_PAUSED:
		release_all()


func set_left_handed(value: bool) -> void:
	left_handed = value
	release_all()
	_layout()


## Releases every action and forgets all fingers (pause, focus loss, exit).
func release_all() -> void:
	for action: StringName in _held.keys():
		Input.action_release(action)
	_held.clear()
	for b: Dictionary in _buttons:
		b.finger = -1
	if not _stick.is_empty():
		_stick.finger = -1
		_stick.dir = Vector2i.ZERO
	if _canvas != null:
		_canvas.queue_redraw()


## Test/debug accessor: centre of a button by action, in viewport pixels.
## Greys out a button and makes it ignore touches (e.g. ULT without meter).
func set_action_enabled(action: StringName, enabled: bool) -> void:
	var was: bool = not _disabled.has(action)
	if enabled:
		_disabled.erase(action)
	else:
		_disabled[action] = true
		for b: Dictionary in _buttons:
			if b.action == action and b.finger != -1:
				b.finger = -1
				_release(action)
	if was != enabled and _canvas != null:
		_canvas.queue_redraw()


func is_action_enabled(action: StringName) -> bool:
	return not _disabled.has(action)


func button_center(action: StringName) -> Vector2:
	for b: Dictionary in _buttons:
		if b.action == action:
			return b.center
	return Vector2(-1, -1)


## Centre of the throw spot between the Light and Kick buttons (D-103).
func throw_spot() -> Vector2:
	var bl: Dictionary = _button(InputActions.ATTACK_LIGHT)
	var bk: Dictionary = _button(InputActions.ATTACK_KICK)
	if bl.is_empty() or bk.is_empty():
		return Vector2.INF
	return ((bl.center as Vector2) + (bk.center as Vector2)) * 0.5


func _button(action: StringName) -> Dictionary:
	for b: Dictionary in _buttons:
		if b.action == action:
			return b
	return {}


func stick_rest() -> Vector2:
	return _stick.rest


func _layout() -> void:
	var size: Vector2 = get_viewport().get_visible_rect().size
	var s: float = size.y / REF_HEIGHT * scale_factor
	var inset: Rect2 = _safe_insets(size)
	var margin: float = EDGE_MARGIN * s
	var r: float = BUTTON_RADIUS * s
	var spacing: float = r * 1.72
	# Cluster centre: bottom corner on the action side, inside the safe area.
	var cx: float = size.x - inset.size.x - margin - r - spacing
	var cy: float = size.y - inset.size.y - margin - r - spacing * 0.9
	var small: float = r * 0.75
	var defs: Array = [
		[InputActions.ATTACK_HEAVY, "H", Vector2(0, -spacing * 0.9), Color(0.9, 0.16, 0.2), r],
		[InputActions.ATTACK_LIGHT, "L", Vector2(-spacing, 0), Color(0.95, 0.74, 0.4), r],
		[InputActions.ATTACK_KICK, "K", Vector2(0, spacing * 0.9), Color(1.0, 0.45, 0.2), r],
		[InputActions.BLOCK, "BLOCK", Vector2(spacing, 0), Color(0.78, 0.8, 0.86), r],
		[InputActions.SPECIAL, "SP", Vector2(-spacing * 1.05, -spacing * 1.25), Color(1.0, 0.6, 0.3), small],
		[InputActions.ULTIMATE, "ULT", Vector2(spacing * 1.05, -spacing * 1.25), Color(1.0, 0.15, 0.1), small],
	]
	var old_fingers: Dictionary = {}
	for b: Dictionary in _buttons:
		old_fingers[b.action] = b.finger
	_buttons.clear()
	for d: Array in defs:
		var c: Vector2 = Vector2(cx, cy) + (d[2] as Vector2)
		if left_handed:
			c.x = size.x - c.x
		_buttons.append({"action": d[0], "label": d[1], "center": c, "radius": d[4],
			"color": d[3], "finger": old_fingers.get(d[0], -1)})
	var stick_r: float = STICK_RADIUS * s
	var rest := Vector2(inset.position.x + margin + stick_r * 1.4, size.y - inset.size.y - margin - stick_r * 1.4)
	var zone := Rect2(0, size.y * STICK_ZONE_TOP, size.x * STICK_ZONE_WIDTH, size.y * (1.0 - STICK_ZONE_TOP))
	if left_handed:
		rest.x = size.x - rest.x
		zone.position.x = size.x - zone.size.x
	_stick = {"zone": zone, "rest": rest, "radius": stick_r, "finger": -1,
		"origin": rest, "knob": rest, "dir": Vector2i.ZERO}
	if _canvas != null:
		_canvas.queue_redraw()


## Safe-area insets in viewport pixels: position = left/top, size = right/bottom.
func _safe_insets(vp: Vector2) -> Rect2:
	var screen: Vector2i = DisplayServer.screen_get_size()
	var safe: Rect2i = DisplayServer.get_display_safe_area()
	if screen.x <= 0 or screen.y <= 0 or safe.size.x <= 0 or safe.size.y <= 0:
		return Rect2()
	var k: Vector2 = vp / Vector2(screen)
	return Rect2(safe.position.x * k.x, safe.position.y * k.y,
		(screen.x - safe.end.x) * k.x, (screen.y - safe.end.y) * k.y)


func _input(event: InputEvent) -> void:
	if not visible:
		return
	if event is InputEventScreenTouch:
		var t := event as InputEventScreenTouch
		if t.pressed:
			if _touch_down(t.index, t.position):
				get_viewport().set_input_as_handled()
		else:
			if _touch_up(t.index):
				get_viewport().set_input_as_handled()
	elif event is InputEventScreenDrag:
		var d := event as InputEventScreenDrag
		if d.index == _stick.finger:
			_stick_move(d.position)
			get_viewport().set_input_as_handled()


func _touch_down(index: int, pos: Vector2) -> bool:
	touched.emit()
	# The spot where Light and Kick meet presses both: the throw (D-103) with
	# one thumb.
	var chord: Vector2 = throw_spot()
	var bl: Dictionary = _button(InputActions.ATTACK_LIGHT)
	var bk: Dictionary = _button(InputActions.ATTACK_KICK)
	if not bl.is_empty() and not bk.is_empty() and bl.finger == -1 and bk.finger == -1 \
			and pos.distance_to(chord) <= float(bl.radius) * THROW_SPOT_RADIUS:
		for b: Dictionary in [bl, bk]:
			b.finger = index
			_press(b.action)
		_canvas.queue_redraw()
		return true
	for b: Dictionary in _buttons:
		if _disabled.has(b.action):
			continue
		if b.finger == -1 and pos.distance_to(b.center) <= b.radius * HIT_SLOP:
			b.finger = index
			_press(b.action)
			_canvas.queue_redraw()
			return true
	if _stick.finger == -1 and (_stick.zone as Rect2).has_point(pos):
		_stick.finger = index
		_stick.origin = pos
		_stick.knob = pos
		_stick.dir = Vector2i.ZERO
		_canvas.queue_redraw()
		return true
	return false


func _touch_up(index: int) -> bool:
	var used: bool = false
	for b: Dictionary in _buttons:
		if b.finger == index:
			b.finger = -1
			_release(b.action)
			used = true
	if _stick.finger == index:
		_stick.finger = -1
		_set_stick_dir(Vector2i.ZERO)
		_stick.knob = _stick.rest
		_stick.origin = _stick.rest
		used = true
	if used:
		_canvas.queue_redraw()
	return used


func _stick_move(pos: Vector2) -> void:
	var r: float = _stick.radius
	var offset: Vector2 = (pos - _stick.origin).limit_length(r)
	_stick.knob = _stick.origin + offset
	var dir := Vector2i.ZERO
	var held: Vector2i = _stick.dir
	var sx: int = 1 if offset.x > 0.0 else -1
	var sy: int = 1 if offset.y > 0.0 else -1
	if absf(offset.x) > r * DEADZONE_X * (RELEASE_FACTOR if held.x == sx else 1.0):
		dir.x = sx
	var keep_y: float = (RELEASE_FACTOR_DOWN if sy > 0 else RELEASE_FACTOR) if held.y == sy else 1.0
	if absf(offset.y) > r * DEADZONE_Y * keep_y:   # screen y grows downward: sy > 0 is down
		dir.y = sy
	_set_stick_dir(dir)
	_canvas.queue_redraw()


func _set_stick_dir(dir: Vector2i) -> void:
	var old: Vector2i = _stick.dir
	if old == dir:
		return
	_stick.dir = dir
	_apply_axis(old.x, dir.x, InputActions.MOVE_LEFT, InputActions.MOVE_RIGHT)
	_apply_axis(old.y, dir.y, InputActions.MOVE_UP, InputActions.MOVE_DOWN)


func _apply_axis(old: int, new: int, neg: StringName, pos: StringName) -> void:
	if old == new:
		return
	if old < 0:
		_release(neg)
	elif old > 0:
		_release(pos)
	if new < 0:
		_press(neg)
	elif new > 0:
		_press(pos)


func _press(action: StringName) -> void:
	_held[action] = true
	Input.action_press(action)


func _release(action: StringName) -> void:
	if _held.erase(action):
		Input.action_release(action)


func _draw_controls() -> void:
	# "Blood Signet" pads: dark glass discs, a coloured rim with a thin inner
	# ring, display-type labels. Pressed pads fill with their colour.
	var a: float = opacity
	var glass := Color(0.03, 0.025, 0.035, 0.5 * a)
	# Stick: dark base, crimson rim, eight direction ticks, bone-white knob.
	var base: Vector2 = _stick.origin if _stick.finger != -1 else _stick.rest
	var rr: float = _stick.radius
	_canvas.draw_circle(base, rr, glass)
	_canvas.draw_arc(base, rr, 0.0, TAU, 64, Color(UiTheme.ACCENT, 0.85 * a), 5.0, true)
	_canvas.draw_arc(base, rr * 0.9, 0.0, TAU, 64, Color(1, 1, 1, 0.12 * a), 2.0, true)
	for k: int in 8:
		var d := Vector2.RIGHT.rotated(TAU * k / 8.0)
		_canvas.draw_line(base + d * rr * 0.78, base + d * rr * 0.88, Color(1, 1, 1, (0.5 if k % 2 == 0 else 0.25) * a), 3.0, true)
	var knob: Vector2 = _stick.knob if _stick.finger != -1 else _stick.rest
	var kr: float = KNOB_RADIUS * rr / STICK_RADIUS
	_canvas.draw_circle(knob, kr, Color(UiTheme.TEXT, 0.6 * a))
	_canvas.draw_arc(knob, kr, 0.0, TAU, 48, Color(UiTheme.ACCENT, 0.9 * a), 4.0, true)
	# Buttons
	for b: Dictionary in _buttons:
		var pressed: bool = b.finger != -1
		var col: Color = b.color
		if _disabled.has(b.action):
			col = Color(0.35, 0.35, 0.38)
		_canvas.draw_circle(b.center, b.radius, Color(col.darkened(0.35), 0.8 * a) if pressed else glass)
		_canvas.draw_arc(b.center, b.radius, 0.0, TAU, 64, Color(col, 0.95 * a), 6.0, true)
		_canvas.draw_arc(b.center, b.radius * 0.84, 0.0, TAU, 64, Color(col, 0.28 * a), 2.0, true)
		var fs: int = int(b.radius * (0.5 if String(b.label).length() > 2 else 0.85))
		var text_size: Vector2 = _font.get_string_size(b.label, HORIZONTAL_ALIGNMENT_CENTER, -1, fs)
		var tc: Color = Color.WHITE if pressed else col.lightened(0.35)
		_canvas.draw_string(_font, b.center + Vector2(-text_size.x * 0.5, fs * 0.32), b.label,
			HORIZONTAL_ALIGNMENT_CENTER, -1, fs, Color(tc, 0.97 * a))
	# the throw spot between Light and Kick: a small chip
	var ts: Vector2 = throw_spot()
	var bl: Dictionary = _button(InputActions.ATTACK_LIGHT)
	if ts != Vector2.INF and not bl.is_empty():
		var tr: float = float(bl.radius) * THROW_SPOT_RADIUS
		var both: bool = bl.finger != -1 and _button(InputActions.ATTACK_KICK).finger == bl.finger
		_canvas.draw_circle(ts, tr, Color(UiTheme.ACCENT.darkened(0.3), 0.85 * a) if both else glass)
		_canvas.draw_arc(ts, tr, 0.0, TAU, 32, Color(1, 1, 1, 0.55 * a), 2.5, true)
		var tfs: int = int(tr * 0.62)
		var tsz: Vector2 = _font.get_string_size("THROW", HORIZONTAL_ALIGNMENT_CENTER, -1, tfs)
		_canvas.draw_string(_font, ts + Vector2(-tsz.x * 0.5, tfs * 0.32), "THROW", HORIZONTAL_ALIGNMENT_CENTER, -1, tfs,
			Color(1, 1, 1, 0.85 * a))
