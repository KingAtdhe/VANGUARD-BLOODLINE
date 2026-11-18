extends MenuScreen
## Main menu (Milestone 7): every launch mode, profile, settings and quit,
## over a live arena backdrop with Kairo. Shows account level, title and
## currency. Nothing here is a placeholder button: each entry routes.


func _build() -> void:
	show_back = false
	title_label.text = ""
	backdrop.show_arena(&"ascendant")
	backdrop.show_fighter(&"kairo")
	backdrop.fighter_offset = 1.25
	SessionSettings.ai_difficulty = int(SaveManager.setting("ai_difficulty"))

	var logo := VBoxContainer.new()
	logo.set_anchors_preset(Control.PRESET_TOP_LEFT)
	logo.position = Vector2(0, -60)
	content.add_child(logo)
	var t1 := make_label("VANGUARD", 132, Color.WHITE)
	t1.autowrap_mode = TextServer.AUTOWRAP_OFF
	t1.add_theme_constant_override("outline_size", 14)
	logo.add_child(t1)
	var t2 := make_label("B L O O D L I N E", 52, UiTheme.ACCENT)
	t2.autowrap_mode = TextServer.AUTOWRAP_OFF
	logo.add_child(t2)

	var col := side_column(720)
	col.add_theme_constant_override("separation", 10)
	var p: Dictionary = SaveManager.section("profile")
	var badge := make_panel()
	var bl := VBoxContainer.new()
	badge.add_child(bl)
	bl.add_child(make_label("Lv %d  ·  %s" % [Progression.account_level(), p["title"]], 36, UiTheme.GOLD))
	bl.add_child(make_label("%d %s" % [int(p["currency"]), Progression.CURRENCY_NAME], 30, UiTheme.MUTED))
	col.add_child(badge)
	var entries: Array = [
		["Story", "MenuStory", func() -> void: _enter(MatchSetup.Mode.STORY)],
		["Arcade", "MenuArcade", func() -> void: _enter(MatchSetup.Mode.ARCADE)],
		["Versus CPU", "MenuVersus", func() -> void: _enter(MatchSetup.Mode.VERSUS)],
		["Training", "MenuTraining", func() -> void: _enter(MatchSetup.Mode.TRAINING)],
		["Survival", "MenuSurvival", func() -> void: _enter(MatchSetup.Mode.SURVIVAL)],
		["Profile", "MenuProfile", func() -> void: SceneRouter.goto(ScenePaths.PROFILE)],
		["Settings", "MenuSettings", func() -> void: SceneRouter.goto(ScenePaths.SETTINGS)],
		["Quit", "MenuQuit", func() -> void: get_tree().quit()],
	]
	for e: Array in entries:
		var b := make_button(e[0], e[2], Vector2(720, 68), 34)
		b.name = e[1]
		col.add_child(b)
	var info := make_label("v%s  ·  %s" % [AppInfo.game_version(), AppInfo.BUILD_LABEL], 22, UiTheme.MUTED)
	info.autowrap_mode = TextServer.AUTOWRAP_OFF
	logo.add_child(info)


func back_scene() -> String:
	return ""


func _enter(m: MatchSetup.Mode) -> void:
	SceneRouter.goto(ModeFlow.begin(m))
