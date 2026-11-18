class_name UiTheme
extends RefCounted
## The menu look, built in code so every screen shares one source:
## dark glass panels, red Origin accent, gold for rewards, large touch
## targets sized for a landscape phone (2400×1080 reference).

const BG: Color = Color(0.03, 0.03, 0.05)
const PANEL: Color = Color(0.06, 0.065, 0.09, 0.86)
const PANEL_EDGE: Color = Color(1, 1, 1, 0.08)
const ACCENT: Color = Color(0.93, 0.17, 0.14)
const GOLD: Color = Color(1.0, 0.8, 0.42)
const TEXT: Color = Color(0.93, 0.93, 0.95)
const MUTED: Color = Color(0.62, 0.63, 0.68)
const LOCKED: Color = Color(0.4, 0.4, 0.44)

static var _theme: Theme = null


static func get_theme() -> Theme:
	if _theme == null:
		_theme = _build()
	return _theme


static func box(bg: Color, edge: Color = PANEL_EDGE, radius: int = 18, border: int = 2, pad: int = 24) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = edge
	s.set_border_width_all(border)
	s.set_corner_radius_all(radius)
	s.set_content_margin_all(pad)
	s.anti_aliasing = true
	return s


static func _build() -> Theme:
	var t := Theme.new()
	t.default_font_size = 34
	# Buttons: slanted feel via a thick accent edge on the left.
	var normal := box(Color(0.09, 0.095, 0.13, 0.92), Color(1, 1, 1, 0.1), 14, 2, 20)
	normal.border_width_left = 8
	normal.border_color = Color(0.5, 0.12, 0.1, 0.9)
	var hover := normal.duplicate() as StyleBoxFlat
	hover.bg_color = Color(0.16, 0.08, 0.09, 0.95)
	hover.border_color = ACCENT
	var pressed := hover.duplicate() as StyleBoxFlat
	pressed.bg_color = Color(0.32, 0.07, 0.07, 1.0)
	var focus := box(Color(0, 0, 0, 0), GOLD, 14, 4, 20)
	focus.draw_center = false
	var disabled := normal.duplicate() as StyleBoxFlat
	disabled.bg_color = Color(0.07, 0.07, 0.08, 0.7)
	disabled.border_color = Color(0.25, 0.25, 0.27, 0.6)
	for cls: String in ["Button", "OptionButton", "CheckButton"]:
		t.set_stylebox("normal", cls, normal)
		t.set_stylebox("hover", cls, hover)
		t.set_stylebox("pressed", cls, pressed)
		t.set_stylebox("hover_pressed", cls, pressed)
		t.set_stylebox("focus", cls, focus)
		t.set_stylebox("disabled", cls, disabled)
		t.set_color("font_color", cls, TEXT)
		t.set_color("font_hover_color", cls, Color.WHITE)
		t.set_color("font_pressed_color", cls, GOLD)
		t.set_color("font_focus_color", cls, Color.WHITE)
		t.set_color("font_disabled_color", cls, LOCKED)
	t.set_stylebox("panel", "PanelContainer", box(PANEL))
	t.set_stylebox("panel", "Panel", box(PANEL))
	t.set_color("font_color", "Label", TEXT)
	t.set_color("font_outline_color", "Label", Color(0, 0, 0, 0.7))
	t.set_constant("outline_size", "Label", 4)
	# Sliders and progress bars.
	var track := box(Color(1, 1, 1, 0.12), Color(0, 0, 0, 0), 8, 0, 0)
	track.content_margin_top = 8
	track.content_margin_bottom = 8
	var fill := box(ACCENT, Color(0, 0, 0, 0), 8, 0, 0)
	t.set_stylebox("slider", "HSlider", track)
	t.set_stylebox("grabber_area", "HSlider", fill)
	t.set_stylebox("grabber_area_highlight", "HSlider", fill)
	t.set_stylebox("background", "ProgressBar", box(Color(1, 1, 1, 0.1), Color(0, 0, 0, 0), 8, 0, 0))
	t.set_stylebox("fill", "ProgressBar", box(GOLD, Color(0, 0, 0, 0), 8, 0, 0))
	var popup := box(Color(0.07, 0.07, 0.1, 0.98), Color(1, 1, 1, 0.15), 12, 2, 12)
	t.set_stylebox("panel", "PopupMenu", popup)
	t.set_font_size("font_size", "PopupMenu", 34)
	t.set_constant("v_separation", "PopupMenu", 18)
	t.set_stylebox("panel", "ScrollContainer", StyleBoxEmpty.new())
	return t
