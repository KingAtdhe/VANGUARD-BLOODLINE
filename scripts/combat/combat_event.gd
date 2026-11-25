class_name CombatEvent
extends RefCounted
## One entry in the combat log, stamped with the simulation tick.

enum Type { ATTACK_START, HIT, BLOCK, WHIFF, KO, RESET, SURGE_START, SURGE_END, KNOCKDOWN, COUNTER,
	PROJECTILE_FIRED, PROJECTILE_CLASH, DASH, JUMP, THROW_BREAK }

var tick: int = 0
var type: Type = Type.HIT
## Fighter indices (0 = P1, 1 = P2); -1 when not applicable.
var actor: int = -1
var target: int = -1
var move_id: StringName = &""
var damage: int = 0
## Target health after the event.
var target_health: int = 0
## Contact point on the fighting plane (x, height) for effects.
var point: Vector2 = Vector2.ZERO
var hitstop: int = 0
## ATTACK_START: id of the move this one cancelled ("" = not a cancel).
var cancel_from: StringName = &""
## HIT: which hit of the combo this was (1 = first) and scaling applied.
var combo_hits: int = 0
var scaling_percent: int = 100
## HIT: the target's armour absorbed it (damage taken, no stun).
var armored: bool = false
## HIT: it interrupted the target's own attack before its recovery.
var counter_hit: bool = false


func type_name() -> String:
	return Type.keys()[type]


func to_text() -> String:
	var who: String = "P%d" % (actor + 1) if actor >= 0 else "--"
	match type:
		Type.ATTACK_START:
			if cancel_from != &"":
				return "t%d %s cancels %s -> %s" % [tick, who, cancel_from, move_id]
			return "t%d %s starts %s" % [tick, who, move_id]
		Type.HIT:
			var combo: String = "" if combo_hits <= 1 else "  combo %d (%d%%)" % [combo_hits, scaling_percent]
			return "t%d %s %s HIT P%d  -%d  (hp %d)  stop %d%s" % [
				tick, who, move_id, target + 1, damage, target_health, hitstop, combo + ("  ARMOUR" if armored else "") + ("  COUNTER HIT" if counter_hit else "")]
		Type.BLOCK:
			return "t%d %s %s BLOCKED by P%d  chip %d  (hp %d)  stop %d" % [
				tick, who, move_id, target + 1, damage, target_health, hitstop]
		Type.COUNTER:
			return "t%d %s %s COUNTERED P%d" % [tick, who, move_id, target + 1]
		Type.THROW_BREAK:
			return "t%d %s breaks P%d's %s" % [tick, who, target + 1, move_id]
		Type.DASH, Type.JUMP:
			return "t%d %s %s" % [tick, who, move_id]
		Type.PROJECTILE_FIRED:
			return "t%d %s %s fired" % [tick, who, move_id]
		Type.PROJECTILE_CLASH:
			return "t%d projectiles clash" % tick
		Type.WHIFF:
			return "t%d %s %s whiffed" % [tick, who, move_id]
		Type.KO:
			return "t%d P%d KO" % [tick, target + 1]
		Type.SURGE_START:
			return "t%d %s ORIGIN SURGE" % [tick, who]
		Type.SURGE_END:
			return "t%d %s surge ends" % [tick, who]
		Type.KNOCKDOWN:
			return "t%d P%d knocked down" % [tick, target + 1]
		Type.RESET:
			return "t%d reset" % tick
	return "t%d %s" % [tick, type_name()]
