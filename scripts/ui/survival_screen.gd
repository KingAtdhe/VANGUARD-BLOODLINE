extends MenuScreen
## Survival (spec §6.1): one-round fights against ever stronger opponents.
## Health carries over with a small recovery between fights; every fifth
## opponent is the Warden. The run ends on the first loss.


func _build() -> void:
	title_label.text = "SURVIVAL  ·  %s" % Catalog.fighter(ModeFlow.p1_id).display_name.to_upper()
	backdrop.show_fighter(ModeFlow.p1_id)
	backdrop.show_arena(&"neon" if Catalog.is_arena_unlocked(&"neon") else &"temple")
	backdrop.fighter_offset = 1.3
	var col := side_column(1000)
	col.add_theme_constant_override("separation", 14)
	var progress: Dictionary = SaveManager.section("progress")
	var max_hp: int = Catalog.fighter(ModeFlow.p1_id).base_health
	var hp: int = max_hp if ModeFlow.survival_health < 0 else ModeFlow.survival_health
	var tiles := HBoxContainer.new()
	tiles.add_theme_constant_override("separation", 14)
	tiles.add_child(stat_tile("Defeated", str(ModeFlow.survival_wins), Color.WHITE, 0.0, 56))
	tiles.add_child(stat_tile("Score", str(ModeFlow.survival_score), UiTheme.GOLD, 0.0, 56))
	tiles.add_child(stat_tile("Best", "%d · %d pts" % [int(progress["survival_best_wins"]),
		int(progress["survival_best_score"])], UiTheme.MUTED))
	col.add_child(tiles)
	# carried-over health
	var hp_box := PanelContainer.new()
	var hv := VBoxContainer.new()
	hv.add_theme_constant_override("separation", 8)
	hp_box.add_child(hv)
	var hrow := HBoxContainer.new()
	var cap := make_label("HEALTH CARRIED OVER", 22, UiTheme.MUTED)
	cap.add_theme_font_override("font", UiTheme.bold_font())
	cap.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hrow.add_child(cap)
	var pct: int = int(100.0 * hp / max_hp)
	hrow.add_child(make_display("%d%%" % pct, 52, UiTheme.GOLD if pct > 50 else UiTheme.EMBER if pct > 25 else UiTheme.ACCENT))
	hv.add_child(hrow)
	var bar := ProgressBar.new()
	bar.custom_minimum_size = Vector2(0, 22)
	bar.max_value = max_hp
	bar.value = hp
	bar.show_percentage = false
	hv.add_child(bar)
	col.add_child(hp_box)
	if ModeFlow.survival_over:
		col.add_child(make_display("RUN OVER", 72, UiTheme.ACCENT))
		col.add_child(make_label("\n".join(ModeFlow.survival_reward_lines), 30, UiTheme.GOLD))
		var again := make_button("New run  ›", func() -> void: SceneRouter.goto(ModeFlow.begin(MatchSetup.Mode.SURVIVAL)),
			Vector2(1000, 104), 44)
		again.name = "NewRunButton"
		col.add_child(again)
	else:
		var n: int = ModeFlow.survival_wins + 1
		var boss: bool = n % 5 == 0
		var diff: String = "Boss" if boss else SessionSettings.AI_DIFFICULTY_NAMES[ModeFlow.survival_difficulty()]
		col.add_child(make_card("%02d" % n, "Next opponent", "Difficulty: %s  ·  every 5th fight is the Warden" % diff,
			"BOSS" if boss else diff, UiTheme.ACCENT if boss else UiTheme.EMBER, Callable(), Vector2(1000, 100), true))
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 14)
		var fight := make_button("Fight  ›", func() -> void: SceneRouter.goto(ModeFlow.start_survival_match()),
			Vector2(560, 110), 48)
		fight.name = "FightButton"
		row.add_child(fight)
		var give := make_button("Give up (bank rewards)", _give_up, Vector2(426, 110), 30)
		give.name = "GiveUpButton"
		row.add_child(give)
		col.add_child(row)


func back_scene() -> String:
	return ScenePaths.MAIN_MENU


func go_back() -> void:
	if ModeFlow.survival_wins > 0:
		ModeFlow.end_survival_run()
	super.go_back()


func _give_up() -> void:
	ModeFlow.end_survival_run()
	SceneRouter.goto(ScenePaths.SURVIVAL)
