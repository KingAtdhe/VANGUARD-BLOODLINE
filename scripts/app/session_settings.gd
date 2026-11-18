class_name SessionSettings
extends RefCounted
## Choices that live for the current app session only (no autoload needed).
## Persisted settings arrive with the save system in Milestone 7.

const AI_DIFFICULTIES: Array[String] = ["beginner", "standard", "expert"]
const AI_DIFFICULTY_NAMES: Array[String] = ["Beginner", "Standard", "Expert"]

## Index into AI_DIFFICULTIES used by Fight (versus).
static var ai_difficulty: int = 1


static func ai_profile_path(difficulty: int = ai_difficulty) -> String:
	return "res://data/ai/%s.tres" % AI_DIFFICULTIES[clampi(difficulty, 0, AI_DIFFICULTIES.size() - 1)]


static func cycle_ai_difficulty() -> void:
	ai_difficulty = (ai_difficulty + 1) % AI_DIFFICULTIES.size()
