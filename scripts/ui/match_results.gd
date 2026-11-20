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
var _winner_name: Label
var _score_row: HBoxContainer
var _rounds_row: HBoxContainer


func _ready() -> void:
	visible = false
	UiTheme.apply_overlay(self)
	_rematch.pressed.connect(func() -> void: rematch_requested.emit())
	_menu.pressed.connect(func() -> void: menu_requested.emit())
	_continue.pressed.connect(func() -> void: continue_requested.emit())
	_build_layout()


## Results layout (presentation): the winner's name huge, the "P1 WINS"
## title under it in gold, a scoreboard row (names either side of the round
## score) and one chip per round with how it ended.
func _build_layout() -> void:
	var list: VBoxContainer = _title.get_parent() as VBoxContainer
	list.add_theme_constant_override("separation", 16)
	list.alignment = BoxContainer.ALIGNMENT_CENTER
	var dim := get_node_or_null("Dim") as ColorRect
	if dim != null:
		dim.color = Color(0.02, 0.015, 0.02, 0.72)
	_winner_name = _display("", 170, Color.WHITE)
	_winner_name.add_theme_color_override("font_outline_color", UiTheme.ACCENT)
	_winner_name.add_theme_constant_override("outline_size", 18)
	_winner_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var head := VBoxContainer.new()             # name and "P1 WINS" set tight together
	head.add_theme_constant_override("separation", -46)
	list.add_child(head)
	list.move_child(head, _title.get_index())
	_title.reparent(head)
	head.add_child(_winner_name)
	head.move_child(_winner_name, 0)
	_title.add_theme_font_override("font", UiTheme.display_font())
	_title.add_theme_font_size_override("font_size", 60)
	_title.add_theme_color_override("font_color", UiTheme.GOLD)
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_score_row = HBoxContainer.new()
	_score_row.alignment = BoxContainer.ALIGNMENT_CENTER
	_score_row.add_theme_constant_override("separation", 40)
	list.add_child(_score_row)
	list.move_child(_score_row, _detail.get_index())
	_rounds_row = HBoxContainer.new()
	_rounds_row.alignment = BoxContainer.ALIGNMENT_CENTER
	_rounds_row.add_theme_constant_override("separation", 14)
	list.add_child(_rounds_row)
	list.move_child(_rounds_row, _detail.get_index())
	_detail.visible = false           # kept as plain text for accessibility/tests
	_rewards.add_theme_color_override("font_color", UiTheme.GOLD)
	_rewards.add_theme_font_size_override("font_size", 32)
	_rewards.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	(_rematch.get_parent() as HBoxContainer).alignment = BoxContainer.ALIGNMENT_CENTER
	(_rematch.get_parent() as HBoxContainer).add_theme_constant_override("separation", 18)
	for b: Button in [_rematch, _continue, _menu]:
		b.custom_minimum_size = Vector2(380, 104)
		b.alignment = HORIZONTAL_ALIGNMENT_CENTER


func _fill_layout(director: MatchDirector, defs: Array[FighterDefinition]) -> void:
	var w: int = director.match_winner
	_winner_name.text = "DRAW" if w < 0 else defs[w].display_name.to_upper()
	for c: Node in _score_row.get_children():
		c.queue_free()
	for c: Node in _rounds_row.get_children():
		c.queue_free()
	for i: int in 2:
		var nm := _display(defs[i].display_name.to_upper(), 56,
			Color.WHITE if w == i else UiTheme.MUTED)
		nm.custom_minimum_size = Vector2(420, 0)
		nm.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT if i == 0 else HORIZONTAL_ALIGNMENT_LEFT
		_score_row.add_child(nm)
		if i == 0:
			_score_row.add_child(_display("%d  —  %d" % [director.round_wins[0], director.round_wins[1]],
				96, UiTheme.GOLD))
	for r: MatchDirector.RoundResult in director.results:
		var who: String = "DRAW" if r.winner < 0 else defs[r.winner].display_name
		_rounds_row.add_child(_chip("R%d  %s  ·  %s" % [r.round_number, who, _reason_text(r.reason)],
			UiTheme.GOLD if r.winner == 0 else (UiTheme.ACCENT if r.winner == 1 else UiTheme.MUTED)))


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
	_fill_layout(director, defs)
	if outcome == null:
		_rematch.text = "REMATCH"
		_rematch.visible = true
		_continue.visible = false
		_menu.text = "MAIN MENU"
		_rewards.text = ""
	else:
		_title.text = outcome.headline
		_rewards.text = "\n".join(outcome.lines)
		_rematch.text = outcome.rematch_label.to_upper()
		_rematch.visible = outcome.rematch_label != ""
		_continue.text = outcome.continue_label.to_upper()
		_continue.visible = outcome.continue_label != ""
		_menu.text = outcome.quit_label.to_upper()
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


static func _display(text: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", UiTheme.display_font())
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


static func _chip(text: String, color: Color) -> PanelContainer:
	var chip := PanelContainer.new()
	var st := UiTheme.box(Color(color, 0.2), color, 0, 2, 8, UiTheme.SKEW)
	st.content_margin_left = 18
	st.content_margin_right = 18
	chip.add_theme_stylebox_override("panel", st)
	var l := Label.new()
	l.text = text.to_upper()
	l.add_theme_font_override("font", UiTheme.bold_font())
	l.add_theme_font_size_override("font_size", 24)
	l.add_theme_color_override("font_color", color.lightened(0.3))
	chip.add_child(l)
	return chip


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
