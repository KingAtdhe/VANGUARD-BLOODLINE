class_name SafeAreaMargin
extends MarginContainer
## Keeps children inside the device safe area (notches, cutouts, nav bars)
## plus a minimum margin away from system gesture edges.

## Minimum margin in viewport pixels, applied even when the safe area is full-screen.
@export var minimum_margin: int = 48


func _ready() -> void:
	get_viewport().size_changed.connect(_apply_safe_area)
	_apply_safe_area()


func _apply_safe_area() -> void:
	var viewport_size: Vector2 = get_viewport_rect().size
	var screen_size: Vector2i = DisplayServer.screen_get_size()
	var safe: Rect2i = DisplayServer.get_display_safe_area()

	var left: float = 0.0
	var top: float = 0.0
	var right: float = 0.0
	var bottom: float = 0.0
	# Safe area is reported in screen pixels; convert to viewport units.
	if screen_size.x > 0 and screen_size.y > 0 and safe.size.x > 0 and safe.size.y > 0:
		var scale: Vector2 = viewport_size / Vector2(screen_size)
		left = safe.position.x * scale.x
		top = safe.position.y * scale.y
		right = (screen_size.x - safe.end.x) * scale.x
		bottom = (screen_size.y - safe.end.y) * scale.y

	add_theme_constant_override("margin_left", maxi(minimum_margin, int(left)))
	add_theme_constant_override("margin_top", maxi(minimum_margin, int(top)))
	add_theme_constant_override("margin_right", maxi(minimum_margin, int(right)))
	add_theme_constant_override("margin_bottom", maxi(minimum_margin, int(bottom)))
