class_name SaveManager
extends RefCounted
## Local save data (spec §6.3): settings, progress, unlocks, currency,
## mastery and statistics in one versioned JSON file under user://.
##
## Robustness rules:
##   - Writes are atomic: write save.tmp, then rename over save.json, so a
##     crash mid-write never leaves a half-written save.
##   - Every load is validated field by field against the defaults; wrong
##     types or out-of-range values fall back to the default for that field
##     only, unknown keys are dropped.
##   - A file that can't be parsed is kept as save.corrupt.json (for support)
##     and the game continues with defaults — it never crashes or blocks.
##   - Older versions are migrated step by step (see _migrate).
## Static on purpose: no autoload beyond SceneRouter (see test_project_config).
## No secrets or purchase state are ever stored here.

const VERSION: int = 1
const DEFAULT_PATH: String = "user://save.json"

## Overridable for tests (point at a temp file).
static var path: String = DEFAULT_PATH
static var data: Dictionary = {}
static var _loaded: bool = false
## Why the last load fell back to defaults ("" = clean load or new save).
static var last_load_issue: String = ""


static func defaults() -> Dictionary:
	return {
		"version": VERSION,
		"settings": {
			"left_handed": false,
			"controls_scale": 1.0,
			"controls_opacity": 0.55,
			"touch_controls": 0,          # 0 auto, 1 always, 2 never
			"master_volume": 0.8,
			"sfx_volume": 0.8,
			"reduced_shake": false,
			"cinematics": true,
			"reduced_effects": false,
			"ai_difficulty": 1,
		},
		"profile": {
			"account_xp": 0,
			"currency": 0,
			"title": "Newcomer",
			"titles": ["Newcomer"],
		},
		"mastery": {},                    # fighter_id -> xp
		"progress": {
			"story_cleared": 0,           # chapters completed (0..6)
			"arcade_clears": 0,
			"arcade_best_score": 0,
			"survival_best_wins": 0,
			"survival_best_score": 0,
			"unlocked_arenas": [],        # beyond the default-unlocked ones
		},
		"stats": {
			"matches": 0,
			"wins": 0,
			"losses": 0,
			"draws": 0,
			"rounds_won": 0,
			"perfect_rounds": 0,
		},
	}


## Ranges for numeric settings: key -> [min, max].
const RANGES: Dictionary = {
	"controls_scale": [0.7, 1.4],
	"controls_opacity": [0.2, 1.0],
	"touch_controls": [0, 2],
	"master_volume": [0.0, 1.0],
	"sfx_volume": [0.0, 1.0],
	"ai_difficulty": [0, 2],
	"story_cleared": [0, 6],
}


static func ensure_loaded() -> void:
	if not _loaded:
		load_save()


## Loads (or creates) the save. Never fails: problems fall back to defaults.
static func load_save() -> void:
	_loaded = true
	last_load_issue = ""
	data = defaults()
	if not FileAccess.file_exists(path):
		return
	var text: String = FileAccess.get_file_as_string(path)
	# JSON instance (not JSON.parse_string): a bad file is an expected case,
	# reported via last_load_issue rather than an engine error.
	var json := JSON.new()
	var parsed: Variant = json.data if json.parse(text) == OK else null
	if typeof(parsed) != TYPE_DICTIONARY:
		last_load_issue = "unreadable save (kept as %s)" % _corrupt_path()
		_keep_corrupt(text)
		push_warning("SaveManager: %s; starting fresh." % last_load_issue)
		save()
		return
	var d: Dictionary = parsed
	var version: int = int(d.get("version", 0)) if typeof(d.get("version")) in [TYPE_INT, TYPE_FLOAT] else 0
	if version > VERSION:
		# A newer build wrote this. Read what we understand, keep the file.
		last_load_issue = "save from a newer version (%d)" % version
	d = _migrate(d, version)
	data = _sanitize(defaults(), d)
	data["version"] = VERSION


