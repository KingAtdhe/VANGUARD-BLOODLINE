class_name MenuScreen
extends Control
## Base for every menu screen: shared theme, live 3D backdrop, safe-area
## margins, a header (title + Back), and back handling for Esc, gamepad B
## and the Android back gesture. Subclasses fill [member content] in
## _build() and say where Back leads in back_scene().
##
## Navigation contract (tested in test_navigation): every MenuScreen except
## the main menu returns a non-empty back_scene(), so no screen is a dead end.

var backdrop: MenuBackdrop
var safe: MarginContainer
var header: HBoxContainer
var title_label: Label
var back_button: Button
var content: Control
## Set by subclasses that don't want a Back button (main menu).
var show_back: bool = true


func _ready() -> void:
	SaveManager.ensure_loaded()
	theme = UiTheme.get_theme()
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = UiTheme.BG
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	backdrop = MenuBackdrop.new()
	add_child(backdrop)
	var shade := TextureRect.new()   # darkens the UI side for legibility
	shade.texture = _gradient_texture()
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.stretch_mode = TextureRect.STRETCH_SCALE
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(shade)
	safe = MarginContainer.new()
	safe.set_anchors_preset(Control.PRESET_FULL_RECT)
	safe.set_script(load("res://scripts/ui/safe_area_margin.gd"))
	add_child(safe)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 24)
	safe.add_child(col)
	header = HBoxContainer.new()
	header.add_theme_constant_override("separation", 28)
	col.add_child(header)
	back_button = Button.new()
	back_button.name = "BackButton"
	back_button.text = "‹  Back"
	back_button.custom_minimum_size = Vector2(240, 96)
	back_button.pressed.connect(go_back)
	header.add_child(back_button)
	title_label = Label.new()
	title_label.add_theme_font_size_override("font_size", 64)
	title_label.add_theme_color_override("font_color", Color.WHITE)
	title_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	header.add_child(title_label)
	content = Control.new()
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(content)
	_build()
	back_button.visible = show_back
	_focus_first()


## Override: populate [member content].
func _build() -> void:
	pass


## Override: where Back leads ("" = nowhere, main menu only).
func back_scene() -> String:
	return ScenePaths.MAIN_MENU


## Override for screens that must tidy up a run before leaving.
func go_back() -> void:
	var target: String = back_scene()
	if target != "":
		SceneRouter.goto(target)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(&"ui_cancel") and show_back:
		get_viewport().set_input_as_handled()
		go_back()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_GO_BACK_REQUEST and show_back:
		go_back()


func _focus_first() -> void:
	for n: Node in content.find_children("*", "Button", true, false):
		var b := n as Button
		if b.visible and not b.disabled:
			b.grab_focus.call_deferred()
			return


# --- widgets ------------------------------------------------------------------------

static func make_button(text: String, on_press: Callable, min_size: Vector2 = Vector2(560, 104), font: int = 40) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = min_size
	b.add_theme_font_size_override("font_size", font)
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	if on_press.is_valid():
		b.pressed.connect(on_press)
	return b


static func make_label(text: String, size: int = 34, color: Color = UiTheme.TEXT) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return l


static func make_panel(min_size: Vector2 = Vector2.ZERO) -> PanelContainer:
	var p := PanelContainer.new()
	p.custom_minimum_size = min_size
	return p


## Right-side column anchored inside [member content], width [param w] px.
func side_column(w: float, right: bool = true) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 18)
	if right:
		v.set_anchors_preset(Control.PRESET_RIGHT_WIDE)
		v.offset_left = -w
	else:
		v.set_anchors_preset(Control.PRESET_LEFT_WIDE)
		v.offset_right = w
	content.add_child(v)
	return v


static func _gradient_texture() -> GradientTexture2D:
	var g := Gradient.new()
	g.set_color(0, Color(0, 0, 0, 0.0))
	g.set_color(1, Color(0, 0, 0, 0.78))
	g.set_offset(0, 0.25)
	g.set_offset(1, 0.75)
	var t := GradientTexture2D.new()
	t.gradient = g
	t.width = 256
	t.height = 4
	return t
