class_name UiTheme
extends RefCounted
## The menu look ("Blood Signet"), built in code so every screen shares one
## source. Angled blade buttons and panels (StyleBoxFlat skew), a crimson
## Origin accent with ember and gold for highlights and rewards, Teko for
## display type and Chakra Petch for body text (both SIL OFL, see
## LICENSES.md). Sized for a landscape phone (2400×1080 reference).

const BG: Color = Color(0.025, 0.022, 0.028)
const PANEL: Color = Color(0.06, 0.055, 0.065, 0.9)
const PANEL_EDGE: Color = Color(1, 1, 1, 0.07)
const ACCENT: Color = Color(0.86, 0.11, 0.16)        # Origin crimson
const ACCENT_DEEP: Color = Color(0.36, 0.04, 0.06)
const EMBER: Color = Color(1.0, 0.45, 0.2)
const GOLD: Color = Color(0.95, 0.74, 0.4)
const TEXT: Color = Color(0.95, 0.93, 0.9)           # bone white
const MUTED: Color = Color(0.62, 0.59, 0.6)
const LOCKED: Color = Color(0.38, 0.36, 0.38)
## Horizontal skew of blades: the top edge leans right, like a cut.
const SKEW: float = -0.28

const FONT_DISPLAY_PATH: String = "res://assets/fonts/Teko-SemiBold.woff2"
const FONT_BODY_PATH: String = "res://assets/fonts/ChakraPetch-Medium.woff2"
const FONT_BOLD_PATH: String = "res://assets/fonts/ChakraPetch-Bold.woff2"

static var _theme: Theme = null
static var _display: Font = null
static var _body: Font = null
static var _bold: Font = null


static func get_theme() -> Theme:
	if _theme == null:
		_theme = _build()
	return _theme


static func display_font() -> Font:
	if _display == null:
		_display = _load_font(FONT_DISPLAY_PATH)
	return _display


static func body_font() -> Font:
	if _body == null:
		_body = _load_font(FONT_BODY_PATH)
	return _body


static func bold_font() -> Font:
	if _bold == null:
		_bold = _load_font(FONT_BOLD_PATH)
	return _bold


## In-match overlays (pause, results) built as scenes: give them the menu
## theme, blade buttons with upper-case labels, display type for big titles,
## and the angled crimson-edged panel.
static func apply_overlay(root: Node) -> void:
	for c: Node in root.get_children():
		if c is Control:
			(c as Control).theme = get_theme()
	for n: Node in root.find_children("*", "", true, false):
		if n is Button:
			(n as Button).text = (n as Button).text.to_upper()
		elif n is Label and (n as Label).get_theme_font_size("font_size") >= 72:
			(n as Label).add_theme_font_override("font", display_font())
		elif n is PanelContainer:
			(n as PanelContainer).remove_theme_stylebox_override("panel")


static func _load_font(path: String) -> Font:
	if ResourceLoader.exists(path):
		var f: Font = load(path)
		if f != null:
			return f
	return ThemeDB.fallback_font


## Flat box. [param skew] > 0 leans the shape (blade); 0 = upright panel.
static func box(bg: Color, edge: Color = PANEL_EDGE, radius: int = 0, border: int = 1, pad: int = 24,
		skew: float = 0.0) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = edge
	s.set_border_width_all(border)
	s.set_corner_radius_all(radius)
	s.set_content_margin_all(pad)
	s.skew = Vector2(skew, 0)
	s.anti_aliasing = true
	return s


static func _build() -> Theme:
	var t := Theme.new()
	t.default_font = body_font()
	t.default_font_size = 32
	var normal := box(Color(0.075, 0.068, 0.08, 0.9), Color(1, 1, 1, 0.07), 0, 1, 22, SKEW)
	normal.border_width_left = 6
	normal.border_color = Color(0.45, 0.07, 0.09, 0.95)
	var hover := normal.duplicate() as StyleBoxFlat
	hover.bg_color = Color(0.24, 0.04, 0.06, 0.95)
	hover.border_width_left = 12
	hover.border_color = ACCENT
	var pressed := hover.duplicate() as StyleBoxFlat
	pressed.bg_color = ACCENT
	pressed.border_color = EMBER
	var focus := box(Color(0, 0, 0, 0), EMBER, 0, 3, 22, SKEW)
	focus.draw_center = false
	focus.expand_margin_left = 2
	focus.expand_margin_right = 2
	var disabled := normal.duplicate() as StyleBoxFlat
	disabled.bg_color = Color(0.05, 0.05, 0.055, 0.7)
	disabled.border_color = Color(0.22, 0.2, 0.22, 0.6)
	for cls: String in ["Button", "OptionButton", "CheckButton"]:
		t.set_stylebox("normal", cls, normal)
		t.set_stylebox("hover", cls, hover)
		t.set_stylebox("pressed", cls, pressed)
		t.set_stylebox("hover_pressed", cls, pressed)
		t.set_stylebox("focus", cls, focus)
		t.set_stylebox("disabled", cls, disabled)
		t.set_font("font", cls, display_font())
		t.set_font_size("font_size", cls, 44)
		t.set_color("font_color", cls, TEXT)
		t.set_color("font_hover_color", cls, Color.WHITE)
		t.set_color("font_pressed_color", cls, Color.WHITE)
		t.set_color("font_focus_color", cls, Color.WHITE)
		t.set_color("font_disabled_color", cls, LOCKED)
	var panel := box(PANEL, PANEL_EDGE, 0, 1, 28, SKEW * 0.25)
	panel.border_width_top = 3
	panel.border_color = Color(ACCENT, 0.85)
	t.set_stylebox("panel", "PanelContainer", panel)
	t.set_stylebox("panel", "Panel", panel)
	t.set_color("font_color", "Label", TEXT)
	t.set_color("font_outline_color", "Label", Color(0, 0, 0, 0.6))
	t.set_constant("outline_size", "Label", 3)
	# Sliders and progress bars: thin, sharp, crimson.
	var track := box(Color(1, 1, 1, 0.1), Color(0, 0, 0, 0), 0, 0, 0)
	track.content_margin_top = 6
	track.content_margin_bottom = 6
	var fill := box(ACCENT, Color(0, 0, 0, 0), 0, 0, 0)
	t.set_stylebox("slider", "HSlider", track)
	t.set_stylebox("grabber_area", "HSlider", fill)
	t.set_stylebox("grabber_area_highlight", "HSlider", box(EMBER, Color(0, 0, 0, 0), 0, 0, 0))
	t.set_stylebox("background", "ProgressBar", box(Color(1, 1, 1, 0.08), Color(0, 0, 0, 0), 0, 0, 0, SKEW))
	t.set_stylebox("fill", "ProgressBar", box(GOLD, Color(0, 0, 0, 0), 0, 0, 0, SKEW))
	var popup := box(Color(0.06, 0.055, 0.065, 0.98), Color(ACCENT, 0.6), 0, 2, 14)
	t.set_stylebox("panel", "PopupMenu", popup)
	t.set_stylebox("hover", "PopupMenu", box(ACCENT_DEEP, Color(0, 0, 0, 0), 0, 0, 8))
	t.set_font_size("font_size", "PopupMenu", 34)
	t.set_constant("v_separation", "PopupMenu", 18)
	t.set_stylebox("panel", "ScrollContainer", StyleBoxEmpty.new())
	return t
