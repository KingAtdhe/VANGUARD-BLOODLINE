extends RefCounted
## Milestone 7: mode logic without rendering — Story chapters and unlocks,
## the Arcade ladder, Survival carry-over, rewards and content integrity.


func test_story_data_is_complete_and_valid() -> Array[String]:
	var f: Array[String] = []
	var chapters: Array = ModeFlow.story_chapters()
	if chapters.size() != 6:
		f.append("expected 6 story chapters, got %d" % chapters.size())
	var bosses: int = 0
	for ch: Dictionary in chapters:
		for key: String in ["id", "title", "arena", "opponent", "ai", "intro", "outro", "reward"]:
			if not ch.has(key):
				f.append("%s missing %s" % [ch.get("id", "?"), key])
		if Catalog.arena(StringName(ch.get("arena", ""))) == null:
			f.append("%s: unknown arena" % ch.get("id"))
		if Catalog.fighter(StringName(ch.get("opponent", ""))) == null:
			f.append("%s: unknown opponent" % ch.get("id"))
		for line: Variant in ch.get("intro", []) + ch.get("outro", []):
			if typeof(line) != TYPE_ARRAY or (line as Array).size() != 2:
				f.append("%s: malformed dialogue line" % ch.get("id"))
		if ch.get("boss", false):
			bosses += 1
	if bosses != 1 or not chapters[-1].get("boss", false):
		f.append("story needs exactly one unique boss, in the final chapter")
	return f


func test_story_progression_unlocks_in_order() -> Array[String]:
	var f: Array[String] = []
	ModeFlow.begin(MatchSetup.Mode.STORY)
	if ModeFlow.open_story_chapter(1):
		f.append("chapter 2 opened before chapter 1 was cleared")
	if not ModeFlow.open_story_chapter(0):
		return ["chapter 1 is not available on a new save"]
	ModeFlow.start_story_fight()
	if ModeFlow.setup.p1_id != &"kairo" or ModeFlow.setup.validate().size() > 0:
		f.append("story setup invalid: %s" % ModeFlow.setup.describe())
	var lost: ModeFlow.Outcome = ModeFlow.on_match_end(1, 0, 0, 1000, 0)
	if lost.rematch_label == "" or int(SaveManager.section("progress")["story_cleared"]) != 0:
		f.append("a lost chapter must offer Retry and not count as cleared")
	var won: ModeFlow.Outcome = ModeFlow.on_match_end(0, 2, 700, 1000, 30)
	if int(SaveManager.section("progress")["story_cleared"]) != 1:
		f.append("winning chapter 1 did not clear it")
	if won.continue_scene != ScenePaths.STORY or ModeFlow.story_phase != 2:
		f.append("after a win the story should continue to the closing scene")
	if not (SaveManager.section("profile")["titles"] as Array).has("Heir of Origin"):
		f.append("chapter 1 title reward missing")
	var currency: int = int(SaveManager.section("profile")["currency"])
	# Replaying a cleared chapter pays a small reward, not the first-clear one.
	ModeFlow.open_story_chapter(0)
	ModeFlow.start_story_fight()
	ModeFlow.on_match_end(0, 2, 700, 1000, 30)
	if int(SaveManager.section("profile")["currency"]) - currency >= 100:
		f.append("replaying chapter 1 paid the first-clear reward again")
	# Chapter 3 unlocks the Neon District.
	SaveManager.section("progress")["story_cleared"] = 2
	ModeFlow.open_story_chapter(2)
	ModeFlow.start_story_fight()
	ModeFlow.on_match_end(0, 2, 700, 1000, 30)
	if not Catalog.is_arena_unlocked(&"neon"):
		f.append("clearing chapter 3 did not unlock the Neon District")
	# Chapter 6 (the finale) unlocks the Origin Chamber; it starts locked.
	if Catalog.is_arena_unlocked(&"origin"):
		f.append("the Origin Chamber should start locked")
	SaveManager.section("progress")["story_cleared"] = 5
	ModeFlow.open_story_chapter(5)
	ModeFlow.start_story_fight()
	ModeFlow.on_match_end(0, 2, 700, 1000, 30)
	if not Catalog.is_arena_unlocked(&"origin"):
		f.append("clearing chapter 6 did not unlock the Origin Chamber")
	return f


func test_arcade_ladder_to_the_boss() -> Array[String]:
	var f: Array[String] = []
	if ModeFlow.begin(MatchSetup.Mode.ARCADE) != ScenePaths.FIGHTER_SELECT:
		f.append("arcade must start at fighter select")
	if ModeFlow.fighter_chosen(&"warden") != "":
		f.append("a non-playable fighter (the boss) was accepted")
	if ModeFlow.fighter_chosen(&"kairo") != ScenePaths.ARCADE:
		f.append("arcade fighter select should lead to the ladder")
	ModeFlow.start_arcade_stage()
	var lost: ModeFlow.Outcome = ModeFlow.on_match_end(1, 0, 0, 1000, 0)
	if lost.rematch_label == "" or ModeFlow.arcade_stage != 0 or ModeFlow.arcade_retries != 1:
		f.append("a loss should offer a retry without advancing")
	var last: ModeFlow.Outcome = null
	for i: int in ModeFlow.ARCADE_STAGES.size():
		ModeFlow.start_arcade_stage()
		if i == ModeFlow.ARCADE_STAGES.size() - 1 and ModeFlow.setup.p2_id != &"warden":
			f.append("the final arcade stage must be the boss")
		last = ModeFlow.on_match_end(0, 2, 500, 1000, 40)
	if ModeFlow.arcade_state != 1 or last.continue_label != "Finish":
		f.append("ladder not marked cleared after the boss")
	if int(SaveManager.section("progress")["arcade_clears"]) != 1 or int(SaveManager.section("progress")["arcade_best_score"]) <= 0:
		f.append("arcade clear/score not recorded")
	if not Catalog.is_arena_unlocked(&"neon"):
		f.append("clearing arcade did not unlock the Neon District")
	return f


