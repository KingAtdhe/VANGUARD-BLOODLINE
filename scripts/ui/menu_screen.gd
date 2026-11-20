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
var chrome: MenuChrome
var eyebrow: Label
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
	chrome = MenuChrome.new()          # angled slab + Origin vein behind the menu column
	add_child(chrome)
	safe = MarginContainer.new()
	safe.set_anchors_preset(Control.PRESET_FULL_RECT)
	safe.set_script(load("res://scripts/ui/safe_area_margin.gd"))
	add_child(safe)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 24)
	safe.add_child(col)
	header = HBoxContainer.new()
	header.add_theme_constant_override("separation", 36)
	col.add_child(header)
	back_button = Button.new()
	back_button.name = "BackButton"
	back_button.text = "◂  BACK"
	back_button.custom_minimum_size = Vector2(230, 92)
	back_button.add_theme_font_size_override("font_size", 40)
	back_button.pressed.connect(go_back)
	header.add_child(back_button)
	var titles := VBoxContainer.new()
	titles.add_theme_constant_override("separation", -10)
	titles.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(titles)
	eyebrow = make_label("VANGUARD  //  BLOODLINE", 22, UiTheme.EMBER)
	eyebrow.add_theme_font_override("font", UiTheme.bold_font())
	eyebrow.autowrap_mode = TextServer.AUTOWRAP_OFF
	titles.add_child(eyebrow)
	title_label = make_display("", 96, Color.WHITE)
	titles.add_child(title_label)
	var bar := ColorRect.new()                 # crimson slash under the title
	bar.color = UiTheme.ACCENT
	bar.custom_minimum_size = Vector2(140, 6)
	bar.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	titles.add_child(bar)
	content = Control.new()
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(content)
	_build()
	back_button.visible = show_back
	eyebrow.visible = title_label.text != ""
	_focus_first()
	_intro()


## Screens arrive with a short slide/fade (presentation only).
func _intro() -> void:
	if not is_inside_tree():
		return
	content.modulate.a = 0.0
	header.modulate.a = 0.0
	var tw := create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(header, "modulate:a", 1.0, 0.25)
	tw.tween_property(content, "modulate:a", 1.0, 0.35).set_delay(0.05)


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

static func make_button(text: String, on_press: Callable, min_size: Vector2 = Vector2(560, 104), font: int = 44) -> Button:
	var b := Button.new()
	b.text = text.to_upper()
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


## Display type (Teko): titles, names, big numbers.
static func make_display(text: String, size: int = 64, color: Color = Color.WHITE) -> Label:
	var l := make_label(text, size, color)
	l.add_theme_font_override("font", UiTheme.display_font())
	l.autowrap_mode = TextServer.AUTOWRAP_OFF
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
