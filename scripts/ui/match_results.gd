class_name MatchResults
extends CanvasLayer
## End-of-match results: unambiguous winner (or draw), round score and the
## reason for each round. In a mode run (ModeFlow.Outcome) it also shows the
## rewards and the mode's own options: Retry / Next stage / Continue / Ladder…
## Every state offers at least one way out (no dead ends).

signal rematch_requested
signal menu_requested
signal continue_requested

@onready var _title: Label = %ResultTitle
@onready var _detail: Label = %ResultDetail
@onready var _rematch: Button = %RematchButton
@onready var _continue: Button = %ContinueButton
@onready var _menu: Button = %MenuButton
@onready var _rewards: Label = %RewardLines


func _ready() -> void:
	visible = false
	_rematch.pressed.connect(func() -> void: rematch_requested.emit())
	_menu.pressed.connect(func() -> void: menu_requested.emit())
	_continue.pressed.connect(func() -> void: continue_requested.emit())


func show_results(director: MatchDirector, defs: Array[FighterDefinition], outcome: ModeFlow.Outcome = null) -> void:
	if director.match_winner < 0:
		_title.text = "DRAW"
	else:
		_title.text = "P%d WINS" % (director.match_winner + 1)
	var lines: PackedStringArray = []
	lines.append("%s  %d  —  %d  %s" % [defs[0].display_name, director.round_wins[0],
		director.round_wins[1], defs[1].display_name])
	for r: MatchDirector.RoundResult in director.results:
		lines.append("Round %d: %s — %s" % [r.round_number,
			"Draw" if r.winner < 0 else "P%d" % (r.winner + 1), _reason_text(r.reason)])
	_detail.text = "\n".join(lines)
	if outcome == null:
		_rematch.text = "Rematch"
		_rematch.visible = true
		_continue.visible = false
		_menu.text = "Main menu"
		_rewards.text = ""
	else:
		_title.text = outcome.headline
		_rewards.text = "\n".join(outcome.lines)
		_rematch.text = outcome.rematch_label
		_rematch.visible = outcome.rematch_label != ""
		_continue.text = outcome.continue_label
		_continue.visible = outcome.continue_label != ""
		_menu.text = outcome.quit_label
	_rewards.visible = _rewards.text != ""
	visible = true
	if _continue.visible:
		_continue.grab_focus()
	elif _rematch.visible:
		_rematch.grab_focus()
	else:
		_menu.grab_focus()


## Labels of the visible buttons, in order (tests / accessibility).
func button_labels() -> PackedStringArray:
	var out: PackedStringArray = []
	for b: Button in [_rematch, _continue, _menu]:
		if b.visible:
			out.append(b.text)
	return out


func hide_results() -> void:
	visible = false


func title_text() -> String:
	return _title.text


static func _reason_text(reason: MatchDirector.Reason) -> String:
	match reason:
		MatchDirector.Reason.KO:
			return "K.O."
		MatchDirector.Reason.DOUBLE_KO:
			return "Double K.O."
		MatchDirector.Reason.TIME_OUT:
			return "Time (more health)"
		MatchDirector.Reason.TIME_OUT_DRAW:
			return "Time (equal health)"
	return "?"
