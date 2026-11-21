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
	_apply_style()


## Blood Signet look: translucent dark panels with a crimson edge, compact
## bold type, so the readout informs without covering the fight.
func _apply_style() -> void:
	for p: PanelContainer in [$SafeArea/Root/Info, $SafeArea/Root/History]:
		var st := UiTheme.box(Color(0.03, 0.025, 0.035, 0.62), Color(1, 1, 1, 0.06), 0, 1, 14, UiTheme.SKEW * 0.15)
		st.border_width_left = 5
		st.border_color = Color(UiTheme.ACCENT, 0.9)
		p.add_theme_stylebox_override("panel", st)
	for l: Label in [_stats, _history]:
		l.add_theme_font_override("font", UiTheme.bold_font())
		l.add_theme_font_size_override("font_size", 21)
		l.add_theme_color_override("font_color", UiTheme.TEXT)
		l.add_theme_constant_override("line_spacing", -2)
	_history.add_theme_color_override("font_color", UiTheme.MUTED)
	var info := $SafeArea/Root/Info as Control
	info.offset_top = 250.0
	info.offset_right = 520.0
	info.offset_bottom = 250.0          # grows with its text
	var hist := $SafeArea/Root/History as Control
	hist.offset_left = 540.0
	hist.offset_top = 250.0
	hist.offset_right = 700.0
	hist.offset_bottom = 250.0
	var reset := %ResetButton as Button
	reset.theme = UiTheme.get_theme()
	reset.text = "RESET"
	reset.alignment = HORIZONTAL_ALIGNMENT_CENTER
	reset.add_theme_font_size_override("font_size", 34)


static func _name_of(sim: CombatSimulation, id: StringName) -> String:
	var m: MoveData = sim.definitions[0].move_for_id(id)
	return m.display_name if m != null and m.display_name != "" else String(id)


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
			_last_hit_text = "%s  %d dmg  (%d%%)" % [_name_of(sim, ev.move_id), ev.damage, ev.scaling_percent]
		CombatEvent.Type.BLOCK:
			_last_hit_text = "%s  blocked  chip %d" % [_name_of(sim, ev.move_id), ev.damage]
		CombatEvent.Type.COUNTER:
			_last_hit_text = "%s  countered" % _name_of(sim, ev.move_id)


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
		frame = "%s   %df startup  ·  %d active  ·  %d recovery\nOn hit %s   ·   on block %+d%s" % [
			(m.display_name if m.display_name != "" else String(m.id)).to_upper(), m.startup_frames, m.active_frames, m.recovery_frames,
			on_hit, m.advantage_on_block(), "   ·   meter %d" % m.meter_cost if m.meter_cost > 0 else ""]
	_stats.text = "%s\nLast hit  %s\n%s" % [combo, _last_hit_text, frame]
	_history.text = "INPUTS\n" + "\n".join(history.lines(6))
