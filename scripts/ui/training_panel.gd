class_name TrainingPanel
extends CanvasLayer
## Training-mode readout (spec §4.5, §6.1): current/last combo (hits,
## damage), last hit's scaling, frame data of P1's last move, P1 input
## history, and a Reset button.

signal reset_requested

@onready var _stats: Label = %StatsLabel
@onready var _history: Label = %HistoryLabel

var _last_combo_hits: int = 0
var _last_combo_damage: int = 0
var _last_hit_text: String = "-"
var _last_move: MoveData = null


func _ready() -> void:
	%ResetButton.pressed.connect(func() -> void: reset_requested.emit())


func clear() -> void:
	_last_combo_hits = 0
	_last_combo_damage = 0
	_last_hit_text = "-"
	_last_move = null


## Feed every new combat event (only P1's actions are tracked).
func on_event(ev: CombatEvent, sim: CombatSimulation) -> void:
	if ev.actor != 0:
		return
	match ev.type:
		CombatEvent.Type.ATTACK_START:
			_last_move = sim.definitions[0].move_for_id(ev.move_id)
		CombatEvent.Type.HIT:
			_last_combo_hits = ev.combo_hits
			_last_combo_damage = sim.fighters[1].combo_damage
			_last_hit_text = "%s  %d dmg  (%d%%)" % [ev.move_id, ev.damage, ev.scaling_percent]
		CombatEvent.Type.BLOCK:
			_last_hit_text = "%s  blocked  chip %d" % [ev.move_id, ev.damage]


func refresh(sim: CombatSimulation, history: InputHistory) -> void:
	var live: int = sim.fighters[1].combo_hits
	var combo: String
	if live > 0:
		combo = "COMBO  %d hits  %d dmg" % [live, sim.fighters[1].combo_damage]
	else:
		combo = "Last combo  %d hits  %d dmg" % [_last_combo_hits, _last_combo_damage]
	var frame: String = "Move  -"
	if _last_move != null:
		var m: MoveData = _last_move
		var on_hit: String = "KD" if m.knockdown else "%+d" % m.advantage_on_hit()
		frame = "Move  %s  S%d A%d R%d  total %d\n      on hit %s   on block %+d%s" % [
			m.id, m.startup_frames, m.active_frames, m.recovery_frames, m.total_frames(),
			on_hit, m.advantage_on_block(), "   meter %d" % m.meter_cost if m.meter_cost > 0 else ""]
	_stats.text = "TRAINING\n%s\nLast hit  %s\n%s" % [combo, _last_hit_text, frame]
	_history.text = "P1 input (newest first)\n" + "\n".join(history.lines(10))
