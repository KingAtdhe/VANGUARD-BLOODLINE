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
	chrome.play_wipe()
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


## Small-caps caption over a big display value, in an angled tile.
static func stat_tile(caption: String, value: String, color: Color = Color.WHITE, min_w: float = 0.0,
		value_size: int = 76) -> PanelContainer:
	var p := PanelContainer.new()
	p.custom_minimum_size = Vector2(min_w, 0)
	p.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", -8)
	p.add_child(v)
	var c := make_label(caption.to_upper(), 22, UiTheme.MUTED)
	c.add_theme_font_override("font", UiTheme.bold_font())
	v.add_child(c)
	v.add_child(make_display(value, value_size, color))
	var st := (UiTheme.get_theme().get_stylebox("panel", "PanelContainer") as StyleBoxFlat).duplicate() as StyleBoxFlat
	st.content_margin_top = 12
	st.content_margin_bottom = 8
	p.add_theme_stylebox_override("panel", st)
	return p


## Coloured tag ("BOSS", "CLEARED", "LOCKED") on a skewed chip.
static func make_chip(text: String, color: Color) -> PanelContainer:
	var chip := PanelContainer.new()
	var st := UiTheme.box(Color(color, 0.22), color, 0, 2, 10, UiTheme.SKEW)
	st.content_margin_top = 2
	st.content_margin_bottom = 2
	st.content_margin_left = 18
	st.content_margin_right = 18
	chip.add_theme_stylebox_override("panel", st)
	var l := make_label(text.to_upper(), 24, color.lightened(0.25))
	l.add_theme_font_override("font", UiTheme.bold_font())
	l.autowrap_mode = TextServer.AUTOWRAP_OFF
	chip.add_child(l)
	chip.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return chip


## A card: big index on the left ("01"), title and a line of context, an
## optional chip on the right. A Button when [param on_press] is valid
## (focusable, themed blade), otherwise a static panel. [param emphasis]
## marks the current item (crimson body, gold index).
static func make_card(index: String, title: String, subtitle: String, chip: String = "",
		chip_color: Color = UiTheme.ACCENT, on_press: Callable = Callable(),
		min_size: Vector2 = Vector2(900, 110), emphasis: bool = false, dim: bool = false) -> Control:
	var root: Control
	if on_press.is_valid():
		var b := Button.new()
		b.pressed.connect(on_press)
		root = b
	else:
		var pnl := PanelContainer.new()
		pnl.add_theme_stylebox_override("panel", UiTheme.get_theme().get_stylebox("normal", "Button"))
		root = pnl
	root.custom_minimum_size = min_size
	# cards set their own height: thin vertical padding instead of the blade's 22 px
	var th: Theme = UiTheme.get_theme()
	for state: String in (["normal", "hover", "pressed", "hover_pressed", "focus", "disabled"] if root is Button else ["panel"]):
		var src: StyleBox = th.get_stylebox("normal" if state == "panel" else state, "Button")
		var sb := src.duplicate() as StyleBox
		sb.content_margin_top = 6
		sb.content_margin_bottom = 6
		root.add_theme_stylebox_override(state, sb)
	if emphasis:
		var em := (UiTheme.get_theme().get_stylebox("hover", "Button") as StyleBoxFlat).duplicate() as StyleBoxFlat
		em.content_margin_top = 6
		em.content_margin_bottom = 6
		root.add_theme_stylebox_override("normal" if root is Button else "panel", em)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 26)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if root is Button:
		row.set_anchors_preset(Control.PRESET_FULL_RECT)
		row.offset_left = 34
		row.offset_right = -30
	root.add_child(row)
	var fade: Color = Color(1, 1, 1, 0.45) if dim else Color.WHITE
	var h: float = min_size.y
	var idx := make_display(index, int(h * 0.62), (UiTheme.GOLD if emphasis else UiTheme.ACCENT) * fade)
	idx.custom_minimum_size = Vector2(h * 0.8, 0)
	idx.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(idx)
	var texts := VBoxContainer.new()
	texts.add_theme_constant_override("separation", -6)
	texts.alignment = BoxContainer.ALIGNMENT_CENTER
	texts.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	texts.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(texts)
	var t := make_display(title.to_upper(), int(h * 0.4), Color.WHITE * fade)
	t.clip_text = true
	texts.add_child(t)
	if subtitle != "":
		var sub := make_label(subtitle, clampi(int(h * 0.22), 18, 24), UiTheme.MUTED * fade)
		sub.autowrap_mode = TextServer.AUTOWRAP_OFF
		sub.clip_text = true
		texts.add_child(sub)
	if chip != "":
		row.add_child(make_chip(chip, chip_color))
	for n: Node in row.find_children("*", "Control", true, false):
		(n as Control).mouse_filter = Control.MOUSE_FILTER_IGNORE
	return root


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