## Atomic write. Returns false (and keeps the old file) if writing fails.
static func save() -> bool:
	ensure_loaded()
	var tmp: String = path + ".tmp"
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		push_warning("SaveManager: cannot write %s (%s)" % [tmp, error_string(FileAccess.get_open_error())])
		return false
	f.store_string(JSON.stringify(data, "\t"))
	f.close()
	var err: Error = DirAccess.rename_absolute(ProjectSettings.globalize_path(tmp), ProjectSettings.globalize_path(path))
	if err != OK and FileAccess.file_exists(path):
		# Platforms that refuse to rename over an existing file.
		DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
		err = DirAccess.rename_absolute(ProjectSettings.globalize_path(tmp), ProjectSettings.globalize_path(path))
	if err != OK:
		push_warning("SaveManager: rename failed (%s)" % error_string(err))
		return false
	return true


## Erases all progress and settings (Settings → Reset), then saves.
static func reset_all() -> void:
	data = defaults()
	_loaded = true
	save()


# --- typed accessors -------------------------------------------------------------

static func setting(key: String) -> Variant:
	ensure_loaded()
	return data["settings"].get(key, defaults()["settings"].get(key))


static func set_setting(key: String, value: Variant) -> void:
	ensure_loaded()
	var fresh: Dictionary = defaults()["settings"]
	if not fresh.has(key):
		push_warning("SaveManager: unknown setting %s" % key)
		return
	data["settings"][key] = _clean_value(key, value, fresh[key])
	save()


static func section(name: String) -> Dictionary:
	ensure_loaded()
	return data[name]


## For tests: forget the cached data so the next access re-reads the file.
static func unload() -> void:
	_loaded = false
	data = {}


# --- internals ---------------------------------------------------------------------

static func _corrupt_path() -> String:
	return path.get_basename() + ".corrupt.json"


static func _keep_corrupt(text: String) -> void:
	var f: FileAccess = FileAccess.open(_corrupt_path(), FileAccess.WRITE)
	if f != null:
		f.store_string(text)
		f.close()


## Step-by-step upgrades from older layouts. Version 0 = pre-release files
## without a version field (none shipped; kept as the migration template).
static func _migrate(d: Dictionary, from_version: int) -> Dictionary:
	var v: int = from_version
	if v < 1:
		# v0 stored settings at the top level.
		if not d.has("settings"):
			var s: Dictionary = {}
			for k: String in defaults()["settings"]:
				if d.has(k):
					s[k] = d[k]
			d["settings"] = s
		v = 1
	return d


## Copies [param src] onto the shape of [param template]: same keys, same
## types; anything else falls back to the template value.
static func _sanitize(template: Dictionary, src: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for key: String in template:
		var t: Variant = template[key]
		if not src.has(key):
			out[key] = t
			continue
		var v: Variant = src[key]
		if typeof(t) == TYPE_DICTIONARY:
			if typeof(v) != TYPE_DICTIONARY:
				out[key] = t
			elif (t as Dictionary).is_empty():
				out[key] = _sanitize_map(v)   # free-form id -> int maps (mastery)
			else:
				out[key] = _sanitize(t, v)
		else:
			out[key] = _clean_value(key, v, t)
	return out


static func _sanitize_map(v: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for k: Variant in v:
		if typeof(k) == TYPE_STRING and typeof(v[k]) in [TYPE_INT, TYPE_FLOAT]:
			out[k] = maxi(0, int(v[k]))
	return out


static func _clean_value(key: String, v: Variant, fallback: Variant) -> Variant:
	match typeof(fallback):
		TYPE_BOOL:
			return v if typeof(v) == TYPE_BOOL else fallback
		TYPE_INT:
			if typeof(v) not in [TYPE_INT, TYPE_FLOAT]:
				return fallback
			var i: int = int(v)
			if RANGES.has(key):
				return clampi(i, RANGES[key][0], RANGES[key][1])
			return maxi(0, i)
		TYPE_FLOAT:
			if typeof(v) not in [TYPE_INT, TYPE_FLOAT] or is_nan(float(v)):
				return fallback
			if RANGES.has(key):
				return clampf(float(v), RANGES[key][0], RANGES[key][1])
			return float(v)
		TYPE_STRING:
			return v if typeof(v) == TYPE_STRING and (v as String).length() <= 64 else fallback
		TYPE_ARRAY:
			if typeof(v) != TYPE_ARRAY:
				return fallback
			var arr: Array = []
			for e: Variant in v:
				if typeof(e) == TYPE_STRING and (e as String).length() <= 64 and not arr.has(e):
					arr.append(e)
			return arr
	return fallback
