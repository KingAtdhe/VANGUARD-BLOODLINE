class_name ModeFlow
extends RefCounted
## Navigation and run state for the offline modes (spec §6.1): Versus (vs
## CPU), Training, Story, Arcade and Survival. Menus call ModeFlow; ModeFlow
## builds the MatchSetup, decides where to go after each match and grants
## rewards through Progression. Static (session-lifetime) state, no autoload.
##
## Screen graph (every screen has a way back; see test_navigation):
##   Main ─ Story ─ (dialogue) ─ combat ─ results ─ Story
##        ├ Arcade:   fighter select ─ ladder ─ combat ─ results ─ ladder
##        ├ Survival: fighter select ─ run    ─ combat ─ results ─ run
##        ├ Versus:   fighter select ─ arena select ─ combat ─ results
##        ├ Training: fighter select ─ arena select ─ training
##        ├ Profile, Settings ─ Main

## What the results screen offers after a match.
class Outcome:
	extends RefCounted
	var headline: String = ""
	var lines: PackedStringArray = []
	## In-scene restart with the same setup ("Rematch" / "Retry").
	var rematch_label: String = ""
	## Primary route after the match ("Continue", "Next stage"…).
	var continue_label: String = ""
	var continue_scene: String = ""
	## Always offered: leave to this screen.
	var quit_label: String = "Main menu"
	var quit_scene: String = ScenePaths.MAIN_MENU


const STORY_PATH: String = "res://data/story/chapters.json"

## Arcade ladder: opponent, title, AI difficulty, arena. Last = boss.
const ARCADE_STAGES: Array[Dictionary] = [
	{"opponent": &"sentinel", "name": "Sentinel Initiate", "ai": 0, "arena": &"temple"},
	{"opponent": &"sentinel", "name": "Sentinel Vanguard", "ai": 1, "arena": &"ascendant"},
	{"opponent": &"sentinel", "name": "Rogue Sentinel", "ai": 1, "arena": &"neon"},
	{"opponent": &"sentinel", "name": "Sentinel Adept", "ai": 2, "arena": &"temple"},
	{"opponent": &"warden", "name": "Origin Warden", "ai": 2, "arena": &"ascendant", "boss": true},
]

## Survival: health restored between matches, as a fraction of max health.
const SURVIVAL_RECOVERY: float = 0.15

static var mode: MatchSetup.Mode = MatchSetup.Mode.VERSUS
static var p1_id: StringName = &"kairo"
static var setup: MatchSetup = null

# Story
static var story_chapter: int = 0
## 0 = chapter list, 1 = intro dialogue, 2 = outro dialogue (after a win).
static var story_phase: int = 0
static var story_reward_lines: PackedStringArray = []
# Arcade
static var arcade_stage: int = 0
static var arcade_score: int = 0
static var arcade_retries: int = 0
## 0 running, 1 cleared, 2 ended early.
static var arcade_state: int = 0
static var arcade_reward_lines: PackedStringArray = []
# Survival
static var survival_wins: int = 0
static var survival_score: int = 0
static var survival_health: int = -1
static var survival_over: bool = false
static var survival_reward_lines: PackedStringArray = []
# Per-match bookkeeping from the combat scene.
static var _perfect_rounds: int = 0
static var _story_cache: Dictionary = {}


# --- entering modes ----------------------------------------------------------------

## Main-menu entry. Returns the scene to open.
static func begin(m: MatchSetup.Mode) -> String:
	mode = m
	setup = null
	match m:
		MatchSetup.Mode.STORY:
			p1_id = &"kairo"   # Kairo-focused campaign
			story_phase = 0
			return ScenePaths.STORY
		MatchSetup.Mode.ARCADE:
			arcade_stage = 0
			arcade_score = 0
			arcade_retries = 0
			arcade_state = 0
			arcade_reward_lines = []
		MatchSetup.Mode.SURVIVAL:
			survival_wins = 0
			survival_score = 0
			survival_health = -1
			survival_over = false
			survival_reward_lines = []
	return ScenePaths.FIGHTER_SELECT


static func fighter_chosen(id: StringName) -> String:
	var def: FighterDefinition = Catalog.fighter(id)
	if def == null or not def.playable:
		return ""
	p1_id = id
	match mode:
		MatchSetup.Mode.ARCADE:
			return ScenePaths.ARCADE
		MatchSetup.Mode.SURVIVAL:
			return ScenePaths.SURVIVAL
	return ScenePaths.ARENA_SELECT


## Back from fighter select.
static func fighter_select_back() -> String:
	return ScenePaths.MAIN_MENU


