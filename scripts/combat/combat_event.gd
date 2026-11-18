class_name CombatEvent
extends RefCounted
## One entry in the combat log, stamped with the simulation tick.

enum Type { ATTACK_START, HIT, BLOCK, WHIFF, KO, RESET }

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


func type_name() -> String:
	return Type.keys()[type]


func to_text() -> String:
	var who: String = "P%d" % (actor + 1) if actor >= 0 else "--"
	match type:
		Type.ATTACK_START:
			return "t%d %s starts %s" % [tick, who, move_id]
		Type.HIT:
			return "t%d %s %s HIT P%d  -%d  (hp %d)  stop %d" % [
				tick, who, move_id, target + 1, damage, target_health, hitstop]
		Type.BLOCK:
			return "t%d %s %s BLOCKED by P%d  chip %d  (hp %d)  stop %d" % [
				tick, who, move_id, target + 1, damage, target_health, hitstop]
		Type.WHIFF:
			return "t%d %s %s whiffed" % [tick, who, move_id]
		Type.KO:
			return "t%d P%d KO" % [tick, target + 1]
		Type.RESET:
			return "t%d reset" % tick
	return "t%d %s" % [tick, type_name()]
