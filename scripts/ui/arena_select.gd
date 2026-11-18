extends MenuScreen
## Arena select (Versus and Training). The backdrop shows the highlighted
## arena from the fight camera's point of view. Locked arenas show how to
## earn them.

var _selected: StringName = &""
var _name: Label
var _tag: Label
var _confirm: Button


func _build() -> void:
	title_label.text = "SELECT ARENA"
	backdrop.framing = "arena"
	var col := side_column(860)
	for id: StringName in Catalog.ARENAS:
		var cfg: ArenaConfig = Catalog.arena(id)
		var open: bool = Catalog.is_arena_unlocked(id)
		var b := make_button(cfg.display_name.to_upper() + ("" if open else "   · LOCKED"), _select.bind(id),
			Vector2(860, 110), 40)
		b.name = "Arena_%s" % id
		b.focus_entered.connect(_select.bind(id))
		col.add_child(b)
	var info := make_panel()
	var il := VBoxContainer.new()
	info.add_child(il)
	_name = make_label("", 48, Color.WHITE)
	_tag = make_label("", 30, UiTheme.MUTED)
	il.add_child(_name)
	il.add_child(_tag)
	col.add_child(info)
	_confirm = make_button("Fight  ›", _confirm_pressed, Vector2(860, 116), 48)
	_confirm.name = "ConfirmButton"
	_confirm.alignment = HORIZONTAL_ALIGNMENT_CENTER
	col.add_child(_confirm)
	_select(Catalog.ARENAS[0])


func back_scene() -> String:
	return ScenePaths.FIGHTER_SELECT


func select(id: StringName) -> void:
	_select(id)


func confirm() -> void:
	_confirm_pressed()


func _select(id: StringName) -> void:
	_selected = id
	var cfg: ArenaConfig = Catalog.arena(id)
	backdrop.show_arena(id)
	_name.text = cfg.display_name.to_upper()
	if Catalog.is_arena_unlocked(id):
		_tag.text = cfg.tagline
		_confirm.disabled = false
		_confirm.text = "Training  ›" if ModeFlow.mode == MatchSetup.Mode.TRAINING else "Fight  ›"
	else:
		_tag.text = "%s\nUnlock: clear Story chapter 3 or the Arcade ladder." % cfg.tagline
		_confirm.disabled = true
		_confirm.text = "Locked"


func _confirm_pressed() -> void:
	var next: String = ModeFlow.arena_chosen(_selected)
	if next != "":
		SceneRouter.goto(next)
