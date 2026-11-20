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


func _build() -> void:
	title_label.text = "SELECT FIGHTER  ·  %s" % MatchSetup.MODE_NAMES[ModeFlow.mode].to_upper()
	backdrop.show_arena(&"temple")
	backdrop.fighter_offset = 1.35
	var col := side_column(1020)
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 16)
	grid.add_theme_constant_override("v_separation", 16)
	col.add_child(grid)
	for id: StringName in Catalog.ROSTER:
		var def: FighterDefinition = Catalog.fighter(id)
		var b := make_button(def.display_name.to_upper() + ("" if def.playable else "\nLOCKED · M8"),
			_select.bind(id), Vector2(328, 150), 44)
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
	_name = make_display("", 96, Color.WHITE)
	_tag = make_label("", 30, UiTheme.MUTED)
	_meta = make_label("", 28, UiTheme.GOLD)
	il.add_child(_name)
	il.add_child(_tag)
	il.add_child(_meta)
	col.add_child(info)
	_confirm = make_button("Confirm", _confirm_pressed, Vector2(1020, 110), 46)
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
