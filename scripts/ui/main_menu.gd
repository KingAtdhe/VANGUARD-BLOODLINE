extends MenuScreen
## Main menu ("Blood Signet" design): the crest and logo over the live
## arena with Kairo, a column of blade buttons on the angled slab — the five
## play modes as large numbered blades with a line of context each, Profile /
## Settings / Quit as a compact row — and the player card on top. Every entry
## routes (tested); the focused blade slides out and lights its index.

const MODES: Array = [
	["01", "Story", "Kairo's road to the Ascendant crown", "MenuStory"],
	["02", "Arcade", "Five fights. One Warden.", "MenuArcade"],
	["03", "Versus CPU", "Any fighter, any stage", "MenuVersus"],
	["04", "Training", "Frame data, combos, a patient dummy", "MenuTraining"],
	["05", "Survival", "How long does your bloodline last?", "MenuSurvival"],
]


func _build() -> void:
	show_back = false
	title_label.text = ""
	backdrop.show_arena(&"ascendant")
	backdrop.show_fighter(&"kairo")
	backdrop.fighter_offset = 0.42
	chrome.slab_start = 0.6
	SessionSettings.ai_difficulty = int(SaveManager.setting("ai_difficulty"))
	_build_logo()
	_build_column()


func _build_logo() -> void:
	var logo := HBoxContainer.new()
	logo.add_theme_constant_override("separation", 26)
	logo.set_anchors_preset(Control.PRESET_TOP_LEFT)
	logo.position = Vector2(0, -150)
	content.add_child(logo)
	var crest := CrestEmblem.new()
	crest.custom_minimum_size = Vector2(200, 200)
	logo.add_child(crest)
	var words := VBoxContainer.new()
	words.add_theme_constant_override("separation", -28)
	logo.add_child(words)
	var t1 := make_display("VANGUARD", 168, Color.WHITE)
	t1.add_theme_constant_override("outline_size", 10)
	words.add_child(t1)
	var spaced := FontVariation.new()
	spaced.base_font = UiTheme.display_font()
	spaced.spacing_glyph = 22
	var t2 := make_display("BLOODLINE", 70, UiTheme.ACCENT.lightened(0.15))
	t2.add_theme_font_override("font", spaced)
	t2.add_theme_constant_override("outline_size", 8)
	words.add_child(t2)
	var tag := make_label("THE ORIGIN REMEMBERS.", 24, UiTheme.MUTED)
	tag.add_theme_font_override("font", UiTheme.bold_font())
	tag.autowrap_mode = TextServer.AUTOWRAP_OFF
	var tag_gap := Control.new()
	tag_gap.custom_minimum_size = Vector2(0, 26)
	words.add_child(tag_gap)
	words.add_child(tag)
	var info := make_label("v%s  ·  %s" % [AppInfo.game_version(), AppInfo.BUILD_LABEL], 20, Color(UiTheme.MUTED, 0.7))
	info.autowrap_mode = TextServer.AUTOWRAP_OFF
	info.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	info.position = Vector2(0, -30)
	content.add_child(info)


func _build_column() -> void:
	var col := side_column(780)
	col.add_theme_constant_override("separation", 12)
	col.add_child(_player_card())
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 6)
	col.add_child(gap)
	for i: int in MODES.size():
		var m: Array = MODES[i]
		var mode: MatchSetup.Mode = [MatchSetup.Mode.STORY, MatchSetup.Mode.ARCADE, MatchSetup.Mode.VERSUS,
			MatchSetup.Mode.TRAINING, MatchSetup.Mode.SURVIVAL][i]
		var b := _blade(m[0], m[1], m[2], func() -> void: _enter(mode))
		b.name = m[3]
		col.add_child(b)
		_stagger(b, i)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	col.add_child(row)
	for e: Array in [["Profile", "MenuProfile", func() -> void: SceneRouter.goto(ScenePaths.PROFILE)],
			["Settings", "MenuSettings", func() -> void: SceneRouter.goto(ScenePaths.SETTINGS)],
			["Quit", "MenuQuit", func() -> void: get_tree().quit()]]:
		var s := make_button(e[0], e[2], Vector2(250, 76), 38)
		s.name = e[1]
		s.alignment = HORIZONTAL_ALIGNMENT_CENTER
		row.add_child(s)
	_stagger(row, MODES.size())


func _player_card() -> PanelContainer:
	var p: Dictionary = SaveManager.section("profile")
	var card := make_panel()
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 24)
	card.add_child(h)
	var lv := make_display("LV %d" % Progression.account_level(), 70, UiTheme.GOLD)
	h.add_child(lv)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 0)
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(v)
	var title := make_label(String(p["title"]).to_upper(), 28, UiTheme.TEXT)
	title.add_theme_font_override("font", UiTheme.bold_font())
	v.add_child(title)
	v.add_child(make_label("%d %s" % [int(p["currency"]), Progression.CURRENCY_NAME], 24, UiTheme.MUTED))
	return card


## A large menu blade: index, title and a line of context. The inner row
## slides out when focused or hovered.
func _blade(index: String, title: String, desc: String, on_press: Callable) -> Button:
	var b := Button.new()
	b.custom_minimum_size = Vector2(780, 104)
	b.pressed.connect(on_press)
	var inner := HBoxContainer.new()
	inner.add_theme_constant_override("separation", 22)
	inner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	inner.position = Vector2(40, 0)
	b.add_child(inner)
	var num := make_display(index, 46, Color(UiTheme.EMBER, 0.55))
	num.mouse_filter = Control.MOUSE_FILTER_IGNORE
	inner.add_child(num)
	var words := VBoxContainer.new()
	words.add_theme_constant_override("separation", -20)
	words.mouse_filter = Control.MOUSE_FILTER_IGNORE
	inner.add_child(words)
	var t := make_display(title.to_upper(), 60, UiTheme.TEXT)
	t.mouse_filter = Control.MOUSE_FILTER_IGNORE
	words.add_child(t)
	var d := make_label(desc, 21, UiTheme.MUTED)
	d.autowrap_mode = TextServer.AUTOWRAP_OFF
	d.mouse_filter = Control.MOUSE_FILTER_IGNORE
	words.add_child(d)
	var lit := func(on: bool) -> void:
		var tw := b.create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		tw.tween_property(inner, "position:x", 64.0 if on else 40.0, 0.18)
		tw.tween_property(num, "modulate", Color(1.8, 1.8, 1.8) if on else Color.WHITE, 0.18)
		d.add_theme_color_override("font_color", UiTheme.TEXT if on else UiTheme.MUTED)
	b.focus_entered.connect(lit.bind(true))
	b.focus_exited.connect(lit.bind(false))
	b.mouse_entered.connect(lit.bind(true))
	b.mouse_exited.connect(func() -> void:
		if not b.has_focus():
			lit.call(false))
	return b


## Column entries slide in one after another (presentation only).
func _stagger(c: Control, i: int) -> void:
	c.modulate.a = 0.0
	var tw := create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_interval(0.08 + i * 0.05)
	tw.tween_property(c, "modulate:a", 1.0, 0.25)


func back_scene() -> String:
	return ""


func _enter(m: MatchSetup.Mode) -> void:
	SceneRouter.goto(ModeFlow.begin(m))