static func arena_chosen(id: StringName) -> String:
	if not Catalog.is_arena_unlocked(id):
		return ""
	var s := MatchSetup.new()
	s.mode = mode
	s.p1_id = p1_id
	s.arena_id = id
	if mode == MatchSetup.Mode.TRAINING:
		s.p2_id = &"training_dummy"
		s.rules_path = MatchSetup.RULES_TRAINING
		s.banner = "TRAINING"
		setup = s
		return ScenePaths.TRAINING_GREYBOX
	s.p2_id = &"sentinel"
	s.ai_difficulty = int(SaveManager.setting("ai_difficulty"))
	s.banner = "VERSUS CPU"
	setup = s
	return ScenePaths.COMBAT_GREYBOX


# --- story --------------------------------------------------------------------------

static func story() -> Dictionary:
	if _story_cache.is_empty():
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(STORY_PATH))
		_story_cache = parsed if typeof(parsed) == TYPE_DICTIONARY else {"chapters": []}
	return _story_cache


static func story_chapters() -> Array:
	return story().get("chapters", [])


static func story_unlocked(index: int) -> bool:
	return index <= int(SaveManager.section("progress")["story_cleared"])


static func open_story_chapter(index: int) -> bool:
	if index < 0 or index >= story_chapters().size() or not story_unlocked(index):
		return false
	story_chapter = index
	story_phase = 1
	story_reward_lines = []
	return true


static func start_story_fight() -> String:
	var ch: Dictionary = story_chapters()[story_chapter]
	var s := MatchSetup.new()
	s.mode = MatchSetup.Mode.STORY
	s.p1_id = &"kairo"
	s.p2_id = StringName(ch["opponent"])
	s.arena_id = StringName(ch["arena"])
	s.ai_difficulty = int(ch["ai"])
	s.p2_display_name = ch.get("opponent_name", "")
	s.banner = ("BOSS — " if ch.get("boss", false) else "") + String(ch["title"]).to_upper()
	setup = s
	mode = MatchSetup.Mode.STORY
	return ScenePaths.COMBAT_GREYBOX


# --- arcade ---------------------------------------------------------------------------

static func start_arcade_stage() -> String:
	var st: Dictionary = ARCADE_STAGES[arcade_stage]
	var s := MatchSetup.new()
	s.mode = MatchSetup.Mode.ARCADE
	s.p1_id = p1_id
	s.p2_id = st["opponent"]
	s.arena_id = st["arena"]
	s.ai_difficulty = st["ai"]
	s.p2_display_name = st["name"]
	s.banner = "ARCADE  STAGE %d/%d%s" % [arcade_stage + 1, ARCADE_STAGES.size(), "  BOSS" if st.get("boss", false) else ""]
	setup = s
	return ScenePaths.COMBAT_GREYBOX


## Ends an unfinished arcade run (quit from the ladder): partial rewards.
static func end_arcade_run() -> void:
	if arcade_state != 0:
		return
	arcade_state = 2
	_finish_arcade(false)


# --- survival -------------------------------------------------------------------------

static func survival_difficulty() -> int:
	return 0 if survival_wins < 2 else (1 if survival_wins < 5 else 2)


static func start_survival_match() -> String:
	var n: int = survival_wins + 1
	var boss: bool = n % 5 == 0
	var unlocked: Array[StringName] = []
	for a: StringName in Catalog.ARENAS:
		if Catalog.is_arena_unlocked(a):
			unlocked.append(a)
	var s := MatchSetup.new()
	s.mode = MatchSetup.Mode.SURVIVAL
	s.p1_id = p1_id
	s.p2_id = &"warden" if boss else &"sentinel"
	s.arena_id = unlocked[survival_wins % unlocked.size()]
	s.ai_difficulty = 2 if boss else survival_difficulty()
	s.rules_path = MatchSetup.RULES_SURVIVAL
	s.p1_opening_health = survival_health
	s.p2_display_name = "Origin Warden" if boss else "Sentinel #%d" % n
	s.banner = "SURVIVAL  OPPONENT %d" % n
	setup = s
	return ScenePaths.COMBAT_GREYBOX


static func end_survival_run() -> void:
	if survival_over:
		return
	survival_over = true
	var progress: Dictionary = SaveManager.section("progress")
	progress["survival_best_wins"] = maxi(int(progress["survival_best_wins"]), survival_wins)
	progress["survival_best_score"] = maxi(int(progress["survival_best_score"]), survival_score)
	var r := Progression.Reward.new(40 * survival_wins, 15 * survival_wins,
		"Unbroken" if survival_wins >= 10 else "")
	survival_reward_lines = Progression.grant(r, p1_id)


# --- match results ----------------------------------------------------------------------

## Combat scene hook: a round ended. Tracks perfect rounds for statistics.
static func note_round(winner: int, winner_health: int, max_health: int) -> void:
	if winner == 0 and winner_health >= max_health:
		_perfect_rounds += 1


