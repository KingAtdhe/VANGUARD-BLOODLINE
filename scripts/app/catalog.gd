class_name Catalog
extends RefCounted
## Content lookup by id: fighters and arenas. Data stays in data/; this only
## knows where it is, so menus and modes never hard-code resource paths.

## Fighter select order (spec §3 launch roster).
const ROSTER: Array[StringName] = [&"kairo", &"drakon", &"seraphina", &"nox", &"vexa", &"ryuen"]
## Selectable arenas, in select-screen order.
const ARENAS: Array[StringName] = [&"ascendant", &"temple", &"neon", &"origin"]


static func fighter_path(id: StringName) -> String:
	return "res://data/fighters/%s.tres" % id


static func arena_path(id: StringName) -> String:
	return "res://data/arenas/%s_arena.tres" % id


static func fighter(id: StringName) -> FighterDefinition:
	var p: String = fighter_path(id)
	return load(p) as FighterDefinition if ResourceLoader.exists(p) else null


static func arena(id: StringName) -> ArenaConfig:
	var p: String = arena_path(id)
	return load(p) as ArenaConfig if ResourceLoader.exists(p) else null


static func is_arena_unlocked(id: StringName) -> bool:
	var a: ArenaConfig = arena(id)
	if a == null:
		return false
	return a.unlocked_by_default or (SaveManager.section("progress")["unlocked_arenas"] as Array).has(String(id))
