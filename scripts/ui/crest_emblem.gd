class_name CrestEmblem
extends Control
## The VANGUARD crest drawn in code (same mark as the one carved into The
## Pit's floor): a V of two blades inside a ring broken into six arcs, one
## per bloodline. The ring turns very slowly and the blade fullers glow.

@export var ring_color: Color = UiTheme.GOLD
@export var blade_color: Color = UiTheme.TEXT
@export var glow_color: Color = UiTheme.ACCENT
@export var spin_speed: float = 4.0   # degrees per second
@export var animate: bool = true

var _t: float = 0.0


func _process(delta: float) -> void:
	if animate and is_visible_in_tree():
		_t += delta
		queue_redraw()


func _draw() -> void:
	var c: Vector2 = size * 0.5
	var r: float = minf(size.x, size.y) * 0.46
	var w: float = r * 0.075
	var rot: float = deg_to_rad(_t * spin_speed)
	for i: int in 6:
		var a0: float = rot + deg_to_rad(60.0 * i + 96.0)
		draw_arc(c, r, a0, a0 + deg_to_rad(48.0), 24, ring_color, w, true)
		draw_arc(c, r - w * 1.6, a0 + 0.04, a0 + deg_to_rad(44.0), 20, Color(glow_color, 0.55), w * 0.35, true)
	var pulse: float = 0.6 + 0.4 * sin(_t * 2.2)
	for side: float in [-1.0, 1.0]:
		var hilt := c + Vector2(side * r * 0.5, -r * 0.58)
		var tip := c + Vector2(0, r * 0.66)
		var d: Vector2 = (tip - hilt).normalized()
		var n := Vector2(-d.y, d.x)
		var L: float = hilt.distance_to(tip)
		var guard := hilt + d * L * 0.16
		var blade := PackedVector2Array([
			guard + n * r * 0.075, tip, guard - n * r * 0.075])
		draw_colored_polygon(blade, blade_color)
		draw_line(guard + d * L * 0.06, tip - d * L * 0.12, Color(glow_color, pulse), maxf(1.5, r * 0.025), true)
		draw_line(guard + n * r * 0.16, guard - n * r * 0.16, ring_color, w * 0.9, true)   # cross-guard
		draw_line(hilt, guard, ring_color, w * 0.7, true)                                    # grip
