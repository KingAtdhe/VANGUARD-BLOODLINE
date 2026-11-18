extends MenuScreen
## Survival (spec §6.1): one-round fights against ever stronger opponents.
## Health carries over with a small recovery between fights; every fifth
## opponent is the Warden. The run ends on the first loss.


func _build() -> void:
	title_label.text = "SURVIVAL  ·  %s" % Catalog.fighter(ModeFlow.p1_id).display_name.to_upper()
	backdrop.show_fighter(ModeFlow.p1_id)
	backdrop.show_arena(&"neon" if Catalog.is_arena_unlocked(&"neon") else &"temple")
	backdrop.fighter_offset = 1.3
	var col := side_column(900)
	var progress: Dictionary = SaveManager.section("progress")
	var max_hp: int = Catalog.fighter(ModeFlow.p1_id).base_health
	var hp: int = max_hp if ModeFlow.survival_health < 0 else ModeFlow.survival_health
	col.add_child(make_label("Opponents defeated:  %d" % ModeFlow.survival_wins, 44, Color.WHITE))
	col.add_child(make_label("Score:  %d" % ModeFlow.survival_score, 38, UiTheme.GOLD))
	var bar := ProgressBar.new()
	bar.custom_minimum_size = Vector2(900, 34)
	bar.max_value = max_hp
	bar.value = hp
	bar.show_percentage = false
	col.add_child(make_label("Health  %d%%" % int(100.0 * hp / max_hp), 32, UiTheme.MUTED))
	col.add_child(bar)
	col.add_child(make_label("Best: %d defeated · %d points" % [int(progress["survival_best_wins"]),
		int(progress["survival_best_score"])], 30, UiTheme.MUTED))
	if ModeFlow.survival_over:
		col.add_child(make_label("RUN OVER", 52, UiTheme.ACCENT))
		col.add_child(make_label("\n".join(ModeFlow.survival_reward_lines), 32, UiTheme.GOLD))
		var again := make_button("New run", func() -> void: SceneRouter.goto(ModeFlow.begin(MatchSetup.Mode.SURVIVAL)),
			Vector2(900, 104), 40)
		again.name = "NewRunButton"
		col.add_child(again)
	else:
		var n: int = ModeFlow.survival_wins + 1
		var diff: String = "Boss" if n % 5 == 0 else SessionSettings.AI_DIFFICULTY_NAMES[ModeFlow.survival_difficulty()]
		col.add_child(make_label("Next: opponent %d (%s)" % [n, diff], 34, Color.WHITE))
		var fight := make_button("Fight  ›", func() -> void: SceneRouter.goto(ModeFlow.start_survival_match()),
			Vector2(900, 116), 46)
		fight.name = "FightButton"
		col.add_child(fight)
		var give := make_button("Give up (bank rewards)", _give_up, Vector2(900, 92), 34)
		give.name = "GiveUpButton"
		col.add_child(give)


func back_scene() -> String:
	return ScenePaths.MAIN_MENU


func go_back() -> void:
	if ModeFlow.survival_wins > 0:
		ModeFlow.end_survival_run()
	super.go_back()


func _give_up() -> void:
	ModeFlow.end_survival_run()
	SceneRouter.goto(ScenePaths.SURVIVAL)
