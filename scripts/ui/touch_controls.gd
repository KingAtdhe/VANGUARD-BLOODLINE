class_name TouchControls
extends CanvasLayer
## Multi-touch fighting controls (spec §2.4).
##
##   - Floating stick: touch anywhere in the stick zone (outer ~33 % of the
##     screen, below the HUD); drag left/right to walk, up/down for
##     jump/crouch actions (not used by gameplay yet).
##   - Action cluster: Light, Heavy, Kick, Block — fire on touch-DOWN, stay
##     held while that finger stays down (even if it slides off).
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


func _ready() -> void:
	_font = ThemeDB.fallback_font
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
func button_center(action: StringName) -> Vector2:
	for b: Dictionary in _buttons:
		if b.action == action:
			return b.center
	return Vector2(-1, -1)


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
	var defs: Array = [
		[InputActions.ATTACK_HEAVY, "H", Vector2(0, -spacing * 0.9), Color(0.95, 0.35, 0.25)],
		[InputActions.ATTACK_LIGHT, "L", Vector2(-spacing, 0), Color(0.95, 0.8, 0.3)],
		[InputActions.ATTACK_KICK, "K", Vector2(0, spacing * 0.9), Color(0.4, 0.85, 0.45)],
		[InputActions.BLOCK, "BLOCK", Vector2(spacing, 0), Color(0.45, 0.7, 1.0)],
	]
	var old_fingers: Dictionary = {}
	for b: Dictionary in _buttons:
		old_fingers[b.action] = b.finger
	_buttons.clear()
	for d: Array in defs:
		var c: Vector2 = Vector2(cx, cy) + (d[2] as Vector2)
		if left_handed:
			c.x = size.x - c.x
		_buttons.append({"action": d[0], "label": d[1], "center": c, "radius": r,
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
	for b: Dictionary in _buttons:
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
	if absf(offset.x) > r * DEADZONE_X:
		dir.x = 1 if offset.x > 0.0 else -1
	if absf(offset.y) > r * DEADZONE_Y:
		dir.y = 1 if offset.y > 0.0 else -1
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
	var a: float = opacity
	# Stick
	var base: Vector2 = _stick.origin if _stick.finger != -1 else _stick.rest
	_canvas.draw_circle(base, _stick.radius, Color(1, 1, 1, 0.12 * a))
	_canvas.draw_arc(base, _stick.radius, 0.0, TAU, 48, Color(1, 1, 1, 0.6 * a), 4.0)
	var knob: Vector2 = _stick.knob if _stick.finger != -1 else _stick.rest
	_canvas.draw_circle(knob, KNOB_RADIUS * _stick.radius / STICK_RADIUS, Color(1, 1, 1, 0.55 * a))
	# Buttons
	for b: Dictionary in _buttons:
		var pressed: bool = b.finger != -1
		var col: Color = b.color
		_canvas.draw_circle(b.center, b.radius, Color(col, (0.75 if pressed else 0.3) * a))
		_canvas.draw_arc(b.center, b.radius, 0.0, TAU, 48, Color(col.lightened(0.3), 0.9 * a), 5.0)
		var fs: int = int(b.radius * (0.38 if String(b.label).length() > 2 else 0.6))
		var text_size: Vector2 = _font.get_string_size(b.label, HORIZONTAL_ALIGNMENT_CENTER, -1, fs)
		_canvas.draw_string(_font, b.center + Vector2(-text_size.x * 0.5, fs * 0.35), b.label,
			HORIZONTAL_ALIGNMENT_CENTER, -1, fs, Color(1, 1, 1, 0.95 * a))