func test_arcade_quit_pays_partial_rewards_once() -> Array[String]:
	var f: Array[String] = []
	ModeFlow.begin(MatchSetup.Mode.ARCADE)
	ModeFlow.fighter_chosen(&"kairo")
	ModeFlow.start_arcade_stage()
	ModeFlow.on_match_end(0, 2, 800, 1000, 50)
	var xp_before: int = int(SaveManager.section("profile")["account_xp"])
	ModeFlow.end_arcade_run()
	var xp_after: int = int(SaveManager.section("profile")["account_xp"])
	ModeFlow.end_arcade_run()
	if xp_after <= xp_before:
		f.append("ending a run with a cleared stage paid nothing")
	if int(SaveManager.section("profile")["account_xp"]) != xp_after:
		f.append("ending the same run twice paid twice")
	return f


func test_survival_carries_health_and_scales() -> Array[String]:
	var f: Array[String] = []
	ModeFlow.begin(MatchSetup.Mode.SURVIVAL)
	ModeFlow.fighter_chosen(&"kairo")
	ModeFlow.start_survival_match()
	if ModeFlow.setup.rules_path != MatchSetup.RULES_SURVIVAL or ModeFlow.setup.p1_opening_health != -1:
		f.append("first survival match should be full health on survival rules")
	ModeFlow.on_match_end(0, 1, 400, 1000, 20)
	if ModeFlow.survival_health != 550:
		f.append("health carry-over: expected 400 + 15%% = 550, got %d" % ModeFlow.survival_health)
	ModeFlow.start_survival_match()
	if ModeFlow.setup.p1_opening_health != 550:
		f.append("carried health not passed to the next match")
	for _i: int in 3:
		ModeFlow.start_survival_match()
		ModeFlow.on_match_end(0, 1, 1000, 1000, 20)
	ModeFlow.start_survival_match()   # opponent 5
	if ModeFlow.setup.p2_id != &"warden" or ModeFlow.setup.ai_difficulty != 2:
		f.append("every fifth survival opponent should be the Warden")
	if ModeFlow.survival_difficulty() < 1:
		f.append("survival difficulty did not increase")
	var over: ModeFlow.Outcome = ModeFlow.on_match_end(1, 0, 0, 1000, 0)
	if not ModeFlow.survival_over or over.rematch_label != "" or over.continue_scene != ScenePaths.SURVIVAL:
		f.append("a survival loss must end the run (no rematch)")
	if int(SaveManager.section("progress")["survival_best_wins"]) != 4:
		f.append("survival best not recorded: %s" % SaveManager.section("progress")["survival_best_wins"])
	return f


func test_versus_and_training_setups() -> Array[String]:
	var f: Array[String] = []
	SaveManager.set_setting("ai_difficulty", 2)
	ModeFlow.begin(MatchSetup.Mode.VERSUS)
	if ModeFlow.fighter_chosen(&"kairo") != ScenePaths.ARENA_SELECT:
		f.append("versus should go to arena select")
	if ModeFlow.arena_chosen(&"neon") != "":
		f.append("a locked arena was accepted")
	if ModeFlow.arena_chosen(&"temple") != ScenePaths.COMBAT_GREYBOX or ModeFlow.setup.ai_difficulty != 2:
		f.append("versus setup wrong: %s" % ModeFlow.setup.describe())
	var o: ModeFlow.Outcome = ModeFlow.on_match_end(0, 2, 900, 1000, 40)
	if o.rematch_label == "" or o.continue_scene != ScenePaths.FIGHTER_SELECT:
		f.append("versus results should offer Rematch and Change fighter")
	if int(SaveManager.section("stats")["wins"]) != 1:
		f.append("statistics not recorded")
	ModeFlow.begin(MatchSetup.Mode.TRAINING)
	ModeFlow.fighter_chosen(&"kairo")
	if ModeFlow.arena_chosen(&"ascendant") != ScenePaths.TRAINING_GREYBOX or ModeFlow.setup.p2_id != &"training_dummy":
		f.append("training setup wrong")
	return f


func test_progression_levels_and_grants() -> Array[String]:
	var f: Array[String] = []
	if Progression.level_for_xp(0) != 1 or Progression.level_for_xp(299) != 1 or Progression.level_for_xp(300) != 2 \
			or Progression.level_for_xp(700) != 3:
		f.append("level curve wrong")
	var lines: PackedStringArray = Progression.grant(Progression.Reward.new(350, 50, "Tester"), &"kairo")
	if Progression.account_level() != 2 or int(SaveManager.section("profile")["currency"]) != 50:
		f.append("grant did not apply xp/currency")
	if not "\n".join(lines).contains("New title: Tester"):
		f.append("grant lines missing the title: %s" % lines)
	Progression.grant(Progression.Reward.new(0, 0, "Tester"), &"kairo")
	if (SaveManager.section("profile")["titles"] as Array).count("Tester") != 1:
		f.append("titles duplicated")
	if Progression.mastery_level(&"kairo") != 2:
		f.append("mastery not granted")
	return f
