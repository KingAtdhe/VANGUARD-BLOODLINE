class_name MatchSetup
extends RefCounted
## Everything the combat scene needs to know about the next match. Built by
## ModeFlow from menu choices; read once by the combat scene in _ready.

enum Mode { VERSUS, TRAINING, STORY, ARCADE, SURVIVAL }
const MODE_NAMES: Array[String] = ["Versus", "Training", "Story", "Arcade", "Survival"]

const RULES_STANDARD: String = "res://data/rules/standard_match.tres"
const RULES_TRAINING: String = "res://data/rules/training.tres"
const RULES_SURVIVAL: String = "res://data/rules/survival.tres"

var mode: Mode = Mode.VERSUS
var p1_id: StringName = &"kairo"
var p2_id: StringName = &"sentinel"
var arena_id: StringName = &"ascendant"
## 0 Beginner, 1 Standard, 2 Expert. Ignored in Training (dummy).
var ai_difficulty: int = 1
var rules_path: String = RULES_STANDARD
## Survival health carry-over; -1 = full health.
var p1_opening_health: int = -1
## Name shown for P2 on the HUD (story/arcade opponents have titles).
var p2_display_name: String = ""
## Small banner on the HUD ("ARCADE  STAGE 3/5").
var banner: String = ""


func is_training() -> bool:
	return mode == Mode.TRAINING


func describe() -> String:
	return "%s %s vs %s @ %s ai=%d" % [MODE_NAMES[mode], p1_id, p2_id, arena_id, ai_difficulty]


## Problems that would stop the combat scene (empty = valid).
func validate() -> Array[String]:
	var p: Array[String] = []
	if Catalog.fighter(p1_id) == null:
		p.append("unknown P1 fighter %s" % p1_id)
	if Catalog.fighter(p2_id) == null:
		p.append("unknown P2 fighter %s" % p2_id)
	if Catalog.arena(arena_id) == null:
		p.append("unknown arena %s" % arena_id)
	if not ResourceLoader.exists(rules_path):
		p.append("missing rules %s" % rules_path)
	if ai_difficulty < 0 or ai_difficulty > 2:
		p.append("ai_difficulty out of range")
	return p