static func note_match_start() -> void:
	_perfect_rounds = 0


## Called once when a match ends (never in Training). Updates statistics,
## run state and rewards, and says what the results screen should offer.
static func on_match_end(winner: int, p1_rounds: int, p1_health: int, p1_max: int, time_left: int) -> Outcome:
	var o := Outcome.new()
	var won: bool = winner == 0
	o.headline = "VICTORY" if won else ("DRAW" if winner < 0 else "DEFEAT")
	Progression.record_match(winner, p1_rounds, _perfect_rounds)
	var m: MatchSetup.Mode = setup.mode if setup != null else MatchSetup.Mode.VERSUS
	match m:
		MatchSetup.Mode.STORY:
			o.quit_label = "Story menu"
			o.quit_scene = ScenePaths.STORY
			if won:
				var progress: Dictionary = SaveManager.section("progress")
				var ch: Dictionary = story_chapters()[story_chapter]
				var first_clear: bool = int(progress["story_cleared"]) == story_chapter
				if first_clear:
					progress["story_cleared"] = story_chapter + 1
					var rw: Dictionary = ch.get("reward", {})
					story_reward_lines = Progression.grant(Progression.Reward.new(
						int(rw.get("xp", 0)), int(rw.get("currency", 0)), rw.get("title", ""),
						StringName(rw.get("arena", ""))), &"kairo")
				else:
					story_reward_lines = Progression.grant(Progression.Reward.new(60, 10), &"kairo")
				o.lines = story_reward_lines
				story_phase = 2
				o.continue_label = "Continue"
				o.continue_scene = ScenePaths.STORY
			else:
				Progression.grant(Progression.Reward.new(20, 0), &"kairo")
				o.rematch_label = "Retry"
				o.lines = ["The chapter isn't over. Try again?"]
		MatchSetup.Mode.ARCADE:
			o.quit_label = "Ladder"
			o.quit_scene = ScenePaths.ARCADE
			if won:
				var stage_score: int = 1000 + p1_health + time_left * 10 + (500 if p1_rounds > 0 and _perfect_rounds > 0 else 0)
				stage_score = maxi(100, stage_score - arcade_retries * 200)
				arcade_score += stage_score
				o.lines.append("Stage score  %d   (total %d)" % [stage_score, arcade_score])
				arcade_stage += 1
				arcade_retries = 0
				if arcade_stage >= ARCADE_STAGES.size():
					arcade_state = 1
					_finish_arcade(true)
					o.lines.append_array(arcade_reward_lines)
					o.continue_label = "Finish"
				else:
					o.continue_label = "Next stage"
				o.continue_scene = ScenePaths.ARCADE
			else:
				o.rematch_label = "Retry stage"
				arcade_retries += 1
				o.lines.append("Retrying costs 200 points from this stage's score.")
		MatchSetup.Mode.SURVIVAL:
			o.quit_label = "Survival"
			o.quit_scene = ScenePaths.SURVIVAL
			if won:
				survival_wins += 1
				var gained: int = 100 + p1_health / 5 + time_left * 2
				survival_score += gained
				survival_health = mini(p1_max, p1_health + int(p1_max * SURVIVAL_RECOVERY))
				o.lines.append("+%d  (score %d)   Health carried: %d%%" % [
					gained, survival_score, int(100.0 * survival_health / p1_max)])
				o.continue_label = "Next opponent"
				o.continue_scene = ScenePaths.SURVIVAL
			else:
				end_survival_run()
				o.headline = "RUN OVER"
				o.lines.append("Opponents defeated: %d   Score: %d" % [survival_wins, survival_score])
				o.lines.append_array(survival_reward_lines)
				o.continue_label = "Finish"
				o.continue_scene = ScenePaths.SURVIVAL
		_:
			o.rematch_label = "Rematch"
			o.continue_label = "Change fighter"
			o.continue_scene = ScenePaths.FIGHTER_SELECT
			o.lines = Progression.grant(Progression.Reward.new(60 if won else 25, 20 if won else 5), setup.p1_id if setup != null else &"")
	SaveManager.save()
	return o


static func _finish_arcade(cleared: bool) -> void:
	var progress: Dictionary = SaveManager.section("progress")
	progress["arcade_best_score"] = maxi(int(progress["arcade_best_score"]), arcade_score)
	var title: String = ""
	if cleared:
		progress["arcade_clears"] = int(progress["arcade_clears"]) + 1
		title = "Arcade Victor"
	var r := Progression.Reward.new(arcade_score / 20, arcade_score / 50, title,
		&"neon" if cleared else &"")
	arcade_reward_lines = Progression.grant(r, p1_id)
