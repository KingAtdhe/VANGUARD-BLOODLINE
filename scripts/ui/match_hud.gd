class_name MatchHUD
extends CanvasLayer
## In-match HUD: health bars with damage trail, timer, round pips, names,
## announcer text and a touch pause button. Reads state, never changes it.

signal pause_pressed

## How fast the white damage trail catches up (fraction of max per second).
const TRAIL_SPEED: float = 0.6
const ANNOUNCE_SECONDS: float = 1.2
const PIP_ON := Color(0.95, 0.74, 0.4)        # UiTheme.GOLD
const PIP_OFF := Color(0.16, 0.15, 0.17, 0.9)
## Health colour by remaining fraction (gold → ember → crimson).
const HP_HIGH := Color(0.97, 0.78, 0.36)
const HP_MID := Color(1.0, 0.45, 0.2)
const HP_LOW := Color(0.9, 0.12, 0.16)

@onready var _bars: Array[ProgressBar] = [%P1Health, %P2Health]
@onready var _trails: Array[ProgressBar] = [%P1Trail, %P2Trail]
@onready var _names: Array[Label] = [%P1Name, %P2Name]
@onready var _pips: Array[HBoxContainer] = [%P1Pips, %P2Pips]
@onready var _timer: Label = %TimerLabel
@onready var _round: Label = %RoundLabel
@onready var _announce: Label = %AnnounceLabel
@onready var _pause_button: Button = %PauseButton
@onready var _combo_labels: Array[Label] = [%P1Combo, %P2Combo]
@onready var _meters: Array[ProgressBar] = [%P1Meter, %P2Meter]
@onready var _meter_labels: Array[Label] = [%P1MeterLabel, %P2MeterLabel]
var _accents: Array[Color] = [Color(1.0, 0.15, 0.1), Color(0.25, 0.6, 1.0)]
var _hp_fill: Array[StyleBoxFlat] = []
var _pip_styles: Array = [[], []]

var _announce_left: float = 0.0
var _hold_announce: bool = false
var _training: bool = false
## Seconds each side's "N HITS" stays up after the combo ends.
const COMBO_LINGER: float = 1.0
var _combo_linger: Array[float] = [0.0, 0.0]


func _ready() -> void:
	_pause_button.pressed.connect(func() -> void: pause_pressed.emit())
	_announce.visible = false
	_apply_style()


## "Blood Signet" HUD look (presentation only): angled bars leaning away
## from the centre, display type, a framed timer, crimson announcer.
func _apply_style() -> void:
	var display: Font = UiTheme.display_font()
	for i: int in 2:
		var lean: float = -UiTheme.SKEW if i == 0 else UiTheme.SKEW   # bars lean outwards
		var frame := UiTheme.box(Color(0.03, 0.025, 0.035, 0.88), Color(1, 1, 1, 0.16), 0, 2, 0, lean)
		frame.border_width_bottom = 4
		frame.border_color = Color(UiTheme.ACCENT, 0.9)
		frame.expand_margin_left = 6
		frame.expand_margin_right = 6
		frame.expand_margin_top = 4
		frame.expand_margin_bottom = 4
		_trails[i].add_theme_stylebox_override("background", frame)
		_trails[i].add_theme_stylebox_override("fill", UiTheme.box(Color(1.0, 0.92, 0.85), Color(0, 0, 0, 0), 0, 0, 0, lean))
		var fill := UiTheme.box(HP_HIGH, Color(1, 1, 1, 0.35), 0, 0, 0, lean)
		fill.border_width_top = 5                            # bright top edge reads as a bevel
		_hp_fill.append(fill)
		_bars[i].add_theme_stylebox_override("fill", fill)
		_bars[i].add_theme_stylebox_override("background", StyleBoxEmpty.new())
		_meters[i].add_theme_stylebox_override("background",
			UiTheme.box(Color(0.03, 0.025, 0.035, 0.85), Color(1, 1, 1, 0.12), 0, 1, 0, lean))
		_meters[i].add_theme_stylebox_override("fill", UiTheme.box(Color.WHITE, Color(0, 0, 0, 0), 0, 0, 0, lean))
		_names[i].uppercase = true
		_names[i].add_theme_font_override("font", display)
		_names[i].add_theme_font_size_override("font_size", 52)
		_names[i].add_theme_constant_override("outline_size", 10)
		_meter_labels[i].add_theme_font_override("font", UiTheme.bold_font())
		_meter_labels[i].add_theme_color_override("font_color", UiTheme.GOLD)
		_combo_labels[i].add_theme_font_override("font", display)
		_combo_labels[i].add_theme_font_size_override("font_size", 84)
		_combo_labels[i].add_theme_color_override("font_color", UiTheme.GOLD)
		_combo_labels[i].add_theme_color_override("font_outline_color", UiTheme.ACCENT_DEEP)
		_combo_labels[i].add_theme_constant_override("outline_size", 12)
	# timer in a dark angled frame with a crimson cap
	var tbox := UiTheme.box(Color(0.03, 0.025, 0.035, 0.9), Color(1, 1, 1, 0.12), 0, 1, 0, UiTheme.SKEW * 0.5)
	tbox.border_width_top = 5
	tbox.border_color = UiTheme.ACCENT
	tbox.content_margin_left = 26
	tbox.content_margin_right = 26
	tbox.content_margin_top = -6
	tbox.content_margin_bottom = -10
	_timer.add_theme_stylebox_override("normal", tbox)
	_timer.add_theme_font_override("font", display)
	_timer.add_theme_font_size_override("font_size", 112)
	_round.add_theme_font_override("font", UiTheme.bold_font())
	_round.add_theme_color_override("font_color", UiTheme.EMBER)
	_round.add_theme_font_size_override("font_size", 24)
	_announce.add_theme_font_override("font", display)
	_announce.add_theme_font_size_override("font_size", 220)
	_announce.add_theme_color_override("font_color", Color(1, 0.96, 0.9))
	_announce.add_theme_color_override("font_outline_color", UiTheme.ACCENT)
	_announce.add_theme_constant_override("outline_size", 22)
	_pause_button.theme = UiTheme.get_theme()
	_pause_button.add_theme_font_size_override("font_size", 36)
	_pause_button.alignment = HORIZONTAL_ALIGNMENT_CENTER


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
		_pip_styles[i] = []
		for _r: int in rounds_to_win:
			var pip := Panel.new()
			pip.custom_minimum_size = Vector2(64, 22)
			var st := UiTheme.box(PIP_OFF, Color(1, 1, 1, 0.25), 0, 2, 0, UiTheme.SKEW * 1.4)
			pip.add_theme_stylebox_override("panel", st)
			_pip_styles[i].append(st)
			_pips[i].add_child(pip)
		_pips[i].alignment = BoxContainer.ALIGNMENT_BEGIN if i == 0 else BoxContainer.ALIGNMENT_END


