class_name MatchResults
extends CanvasLayer
## End-of-match results: unambiguous winner (or draw), round score and the
## reason for each round. Offers Rematch or Main Menu.

signal rematch_requested
signal menu_requested

@onready var _title: Label = %ResultTitle
@onready var _detail: Label = %ResultDetail
@onready var _rematch: Button = %RematchButton


func _ready() -> void:
	visible = false
	_rematch.pressed.connect(func() -> void: rematch_requested.emit())
	%MenuButton.pressed.connect(func() -> void: menu_requested.emit())


func show_results(director: MatchDirector, defs: Array[FighterDefinition]) -> void:
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
	visible = true
	_rematch.grab_focus()


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
