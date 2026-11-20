extends MenuScreen
## Arcade ladder (spec §6.1): five opponents ending with the Origin Warden.
## Shows progress and score between fights; ending a run early still pays
## out for the stages cleared.

var _fight: Button


func _build() -> void:
	title_label.text = "ARCADE  ·  %s" % Catalog.fighter(ModeFlow.p1_id).display_name.to_upper()
	backdrop.show_fighter(ModeFlow.p1_id)
	backdrop.fighter_offset = 1.3
	var col := side_column(1000)
	col.add_theme_constant_override("separation", 10)
	var best: int = int(SaveManager.section("progress")["arcade_best_score"])
	var tiles := HBoxContainer.new()
	tiles.add_theme_constant_override("separation", 14)
	tiles.add_child(stat_tile("Stage", "%d / %d" % [mini(ModeFlow.arcade_stage + 1, ModeFlow.ARCADE_STAGES.size()),
		ModeFlow.ARCADE_STAGES.size()], Color.WHITE))
	tiles.add_child(stat_tile("Score", str(ModeFlow.arcade_score), UiTheme.GOLD, 0.0, 56))
	tiles.add_child(stat_tile("Best", str(best), UiTheme.MUTED, 0.0, 56))
	col.add_child(tiles)
	# the ladder: cleared stages gold, the next fight highlighted, the rest dim
	var stages: Array[Dictionary] = ModeFlow.ARCADE_STAGES
	for i: int in stages.size():
		var st: Dictionary = stages[i]
		var boss: bool = st.get("boss", false)
		var done: bool = i < ModeFlow.arcade_stage
		var now: bool = i == ModeFlow.arcade_stage and ModeFlow.arcade_state == 0
		var chip: String = "CLEARED" if done else ("BOSS" if boss else ("NEXT" if now else ""))
		var col_chip: Color = UiTheme.GOLD if done else UiTheme.ACCENT
		col.add_child(make_card("%02d" % (i + 1), String(st["name"]), Catalog.arena(st["arena"]).display_name,
			chip, col_chip, Callable(), Vector2(1000, 84), now, not done and not now))
	match ModeFlow.arcade_state:
		0:
			var st: Dictionary = stages[ModeFlow.arcade_stage]
			backdrop.show_arena(st["arena"])
			var row := HBoxContainer.new()
			row.add_theme_constant_override("separation", 14)
			_fight = make_button("Fight stage %d  ›" % (ModeFlow.arcade_stage + 1), _start, Vector2(640, 100), 46)
			_fight.name = "FightButton"
			row.add_child(_fight)
			var end := make_button("End run", _end_run, Vector2(346, 100), 32)
			end.name = "EndRunButton"
			row.add_child(end)
			col.add_child(row)
		_:
			backdrop.show_arena(&"ascendant")
			backdrop.play_pose(&"KAIRO_VICTORY" if ModeFlow.arcade_state == 1 else &"KAIRO_IDLE_A")
			col.add_child(make_display("LADDER CLEARED" if ModeFlow.arcade_state == 1 else "RUN ENDED", 72,
				UiTheme.GOLD if ModeFlow.arcade_state == 1 else UiTheme.MUTED))
			col.add_child(make_label("\n".join(ModeFlow.arcade_reward_lines), 30, UiTheme.GOLD))
			var again := make_button("New run  ›", func() -> void: SceneRouter.goto(ModeFlow.begin(MatchSetup.Mode.ARCADE)),
				Vector2(1000, 104), 44)
			again.name = "NewRunButton"
			col.add_child(again)


func back_scene() -> String:
	return ScenePaths.MAIN_MENU


## Leaving mid-run ends it (with partial rewards) — no hidden half-runs.
func go_back() -> void:
	ModeFlow.end_arcade_run()
	super.go_back()


func _start() -> void:
	SceneRouter.goto(ModeFlow.start_arcade_stage())


func _end_run() -> void:
	ModeFlow.end_arcade_run()
	SceneRouter.goto(ScenePaths.ARCADE)