func refresh(sim: CombatSimulation, director: MatchDirector, delta: float) -> void:
	for i: int in 2:
		var hp: float = sim.fighters[i].health
		_bars[i].value = hp
		# Trail snaps up instantly (new round) and drains down smoothly.
		if hp >= _trails[i].value:
			_trails[i].value = hp
		elif director.phase != MatchDirector.Phase.INTRO:
			_trails[i].value = maxf(hp, _trails[i].value - _trails[i].max_value * TRAIL_SPEED * delta)
		var styles: Array = _pip_styles[i]
		for p: int in styles.size():
			(styles[p] as StyleBoxFlat).bg_color = PIP_ON if p < director.round_wins[i] else PIP_OFF
		# gold → ember → crimson as health drops
		if i < _hp_fill.size():
			var frac: float = hp / maxf(1.0, _bars[i].max_value)
			_hp_fill[i].bg_color = HP_LOW.lerp(HP_MID, clampf(frac / 0.3, 0, 1)) if frac < 0.3 \
				else HP_MID.lerp(HP_HIGH, clampf((frac - 0.3) / 0.3, 0, 1))
	# Origin meter: label "MAX" when full, "SURGE" (pulsing) while active.
	for i: int in 2:
		var f: FighterState = sim.fighters[i]
		_meters[i].max_value = sim.tuning.meter_max
		_meters[i].value = f.meter
		var col: Color = _accents[i]
		if f.in_surge():
			_meter_labels[i].text = "SURGE"
			col = col.lightened(0.35 + 0.25 * sin(Time.get_ticks_msec() * 0.015))
		elif f.meter >= sim.tuning.meter_max:
			_meter_labels[i].text = "MAX"
			col = col.lightened(0.3)
		else:
			_meter_labels[i].text = "ORIGIN %d" % f.meter
		_meters[i].modulate = col
	# Combo counter on the ATTACKER's side, counted on the defender.
	for i: int in 2:
		var hits: int = sim.fighters[1 - i].combo_hits
		if hits >= 2:
			_combo_labels[i].text = "%d HITS" % hits
			_combo_labels[i].visible = true
			_combo_linger[i] = COMBO_LINGER
		elif hits == 1 and sim.fighters[1 - i].counter_hit:
			# a single hit that caught the opponent mid-attack
			_combo_labels[i].text = "COUNTER"
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


## Mode banner under the timer ("ARCADE  STAGE 2/5"); empty hides it.
func set_banner(text: String) -> void:
	var b: Label = get_node_or_null("ModeBanner") as Label
	if b == null:
		b = Label.new()
		b.name = "ModeBanner"
		b.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		b.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
		b.offset_top = 300.0
		b.offset_left = -600.0
		b.offset_right = 600.0
		b.add_theme_font_size_override("font_size", 30)
		b.add_theme_color_override("font_color", Color(1.0, 0.82, 0.45))
		b.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
		b.add_theme_constant_override("outline_size", 8)
		add_child(b)
	b.text = text
	b.visible = text != ""


func set_fighter_name(i: int, text: String) -> void:
	_names[i].text = text


func fighter_name(i: int) -> String:
	return _names[i].text


func meter_value(i: int) -> float:
	return _meters[i].value


func meter_text(i: int) -> String:
	return _meter_labels[i].text


func combo_text(i: int) -> String:
	return _combo_labels[i].text if _combo_labels[i].visible else ""


func health_bar_value(i: int) -> float:
	return _bars[i].value
