extends MenuScreen
## Profile: account level, currency, title (cosmetic, chosen from those
## earned), fighter mastery, mode records and statistics.


func _build() -> void:
	title_label.text = "PROFILE"
	backdrop.show_arena(&"ascendant")
	backdrop.show_fighter(&"kairo")
	backdrop.fighter_offset = 1.3
	var col := side_column(1000)
	var p: Dictionary = SaveManager.section("profile")
	var xp: int = int(p["account_xp"])
	col.add_child(make_label("Account level %d" % Progression.account_level(), 52, Color.WHITE))
	var prog: Vector2i = Progression.level_progress(xp)
	var bar := ProgressBar.new()
	bar.custom_minimum_size = Vector2(1000, 30)
	bar.max_value = prog.y
	bar.value = prog.x
	bar.show_percentage = false
	col.add_child(bar)
	col.add_child(make_label("%d / %d XP to next level   ·   %d %s" % [prog.x, prog.y, int(p["currency"]),
		Progression.CURRENCY_NAME], 30, UiTheme.MUTED))
	col.add_child(make_label("Title", 30, UiTheme.MUTED))
	var titles := OptionButton.new()
	titles.name = "TitleOption"
	titles.custom_minimum_size = Vector2(1000, 84)
	var owned: Array = p["titles"]
	for i: int in owned.size():
		titles.add_item(String(owned[i]))
		if owned[i] == p["title"]:
			titles.selected = i
	titles.item_selected.connect(func(i: int) -> void:
		p["title"] = owned[i]
		SaveManager.save())
	col.add_child(titles)
	var stats: Dictionary = SaveManager.section("stats")
	var progress: Dictionary = SaveManager.section("progress")
	var lines: PackedStringArray = [
		"Story: %d / %d chapters" % [int(progress["story_cleared"]), ModeFlow.story_chapters().size()],
		"Arcade: %d clears · best score %d" % [int(progress["arcade_clears"]), int(progress["arcade_best_score"])],
		"Survival: best %d defeated · %d points" % [int(progress["survival_best_wins"]), int(progress["survival_best_score"])],
		"Matches %d · Wins %d · Losses %d · Draws %d · Perfect rounds %d" % [int(stats["matches"]),
			int(stats["wins"]), int(stats["losses"]), int(stats["draws"]), int(stats["perfect_rounds"])],
	]
	var mastery: PackedStringArray = []
	for id: StringName in Catalog.ROSTER:
		if Catalog.fighter(id).playable:
			mastery.append("%s mastery Lv %d" % [Catalog.fighter(id).display_name, Progression.mastery_level(id)])
	lines.append(" · ".join(mastery))
	var panel := make_panel()
	panel.add_child(make_label("\n".join(lines), 30, UiTheme.TEXT))
	col.add_child(panel)


func back_scene() -> String:
	return ScenePaths.MAIN_MENU
