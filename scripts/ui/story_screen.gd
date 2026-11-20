extends MenuScreen
## Story mode (spec §6.1): chapter list → short dialogue scene → fight →
## closing scene with rewards → chapter list. Chapters unlock in order;
## cleared chapters can be replayed. Text comes from data/story/chapters.json.

var _list: VBoxContainer
var _dialogue: PanelContainer
var _speaker: Label
var _line: Label
var _rewards: Label
var _next: Button
var _skip: Button
var _lines: Array = []
var _index: int = 0


func _build() -> void:
	title_label.text = "STORY  ·  %s" % ModeFlow.story().get("title", "").to_upper()
	backdrop.show_fighter(&"kairo")
	backdrop.fighter_offset = 1.3
	_list = side_column(1000)
	_list.add_theme_constant_override("separation", 12)
	_build_list()
	_dialogue = make_panel()
	_dialogue.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	_dialogue.offset_top = -400
	content.add_child(_dialogue)
	var dl := VBoxContainer.new()
	dl.add_theme_constant_override("separation", 12)
	_dialogue.add_child(dl)
	var plate := PanelContainer.new()              # skewed crimson nameplate
	plate.add_theme_stylebox_override("panel", UiTheme.box(UiTheme.ACCENT, UiTheme.EMBER, 0, 0, 10, UiTheme.SKEW))
	plate.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_speaker = make_display("", 52, Color.WHITE)
	plate.add_child(_speaker)
	_line = make_label("", 38, Color.WHITE)
	_line.custom_minimum_size = Vector2(0, 96)
	_rewards = make_label("", 32, UiTheme.GOLD)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_END
	row.add_theme_constant_override("separation", 20)
	_skip = make_button("Skip", _skip_pressed, Vector2(240, 90), 34)
	_skip.name = "SkipButton"
	_next = make_button("Next  ›", _next_pressed, Vector2(360, 90), 38)
	_next.name = "NextButton"
	row.add_child(_skip)
	row.add_child(_next)
	for n: Control in [plate, _line, _rewards, row]:
		dl.add_child(n)
	if ModeFlow.story_phase == 0:
		_show_list()
	else:
		_start_dialogue()


func back_scene() -> String:
	return ScenePaths.MAIN_MENU


func go_back() -> void:
	if ModeFlow.story_phase != 0:
		ModeFlow.story_phase = 0   # leave the scene, back to the chapter list
		_show_list()
		return
	super.go_back()


## Test hooks.
func open_chapter(i: int) -> bool:
	if not ModeFlow.open_story_chapter(i):
		return false
	_start_dialogue()
	return true


func advance() -> void:
	_next_pressed()


func dialogue_visible() -> bool:
	return _dialogue.visible


func _build_list() -> void:
	var cleared: int = int(SaveManager.section("progress")["story_cleared"])
	var chapters: Array = ModeFlow.story_chapters()
	# progress strip
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 22)
	var cap := make_label("CHAPTERS CLEARED", 24, UiTheme.MUTED)
	cap.add_theme_font_override("font", UiTheme.bold_font())
	cap.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	cap.autowrap_mode = TextServer.AUTOWRAP_OFF
	head.add_child(cap)
	head.add_child(make_display("%d / %d" % [cleared, chapters.size()], 56, UiTheme.GOLD))
	var bar := ProgressBar.new()
	bar.max_value = chapters.size()
	bar.value = cleared
	bar.show_percentage = false
	bar.custom_minimum_size = Vector2(0, 14)
	bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	head.add_child(bar)
	_list.add_child(head)
	for i: int in chapters.size():
		var ch: Dictionary = chapters[i]
		var parts: PackedStringArray = String(ch["title"]).split("—", false, 1)
		var name: String = parts[1].strip_edges() if parts.size() > 1 else String(ch["title"])
		var unlocked: bool = ModeFlow.story_unlocked(i)
		var arena: ArenaConfig = Catalog.arena(StringName(ch["arena"]))
		var where: String = arena.display_name if arena != null else ""
		var sub: String = "%s  ·  vs %s" % [where, ch.get("opponent_name", "")] if unlocked else "Clear chapter %d to unlock" % i
		var chip: String = "CLEARED" if i < cleared else ("NEW" if unlocked else "LOCKED")
		var col: Color = UiTheme.GOLD if i < cleared else (UiTheme.ACCENT if unlocked else UiTheme.LOCKED)
		var current: bool = unlocked and i >= cleared
		var b := make_card("%02d" % (i + 1), name, sub, chip, col, _open.bind(i), Vector2(1000, 100),
			current, not unlocked) as Button
		b.name = "Chapter%d" % (i + 1)
		b.disabled = not unlocked
		_list.add_child(b)


