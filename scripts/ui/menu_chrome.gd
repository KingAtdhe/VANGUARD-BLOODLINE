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

var _t: float = 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)


func _process(delta: float) -> void:
	if animate and is_visible_in_tree():
		_t += delta
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
	# scan lines over the slab (very faint)
	var y: float = 0.0
	while y < h:
		draw_line(Vector2(bot_x, y), Vector2(w, y), Color(1, 1, 1, 0.012), 1.0)
		y += 6.0
