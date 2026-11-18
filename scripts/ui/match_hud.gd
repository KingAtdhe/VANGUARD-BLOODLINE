class_name MatchHUD
extends CanvasLayer
## In-match HUD: health bars with damage trail, timer, round pips, names,
## announcer text and a touch pause button. Reads state, never changes it.

signal pause_pressed

## How fast the white damage trail catches up (fraction of max per second).
const TRAIL_SPEED: float = 0.6
const ANNOUNCE_SECONDS: float = 1.2
const PIP_ON := Color(1.0, 0.8, 0.2)
const PIP_OFF := Color(0.25, 0.25, 0.28)

@onready var _bars: Array[ProgressBar] = [%P1Health, %P2Health]
@onready var _trails: Array[ProgressBar] = [%P1Trail, %P2Trail]
@onready var _names: Array[Label] = [%P1Name, %P2Name]
@onready var _pips: Array[HBoxContainer] = [%P1Pips, %P2Pips]
@onready var _timer: Label = %TimerLabel
@onready var _round: Label = %RoundLabel
@onready var _announce: Label = %AnnounceLabel
@onready var _pause_button: Button = %PauseButton
@onready var _combo_labels: Array[Label] = [%P1Combo, %P2Combo]

var _announce_left: float = 0.0
var _hold_announce: bool = false
var _training: bool = false
## Seconds each side's "N HITS" stays up after the combo ends.
const COMBO_LINGER: float = 1.0
var _combo_linger: Array[float] = [0.0, 0.0]


func _ready() -> void:
	_pause_button.pressed.connect(func() -> void: pause_pressed.emit())
	_announce.visible = false


func setup(defs: Array[FighterDefinition], rounds_to_win: int, training: bool = false) -> void:
	_training = training
	for i: int in 2:
		_combo_labels[i].visible = false
		_pips[i].visible = not training
		_names[i].text = defs[i].display_name
		_bars[i].max_value = defs[i].base_health
		_trails[i].max_value = defs[i].base_health
		_bars[i].value = defs[i].base_health
		_trails[i].value = defs[i].base_health
		for c: Node in _pips[i].get_children():
			c.queue_free()
		for _r: int in rounds_to_win:
			var pip := ColorRect.new()
			pip.custom_minimum_size = Vector2(70, 30)
			pip.color = PIP_OFF
			_pips[i].add_child(pip)


func refresh(sim: CombatSimulation, director: MatchDirector, delta: float) -> void:
	for i: int in 2:
		var hp: float = sim.fighters[i].health
		_bars[i].value = hp
		# Trail snaps up instantly (new round) and drains down smoothly.
		if hp >= _trails[i].value:
			_trails[i].value = hp
		elif director.phase != MatchDirector.Phase.INTRO:
			_trails[i].value = maxf(hp, _trails[i].value - _trails[i].max_value * TRAIL_SPEED * delta)
		var pips: Array[Node] = _pips[i].get_children()
		for p: int in pips.size():
			(pips[p] as ColorRect).color = PIP_ON if p < director.round_wins[i] else PIP_OFF
	# Combo counter on the ATTACKER's side, counted on the defender.
	for i: int in 2:
		var hits: int = sim.fighters[1 - i].combo_hits
		if hits >= 2:
			_combo_labels[i].text = "%d HITS" % hits
			_combo_labels[i].visible = true
			_combo_linger[i] = COMBO_LINGER
		elif _combo_linger[i] > 0.0:
			_combo_linger[i] -= delta
			if _combo_linger[i] <= 0.0:
				_combo_labels[i].visible = false
	_timer.text = "∞" if _training else str(director.timer_seconds())
	_round.text = "TRAINING" if _training else "ROUND %d" % director.round_number
	if not _hold_announce and _announce_left > 0.0:
		_announce_left -= delta
		if _announce_left <= 0.0:
			_announce.visible = false


## Shows big centre text. [param hold] keeps it until replaced.
func announce(text: String, hold: bool = false) -> void:
	_announce.text = text
	_announce.visible = true
	_announce_left = ANNOUNCE_SECONDS
	_hold_announce = hold


func clear_announce() -> void:
	_announce.visible = false
	_hold_announce = false
	_announce_left = 0.0


func announce_text() -> String:
	return _announce.text if _announce.visible else ""


func combo_text(i: int) -> String:
	return _combo_labels[i].text if _combo_labels[i].visible else ""


func health_bar_value(i: int) -> float:
	return _bars[i].value
