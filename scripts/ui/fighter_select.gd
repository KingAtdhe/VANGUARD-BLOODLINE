extends MenuScreen
## Fighter select: the six launch fighters as cards, the highlighted one
## standing in the 3D backdrop. Fighters whose movesets aren't implemented
## yet (Milestone 8) can be viewed but not confirmed.

var _selected: StringName = &""
var _cards: Dictionary = {}   # id -> Button
var _name: Label
var _tag: Label
var _meta: Label
var _confirm: Button
var _watermark: Label
var _bars: Dictionary = {}   # stat name -> ProgressBar
const STATS: PackedStringArray = ["POWER", "SPEED", "REACH", "HEALTH"]


func _build() -> void:
	title_label.text = "SELECT FIGHTER  ·  %s" % MatchSetup.MODE_NAMES[ModeFlow.mode].to_upper()
	backdrop.show_arena(&"temple")
	backdrop.fighter_offset = 1.35
	_watermark = make_display("", 340, Color(1, 1, 1, 0.07))
	_watermark.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	_watermark.position = Vector2(-20, -330)
	_watermark.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_watermark.add_theme_constant_override("outline_size", 0)
	content.add_child(_watermark)
	var col := side_column(1020)
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 16)
	grid.add_theme_constant_override("v_separation", 16)
	col.add_child(grid)
	for id: StringName in Catalog.ROSTER:
		var def: FighterDefinition = Catalog.fighter(id)
		var b := make_button(def.display_name.to_upper() + ("" if def.playable else "\nLOCKED"),
			_select.bind(id), Vector2(328, 118), 40)
		b.name = "Card_%s" % id
		b.alignment = HORIZONTAL_ALIGNMENT_CENTER
		var sb := (b.get_theme_stylebox("normal") as StyleBoxFlat).duplicate() as StyleBoxFlat
		sb.border_color = def.accent_color.darkened(0.2 if def.playable else 0.6)
		sb.border_width_bottom = 8
		sb.border_width_left = 2
		b.add_theme_stylebox_override("normal", sb)
		b.focus_entered.connect(_select.bind(id))
		grid.add_child(b)
		_cards[id] = b
	var info := make_panel()
	var il := VBoxContainer.new()
	info.add_child(il)
	_name = make_display("", 84, Color.WHITE)
	_tag = make_label("", 30, UiTheme.MUTED)
	_meta = make_label("", 28, UiTheme.GOLD)
	il.add_child(_name)
	il.add_child(_tag)
	var stats := GridContainer.new()
	stats.columns = 2
	stats.add_theme_constant_override("h_separation", 20)
	stats.add_theme_constant_override("v_separation", 2)
	for s: String in STATS:
		var l := make_label(s, 22, UiTheme.MUTED)
		l.add_theme_font_override("font", UiTheme.bold_font())
		l.custom_minimum_size = Vector2(130, 0)
		stats.add_child(l)
		var bar := ProgressBar.new()
		bar.show_percentage = false
		bar.custom_minimum_size = Vector2(760, 12)
		bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		bar.max_value = 100.0
		stats.add_child(bar)
		_bars[s] = bar
	il.add_child(stats)
	il.add_child(_meta)
	col.add_child(info)
	_confirm = make_button("Confirm", _confirm_pressed, Vector2(1020, 96), 46)
	_confirm.name = "ConfirmButton"
	_confirm.alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(_confirm)
	_select(ModeFlow.p1_id if Catalog.ROSTER.has(ModeFlow.p1_id) else Catalog.ROSTER[0])


func back_scene() -> String:
	return ModeFlow.fighter_select_back()


func selected() -> StringName:
	return _selected


func select(id: StringName) -> void:
	_select(id)


func confirm() -> void:
	_confirm_pressed()


func _select(id: StringName) -> void:
	if id == _selected:
		return
	_selected = id
	var def: FighterDefinition = Catalog.fighter(id)
	backdrop.show_fighter(id)
	_name.text = def.display_name.to_upper()
	_name.add_theme_color_override("font_color", def.accent_color.lightened(0.35))
	_watermark.text = def.display_name.to_upper()
	_watermark.add_theme_color_override("font_color", Color(def.accent_color, 0.12))
	var stat: Dictionary = _stats_of(def)
	for s: String in STATS:
		var bar: ProgressBar = _bars[s]
		var tw := bar.create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		tw.tween_property(bar, "value", float(stat[s]), 0.35)
	_tag.text = def.tagline
	if def.playable:
		_meta.text = "Mastery Lv %d" % Progression.mastery_level(id)
		_confirm.text = "CONFIRM  ›"
		_confirm.disabled = false
	else:
		_meta.text = "Locked — %s" % def.locked_note
		_confirm.text = "NOT PLAYABLE YET"
		_confirm.disabled = true


func _confirm_pressed() -> void:
	var next: String = ModeFlow.fighter_chosen(_selected)
	if next != "":
		SceneRouter.goto(next)


## Display-only ratings (0..100) derived from the fighter's own data, so they
## always match the real tuning. Locked fighters without movesets show their
## movement and health only.
static func _stats_of(def: FighterDefinition) -> Dictionary:
	var power: float = 0.0
	var reach: float = 0.0
	var n: int = 0
	for m: MoveData in def.moves:
		if m == null:
			continue
		power += m.damage
		reach = maxf(reach, m.hitbox_center.x + m.hitbox_size.x * 0.5)
		n += 1
	var speed: float = def.movement.walk_forward_speed if def.movement != null else 2.6
	return {
		"POWER": clampf((power / maxf(1, n)) / 110.0 * 100.0, 8.0, 100.0) if n > 0 else 0.0,
		"SPEED": clampf(speed / 3.6 * 100.0, 8.0, 100.0),
		"REACH": clampf(reach / 1.6 * 100.0, 8.0, 100.0) if n > 0 else 0.0,
		"HEALTH": clampf(float(def.base_health) / 1200.0 * 100.0, 8.0, 100.0),
	}
