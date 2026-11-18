extends MenuScreen
## Arcade ladder (spec §6.1): five opponents ending with the Origin Warden.
## Shows progress and score between fights; ending a run early still pays
## out for the stages cleared.

var _fight: Button


func _build() -> void:
	title_label.text = "ARCADE  ·  %s" % Catalog.fighter(ModeFlow.p1_id).display_name.to_upper()
	backdrop.show_fighter(ModeFlow.p1_id)
	backdrop.fighter_offset = 1.3
	var col := side_column(900)
	var stages: Array[Dictionary] = ModeFlow.ARCADE_STAGES
	for i: int in stages.size():
		var st: Dictionary = stages[i]
		var mark: String = "✓" if i < ModeFlow.arcade_stage else ("›" if i == ModeFlow.arcade_stage and ModeFlow.arcade_state == 0 else "·")
		var row := make_label("%s  Stage %d — %s%s   (%s)" % [mark, i + 1, st["name"],
			"  BOSS" if st.get("boss", false) else "", Catalog.arena(st["arena"]).display_name], 34,
			UiTheme.GOLD if i == ModeFlow.arcade_stage else (UiTheme.TEXT if i < ModeFlow.arcade_stage else UiTheme.MUTED))
		col.add_child(row)
	var best: int = int(SaveManager.section("progress")["arcade_best_score"])
	col.add_child(make_label("Score %d    ·    Best %d" % [ModeFlow.arcade_score, best], 36, Color.WHITE))
	match ModeFlow.arcade_state:
		0:
			var st: Dictionary = stages[ModeFlow.arcade_stage]
			backdrop.show_arena(st["arena"])
			_fight = make_button("Fight stage %d  ›" % (ModeFlow.arcade_stage + 1), _start, Vector2(900, 116), 46)
			_fight.name = "FightButton"
			col.add_child(_fight)
			var end := make_button("End run", _end_run, Vector2(900, 92), 34)
			end.name = "EndRunButton"
			col.add_child(end)
		_:
			backdrop.show_arena(&"ascendant")
			backdrop.play_pose(&"KAIRO_VICTORY" if ModeFlow.arcade_state == 1 else &"KAIRO_IDLE_A")
			col.add_child(make_label("LADDER CLEARED!" if ModeFlow.arcade_state == 1 else "Run ended", 52,
				UiTheme.GOLD if ModeFlow.arcade_state == 1 else UiTheme.MUTED))
			col.add_child(make_label("\n".join(ModeFlow.arcade_reward_lines), 32, UiTheme.GOLD))
			var again := make_button("New run", func() -> void: SceneRouter.goto(ModeFlow.begin(MatchSetup.Mode.ARCADE)),
				Vector2(900, 104), 40)
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
