class_name Progression
extends RefCounted
## Account level, fighter mastery, soft currency ("Shards"), titles and
## statistics (spec §6.2). Earned only by playing: no purchases, no energy,
## no gameplay advantages — rewards are cosmetic/profile items and unlocks.

const CURRENCY_NAME: String = "Shards"
## XP needed for level n -> n+1 grows linearly: 300, 400, 500, …
const LEVEL_BASE_XP: int = 300
const LEVEL_STEP_XP: int = 100
const MAX_LEVEL: int = 99


class Reward:
	extends RefCounted
	var xp: int = 0
	var mastery_xp: int = 0
	var currency: int = 0
	var title: String = ""
	var arena_unlock: StringName = &""

	func _init(p_xp: int = 0, p_currency: int = 0, p_title: String = "", p_arena: StringName = &"") -> void:
		xp = p_xp
		mastery_xp = p_xp
		currency = p_currency
		title = p_title
		arena_unlock = p_arena


static func level_for_xp(xp: int) -> int:
	var level: int = 1
	var need: int = LEVEL_BASE_XP
	var left: int = xp
	while left >= need and level < MAX_LEVEL:
		left -= need
		level += 1
		need += LEVEL_STEP_XP
	return level


## XP into the current level and the size of that level, for progress bars.
static func level_progress(xp: int) -> Vector2i:
	var need: int = LEVEL_BASE_XP
	var left: int = xp
	var level: int = 1
	while left >= need and level < MAX_LEVEL:
		left -= need
		level += 1
		need += LEVEL_STEP_XP
	return Vector2i(left, need)


static func account_level() -> int:
	return level_for_xp(SaveManager.section("profile")["account_xp"])


static func mastery_level(fighter_id: StringName) -> int:
	return level_for_xp(int(SaveManager.section("mastery").get(String(fighter_id), 0)))


## Applies [param r] for [param fighter_id] and saves. Returns readable lines.
static func grant(r: Reward, fighter_id: StringName) -> PackedStringArray:
	var lines: PackedStringArray = []
	var profile: Dictionary = SaveManager.section("profile")
	if r.xp > 0:
		var before: int = account_level()
		profile["account_xp"] = int(profile["account_xp"]) + r.xp
		lines.append("+%d XP" % r.xp)
		if account_level() > before:
			lines.append("Account level %d!" % account_level())
	if r.mastery_xp > 0 and fighter_id != &"":
		var m: Dictionary = SaveManager.section("mastery")
		var before_m: int = mastery_level(fighter_id)
		m[String(fighter_id)] = int(m.get(String(fighter_id), 0)) + r.mastery_xp
		if mastery_level(fighter_id) > before_m:
			lines.append("%s mastery %d!" % [String(fighter_id).capitalize(), mastery_level(fighter_id)])
	if r.currency > 0:
		profile["currency"] = int(profile["currency"]) + r.currency
		lines.append("+%d %s" % [r.currency, CURRENCY_NAME])
	if r.title != "" and not (profile["titles"] as Array).has(r.title):
		(profile["titles"] as Array).append(r.title)
		lines.append("New title: %s" % r.title)
	if r.arena_unlock != &"":
		var unlocked: Array = SaveManager.section("progress")["unlocked_arenas"]
		if not unlocked.has(String(r.arena_unlock)) and not Catalog.is_arena_unlocked(r.arena_unlock):
			unlocked.append(String(r.arena_unlock))
			var a: ArenaConfig = Catalog.arena(r.arena_unlock)
			lines.append("Arena unlocked: %s" % (a.display_name if a != null else String(r.arena_unlock)))
	SaveManager.save()
	return lines


## Records a finished match in the statistics (not saved; grant/save does).
static func record_match(winner: int, rounds_won: int, perfect_rounds: int) -> void:
	var s: Dictionary = SaveManager.section("stats")
	s["matches"] = int(s["matches"]) + 1
	if winner == 0:
		s["wins"] = int(s["wins"]) + 1
	elif winner == 1:
		s["losses"] = int(s["losses"]) + 1
	else:
		s["draws"] = int(s["draws"]) + 1
	s["rounds_won"] = int(s["rounds_won"]) + rounds_won
	s["perfect_rounds"] = int(s["perfect_rounds"]) + perfect_rounds
