class_name MenuChrome
extends Control
## Screen dressing behind every menu: a dark angled slab under the menu
## column (so text reads over the live 3D backdrop), a crimson "Origin vein"
## along its edge with a pulse running up it, a vignette and faint scan
## lines. Purely decorative; ignores input.

## 0..1 of the screen width where the slab starts (its top edge).
@export var slab_start: float = 0.56
@export var slab_lean: float = 0.07
@export var animate: bool = true
## Embers drifting up across the screen.
@export var ember_count: int = 46

var _t: float = 0.0
var _embers: Array[Vector4] = []   # x, y (0..1), speed, size
var _wipe: float = -1.0            # entrance slash: -1 = off, 0..1 = progress


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	for i: int in ember_count:
		_embers.append(Vector4(rng.randf(), rng.randf(), rng.randf_range(0.02, 0.07), rng.randf_range(1.2, 3.4)))


## A crimson blade sweeps across the screen as a menu arrives.
func play_wipe() -> void:
	_wipe = 0.0


func _process(delta: float) -> void:
	if animate and is_visible_in_tree():
		_t += delta
		for i: int in _embers.size():
			var e: Vector4 = _embers[i]
			e.y -= e.z * delta
			e.x += sin(_t * 0.7 + i) * 0.004 * delta
			if e.y < -0.05:
				e.y = 1.05
				e.x = fposmod(e.x + 0.37, 1.0)
			_embers[i] = e
		if _wipe >= 0.0:
			_wipe += delta / 0.5
			if _wipe > 1.0:
				_wipe = -1.0
		queue_redraw()


func _draw() -> void:
	var w: float = size.x
	var h: float = size.y
	# vignette: darker towards the edges and the bottom
	var steps: int = 10
	for i: int in steps:
		var k: float = float(i) / steps
		draw_rect(Rect2(0, h * (0.62 + 0.38 * k), w, h * 0.38 / steps + 1), Color(0, 0, 0, 0.05 + 0.06 * k))
	# the slab
	var top_x: float = w * slab_start
	var bot_x: float = w * (slab_start - slab_lean)
	var slab := PackedVector2Array([Vector2(top_x, 0), Vector2(w, 0), Vector2(w, h), Vector2(bot_x, h)])
	var cols := PackedColorArray([Color(0.02, 0.018, 0.022, 0.55), Color(0.02, 0.018, 0.022, 0.86),
		Color(0.02, 0.018, 0.022, 0.86), Color(0.02, 0.018, 0.022, 0.55)])
	draw_polygon(slab, cols)
	# soft shadow edge, then the vein
	for i: int in 6:
		var o: float = float(i) * 6.0
		draw_line(Vector2(top_x - o, 0), Vector2(bot_x - o, h), Color(0, 0, 0, 0.08), 6.0)
	draw_line(Vector2(top_x, 0), Vector2(bot_x, h), Color(UiTheme.ACCENT, 0.85), 3.0, true)
	draw_line(Vector2(top_x + 10, 0), Vector2(bot_x + 10, h), Color(UiTheme.ACCENT, 0.25), 1.0, true)
	var p: float = fmod(_t * 0.35, 1.3) - 0.15        # a pulse travelling up the vein
	for j: int in 12:
		var q: float = p - j * 0.012
		if q < 0.0 or q > 1.0:
			continue
		var pt: Vector2 = Vector2(bot_x, h).lerp(Vector2(top_x, 0), q)
		draw_circle(pt, 7.0 - j * 0.5, Color(UiTheme.EMBER, 0.55 - j * 0.045))
	# embers
	for i: int in _embers.size():
		var e: Vector4 = _embers[i]
		var flick: float = 0.55 + 0.45 * sin(_t * 3.0 + i * 1.7)
		var col: Color = UiTheme.EMBER if i % 3 else UiTheme.GOLD
		draw_circle(Vector2(e.x * w, e.y * h), e.w * 2.2, Color(col, 0.08 * flick))
		draw_circle(Vector2(e.x * w, e.y * h), e.w * 0.7, Color(col, 0.75 * flick))
	# entrance wipe: a slanted crimson band crossing left to right, then gone
	if _wipe >= 0.0:
		var e2: float = ease(_wipe, 0.4)
		var x0: float = lerpf(-0.5 * w, 1.3 * w, e2)
		var band := PackedVector2Array([Vector2(x0, 0), Vector2(x0 + 0.18 * w, 0),
			Vector2(x0 + 0.06 * w, h), Vector2(x0 - 0.12 * w, h)])
		draw_colored_polygon(band, Color(UiTheme.ACCENT, 0.85 * (1.0 - _wipe)))
		draw_line(Vector2(x0 + 0.18 * w, 0), Vector2(x0 + 0.06 * w, h), Color(UiTheme.EMBER, 1.0 - _wipe), 4.0)
	# scan lines over the slab (very faint)
	var y: float = 0.0
	while y < h:
		draw_line(Vector2(bot_x, y), Vector2(w, y), Color(1, 1, 1, 0.012), 1.0)
		y += 6.0
