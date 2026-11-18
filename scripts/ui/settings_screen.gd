extends MenuScreen
## Settings (spec §8.4 accessibility + controls). Every change is saved at
## once (SaveManager) and applied by the combat scene at match start.

var _reset_armed: bool = false
var _reset_button: Button
var controls: Dictionary = {}   # key -> Control (tests)


func _build() -> void:
	title_label.text = "SETTINGS"
	backdrop.show_arena(&"temple")
	var scroll := ScrollContainer.new()
	scroll.set_anchors_preset(Control.PRESET_FULL_RECT)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	content.add_child(scroll)
	var cols := HBoxContainer.new()
	cols.add_theme_constant_override("separation", 40)
	cols.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(cols)
	var left := _section(cols, "CONTROLS")
	_toggle(left, "left_handed", "Left-handed layout")
	_choice(left, "touch_controls", "Touch controls", ["Auto", "Always", "Never"])
	_slider(left, "controls_scale", "Button size", 0.7, 1.4, 0.05, "%d%%", 100.0)
	_slider(left, "controls_opacity", "Button opacity", 0.2, 1.0, 0.05, "%d%%", 100.0)
	var mid := _section(cols, "AUDIO & VIDEO")
	_slider(mid, "master_volume", "Master volume", 0.0, 1.0, 0.05, "%d%%", 100.0)
	_slider(mid, "sfx_volume", "Effects volume", 0.0, 1.0, 0.05, "%d%%", 100.0)
	_toggle(mid, "reduced_shake", "Reduce screen shake")
	_toggle(mid, "cinematics", "Ultimate cinematics")
	_toggle(mid, "reduced_effects", "Reduce arena effects (battery)")
	var right := _section(cols, "GAMEPLAY & DATA")
	_choice(right, "ai_difficulty", "Versus CPU", SessionSettings.AI_DIFFICULTY_NAMES)
	right.add_child(make_label("Progress is saved on this device automatically.", 26, UiTheme.MUTED))
	_reset_button = make_button("Reset all progress", _reset_pressed, Vector2(600, 96), 34)
	_reset_button.name = "ResetButton"
	right.add_child(_reset_button)


func back_scene() -> String:
	return ScenePaths.MAIN_MENU


func _section(parent: Control, title: String) -> VBoxContainer:
	var p := make_panel(Vector2(680, 0))
	p.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	parent.add_child(p)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 18)
	p.add_child(v)
	v.add_child(make_label(title, 34, UiTheme.ACCENT))
	return v


func _toggle(parent: Control, key: String, text: String) -> void:
	var c := CheckButton.new()
	c.name = "Setting_" + key
	c.text = text
	c.custom_minimum_size = Vector2(620, 84)
	c.add_theme_font_size_override("font_size", 32)
	c.button_pressed = bool(SaveManager.setting(key))
	c.toggled.connect(func(on: bool) -> void: SaveManager.set_setting(key, on))
	parent.add_child(c)
	controls[key] = c


func _choice(parent: Control, key: String, text: String, options: Array) -> void:
	parent.add_child(make_label(text, 30, UiTheme.MUTED))
	var o := OptionButton.new()
	o.name = "Setting_" + key
	o.custom_minimum_size = Vector2(620, 84)
	o.add_theme_font_size_override("font_size", 32)
	for opt: String in options:
		o.add_item(opt)
	o.selected = int(SaveManager.setting(key))
	o.item_selected.connect(func(i: int) -> void:
		SaveManager.set_setting(key, i)
		if key == "ai_difficulty":
			SessionSettings.ai_difficulty = i)
	parent.add_child(o)
	controls[key] = o


func _slider(parent: Control, key: String, text: String, lo: float, hi: float, step: float, fmt: String, mul: float) -> void:
	var lbl := make_label("", 30, UiTheme.MUTED)
	parent.add_child(lbl)
	var s := HSlider.new()
	s.name = "Setting_" + key
	s.min_value = lo
	s.max_value = hi
	s.step = step
	s.custom_minimum_size = Vector2(620, 56)
	s.value = float(SaveManager.setting(key))
	var show := func(v: float) -> void: lbl.text = "%s   %s" % [text, fmt % int(round(v * mul))]
	show.call(s.value)
	s.value_changed.connect(func(v: float) -> void:
		show.call(v)
		SaveManager.set_setting(key, v))
	parent.add_child(s)
	controls[key] = s


## Two-step confirmation: destructive actions never happen on one tap.
func _reset_pressed() -> void:
	if not _reset_armed:
		_reset_armed = true
		_reset_button.text = "Tap again to erase everything"
		return
	SaveManager.reset_all()
	SessionSettings.ai_difficulty = int(SaveManager.setting("ai_difficulty"))
	SceneRouter.goto(ScenePaths.SETTINGS)