func _show_list() -> void:
	_list.visible = true
	_dialogue.visible = false
	backdrop.show_arena(&"temple")
	backdrop.show_fighter(&"kairo")
	backdrop.play_pose(&"KAIRO_IDLE_A")
	_focus_first()


func _open(i: int) -> void:
	if ModeFlow.open_story_chapter(i):
		_start_dialogue()


func _start_dialogue() -> void:
	var ch: Dictionary = ModeFlow.story_chapters()[ModeFlow.story_chapter]
	backdrop.show_arena(StringName(ch["arena"]))
	_list.visible = false
	_dialogue.visible = true
	_lines = ch["intro"] if ModeFlow.story_phase == 1 else ch["outro"]
	_index = 0
	_rewards.text = ""
	if ModeFlow.story_phase == 2:
		backdrop.play_pose(&"KAIRO_VICTORY")
	title_label.text = String(ch["title"]).to_upper()
	_show_line()


func _show_line() -> void:
	var last: bool = _index >= _lines.size() - 1
	if _index < _lines.size():
		_speaker.text = String(_lines[_index][0]).to_upper()
		_show_speaker(String(_lines[_index][0]))
		_line.text = String(_lines[_index][1])
	if last:
		if ModeFlow.story_phase == 1:
			_next.text = "FIGHT  ›"
		else:
			_rewards.text = "\n".join(ModeFlow.story_reward_lines)
			_next.text = "CHAPTER COMPLETE  ›"
	else:
		_next.text = "NEXT  ›"
	_skip.visible = not last
	_next.grab_focus()


## The backdrop shows whoever is talking (Kairo, Ryuen, the chapter's opponent).
func _show_speaker(who: String) -> void:
	var ch: Dictionary = ModeFlow.story_chapters()[ModeFlow.story_chapter]
	var id: StringName = &""
	if who == String(ch.get("opponent_name", "")):
		id = StringName(ch.get("opponent", ""))
	else:
		for f: StringName in Catalog.ROSTER:
			var d: FighterDefinition = Catalog.fighter(f)
			if d != null and d.display_name.to_lower() == who.to_lower():
				id = f
	if id == &"" or Catalog.fighter(id) == null:
		return
	if id != backdrop.fighter_id:
		backdrop.show_fighter(id)
		backdrop.play_pose(&"KAIRO_VICTORY" if ModeFlow.story_phase == 2 and id == &"kairo" else &"KAIRO_IDLE_A")


func _next_pressed() -> void:
	if _index < _lines.size() - 1:
		_index += 1
		_show_line()
		return
	if ModeFlow.story_phase == 1:
		SceneRouter.goto(ModeFlow.start_story_fight())
	else:
		ModeFlow.story_phase = 0
		SceneRouter.goto(ScenePaths.STORY)   # rebuild the list with the new unlock


func _skip_pressed() -> void:
	_index = maxi(0, _lines.size() - 1)
	_show_line()


func _gui_input(event: InputEvent) -> void:
	# Tap anywhere on the dialogue to advance.
	if _dialogue.visible and event is InputEventScreenTouch and (event as InputEventScreenTouch).pressed:
		_next_pressed()
