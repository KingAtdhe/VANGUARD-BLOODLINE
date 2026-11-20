extends RefCounted
## Milestone 7 acceptance with real scenes: every menu builds and has a way
## back (no dead ends), every button leads to a real scene, mode setups run
## in the combat scene with the right fighters/arena/rules, results always
## offer a way out, and settings are applied to a match.


func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree


func _spawn(path: String) -> Node:
	var n: Node = (load(path) as PackedScene).instantiate()
	_tree().root.add_child(n)
	return n


func _free(n: Node) -> void:
	_tree().paused = false
	n.get_parent().remove_child(n)
	n.free()


func test_every_menu_builds_and_has_a_way_back() -> Array[String]:
	var f: Array[String] = []
	ModeFlow.begin(MatchSetup.Mode.ARCADE)
	ModeFlow.fighter_chosen(&"kairo")
	for path: String in ScenePaths.MENUS:
		var s: Node = _spawn(path)
		if not s.is_node_ready() or not (s is MenuScreen):
			f.append("%s did not build as a MenuScreen" % path)
			_free(s)
			continue
		var back: String = (s as MenuScreen).back_scene()
		if path == ScenePaths.MAIN_MENU:
			if back != "":
				f.append("main menu should not have Back")
		elif not ScenePaths.ALL.has(back):
			f.append("%s: Back leads to '%s' (dead end)" % [path, back])
		var usable: int = 0
		for b: Node in s.find_children("*", "Button", true, false):
			if (b as Button).visible and not (b as Button).disabled:
				usable += 1
		if usable == 0:
			f.append("%s has no usable button" % path)
		_free(s)
	return f


func test_main_menu_routes_every_mode() -> Array[String]:
	var f: Array[String] = []
	var s: Node = _spawn(ScenePaths.MAIN_MENU)
	for btn: String in ["MenuStory", "MenuArcade", "MenuVersus", "MenuTraining", "MenuSurvival", "MenuProfile",
			"MenuSettings", "MenuQuit"]:
		var b: Button = s.find_child(btn, true, false) as Button
		if b == null or b.disabled:
			f.append("main menu entry %s missing or disabled" % btn)
	_free(s)
	for m: int in MatchSetup.Mode.size():
		var target: String = ModeFlow.begin(m as MatchSetup.Mode)
		if not ScenePaths.ALL.has(target):
			f.append("%s leads to unknown scene %s" % [MatchSetup.MODE_NAMES[m], target])
	return f


func test_fighter_and_arena_select() -> Array[String]:
	var f: Array[String] = []
	ModeFlow.begin(MatchSetup.Mode.VERSUS)
	var s: Node = _spawn(ScenePaths.FIGHTER_SELECT)
	if s.find_children("Card_*", "Button", true, false).size() != 6:
		f.append("fighter select should show the six launch fighters")
	s.select(&"nox")
	if not (s.find_child("ConfirmButton", true, false) as Button).disabled:
		f.append("a locked fighter can be confirmed")
	if (s.backdrop as MenuBackdrop).fighter_id != &"nox":
		f.append("backdrop does not show the highlighted fighter")
	s.select(&"kairo")
	if (s.find_child("ConfirmButton", true, false) as Button).disabled:
		f.append("Kairo cannot be confirmed")
	_free(s)
	ModeFlow.fighter_chosen(&"kairo")
	var a: Node = _spawn(ScenePaths.ARENA_SELECT)
	a.select(&"neon")
	if not (a.find_child("ConfirmButton", true, false) as Button).disabled:
		f.append("a locked arena can be confirmed")
	a.select(&"temple")
	if (a.backdrop as MenuBackdrop).arena_id != &"temple":
		f.append("arena backdrop not updated")
	_free(a)
	return f


func test_story_screen_dialogue_flow() -> Array[String]:
	var f: Array[String] = []
	ModeFlow.begin(MatchSetup.Mode.STORY)
	var s: Node = _spawn(ScenePaths.STORY)
	if s.dialogue_visible():
		f.append("story should open on the chapter list")
	if (s.find_child("Chapter2", true, false) as Button).disabled == false:
		f.append("chapter 2 is open on a new save")
	if not s.open_chapter(0) or not s.dialogue_visible():
		f.append("chapter 1 dialogue did not open")
	var lines: int = (ModeFlow.story_chapters()[0]["intro"] as Array).size()
	for _i: int in lines - 1:
		s.advance()
	if (s.find_child("NextButton", true, false) as Button).text.find("FIGHT") < 0:
		f.append("last intro line should offer FIGHT")
	(s as MenuScreen).go_back()   # Back from dialogue returns to the list
	if s.dialogue_visible():
		f.append("Back from a dialogue did not return to the chapter list")
	_free(s)
	return f


func _run_match(scene: Node, p1_wins: bool) -> void:
	var sim: CombatSimulation = scene.simulation
	var d: MatchDirector = scene.director
	var guard: int = 0
	while not d.is_match_over() and guard < 20000:
		guard += 1
		if d.phase == MatchDirector.Phase.FIGHT:
			# Decisive KO each round (outcome plumbing is under test, not combat).
			var loser: FighterState = sim.fighters[1 if p1_wins else 0]
			loser.health = 0
			loser.action = FighterState.Action.KO
		scene._process(1.0 / 60.0)


func test_mode_matches_run_in_the_combat_scene() -> Array[String]:
	var f: Array[String] = []
	# Story chapter 1 in the Forgotten Temple vs a Sentinel.
	ModeFlow.begin(MatchSetup.Mode.STORY)
	ModeFlow.open_story_chapter(0)
	var path: String = ModeFlow.start_story_fight()
	var scene: Node = _spawn(path)
	if not scene.is_node_ready() or scene.simulation.fighters.size() != 2:
		_free(scene)
		return ["combat scene did not start from a story setup"]
	if scene.arena_config.arena_id != &"temple" or not (scene.arena_view is ArenaView):
		f.append("story arena not instanced (got %s)" % scene.arena_config.arena_id)
	if scene.p2_definition.fighter_id != &"sentinel" or scene.p2_mode != scene.P2Mode.AI_BEGINNER:
		f.append("story opponent/difficulty wrong")
	if not scene._hud.fighter_name(1).begins_with("Sentinel Initiate"):
		f.append("story opponent title not on the HUD: %s" % scene._hud.fighter_name(1))
	_run_match(scene, true)
	var labels: PackedStringArray = scene._results.button_labels()
	if not labels.has("CONTINUE") or scene.outcome == null or scene.outcome.continue_scene != ScenePaths.STORY:
		f.append("story win results should Continue to the story: %s" % labels)
	if int(SaveManager.section("progress")["story_cleared"]) != 1:
		f.append("story progress not saved by the match")
	_free(scene)
	# Survival: one round, health carried into the next match.
	ModeFlow.begin(MatchSetup.Mode.SURVIVAL)
	ModeFlow.fighter_chosen(&"kairo")
	ModeFlow.survival_health = 600
	scene = _spawn(ModeFlow.start_survival_match())
	if scene.simulation.fighters[0].health != 600 or scene.match_rules.rounds_to_win != 1:
		f.append("survival opening health/rules not applied (hp %d)" % scene.simulation.fighters[0].health)
	_run_match(scene, false)
	labels = scene._results.button_labels()
	if labels.has("REMATCH") or labels.has("RETRY") or labels.is_empty():
		f.append("survival loss results wrong: %s" % labels)
	_free(scene)
	return f


func test_results_always_offer_a_way_out() -> Array[String]:
	var f: Array[String] = []
	for m: MatchSetup.Mode in [MatchSetup.Mode.VERSUS, MatchSetup.Mode.ARCADE]:
		for p1_wins: bool in [true, false]:
			ModeFlow.begin(m)
			ModeFlow.fighter_chosen(&"kairo")
			var path: String = ModeFlow.arena_chosen(&"ascendant") if m == MatchSetup.Mode.VERSUS else ModeFlow.start_arcade_stage()
			var scene: Node = _spawn(path)
			_run_match(scene, p1_wins)
			var r: MatchResults = scene._results
			if not r.visible or r.button_labels().is_empty():
				f.append("%s %s: results without buttons" % [MatchSetup.MODE_NAMES[m], p1_wins])
			if scene.outcome != null:
				for target: String in [scene.outcome.continue_scene, scene.outcome.quit_scene]:
					if target != "" and not ScenePaths.ALL.has(target):
						f.append("results route to unknown scene %s" % target)
			_free(scene)
	return f


func test_settings_apply_to_a_match() -> Array[String]:
	var f: Array[String] = []
	SaveManager.set_setting("left_handed", true)
	SaveManager.set_setting("controls_scale", 1.3)
	SaveManager.set_setting("reduced_shake", true)
	SaveManager.set_setting("cinematics", false)
	SaveManager.set_setting("reduced_effects", true)
	SaveManager.unload()   # "restart the app"
	ModeFlow.begin(MatchSetup.Mode.VERSUS)
	ModeFlow.fighter_chosen(&"kairo")
	var scene: Node = _spawn(ModeFlow.arena_chosen(&"ascendant"))
	if not scene._touch.left_handed or absf(scene._touch.scale_factor - 1.3) > 0.001:
		f.append("touch settings not applied")
	if scene._camera_rig.shake_scale >= 1.0 or scene._camera_rig.cinematics_enabled:
		f.append("camera settings not applied")
	for n: Node in scene.arena_view.find_children("*", "GPUParticles3D", true, false):
		if (n as GPUParticles3D).emitting:
			f.append("reduced effects left %s emitting" % n.name)
			break
	scene.toggle_handedness()
	SaveManager.unload()
	if SaveManager.setting("left_handed") != false:
		f.append("handedness toggled in a match was not saved")
	_free(scene)
	var settings: Node = _spawn(ScenePaths.SETTINGS)
	var slider: HSlider = settings.controls["sfx_volume"]
	slider.value = 0.35
	SaveManager.unload()
	if absf(float(SaveManager.setting("sfx_volume")) - 0.35) > 0.001:
		f.append("settings screen change not persisted")
	_free(settings)
	return f


func test_roster_models_and_arenas() -> Array[String]:
	var f: Array[String] = []
	for id: StringName in Catalog.ROSTER + [&"sentinel", &"warden", &"training_dummy"]:
		var def: FighterDefinition = Catalog.fighter(id)
		if def == null or def.model_scene == null:
			f.append("%s has no model" % id)
			continue
		var model: Node = def.model_scene.instantiate()
		ModelUtil.enable_vertex_colors(model)
		for n: Node in model.find_children("*", "MeshInstance3D", true, false):
			var painted: Mesh = (n as MeshInstance3D).mesh
			for s: int in painted.get_surface_count():
				var pm := painted.surface_get_material(s) as StandardMaterial3D
				var cols: Variant = painted.surface_get_arrays(s)[Mesh.ARRAY_COLOR]
				if pm != null and cols != null and (cols as PackedColorArray).size() > 0 and not pm.vertex_color_use_as_albedo:
					f.append("%s surface %d ignores its vertex colours (would render white)" % [id, s])
		var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false) as AnimationPlayer
		for anim: StringName in def.required_animations():
			if ap == null or not ap.has_animation(anim):
				f.append("%s missing animation %s" % [id, anim])
				break
		var tris: int = 0
		var accent: bool = false
		for n: Node in model.find_children("*", "MeshInstance3D", true, false):
			var mesh: Mesh = (n as MeshInstance3D).mesh
			if mesh.get_surface_count() > 6:
				f.append("%s uses %d materials (max 6)" % [id, mesh.get_surface_count()])
			for s: int in mesh.get_surface_count():
				tris += (mesh.surface_get_arrays(s)[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
				var mat: Material = mesh.surface_get_material(s)
				if mat != null and mat.resource_name.ends_with("_Accent"):
					accent = true
		if tris > 45000:
			f.append("%s: %d triangles exceeds the fighter budget" % [id, tris])
		if not accent:
			f.append("%s has no Accent material for recolouring" % id)
		model.free()
	for id: StringName in Catalog.ARENAS:
		var cfg: ArenaConfig = Catalog.arena(id)
		if cfg == null or not cfg.validate().is_empty() or not ResourceLoader.exists(cfg.scene_path):
			f.append("arena %s config/scene invalid" % id)
			continue
		var arena: Node = (load(cfg.scene_path) as PackedScene).instantiate()
		if not (arena is ArenaView) or (arena as ArenaView).config != cfg:
			f.append("arena %s scene does not point at its config" % id)
		if not cfg.unlocked_by_default and cfg.unlock_hint == "":
			f.append("locked arena %s has no unlock hint" % id)
		# Textured surface materials (tools/blender/arena_builder.py) must load.
		(arena as ArenaView).apply_surface_materials()
		var textured: int = 0
		for mn: Node in arena.find_children("*", "MeshInstance3D", true, false):
			var mi: MeshInstance3D = mn
			for si: int in mi.get_surface_override_material_count():
				var om: Material = mi.get_surface_override_material(si)
				if om is ShaderMaterial and (om as ShaderMaterial).get_shader_parameter("albedo_tex") != null:
					textured += 1
		if textured < 3:
			f.append("arena %s: only %d textured surfaces" % [id, textured])
		# The arena answers a KO: impact dust fires (presentation only).
		var dust: Node = arena.get_node_or_null("Reactions/ImpactDust")
		if not (dust is GPUParticles3D):
			f.append("arena %s has no Reactions/ImpactDust" % id)
		else:
			(arena as ArenaView).react(&"ko", 1.0, 1.0)
			if not (dust as GPUParticles3D).emitting:
				f.append("arena %s: KO reaction did not fire the impact dust" % id)
		if arena.find_children("*", "WorldEnvironment", true, false).is_empty():
			f.append("arena %s has no environment" % id)
		var tris: int = 0
		for n: Node in arena.find_children("*", "MeshInstance3D", true, false):
			var mesh: Mesh = (n as MeshInstance3D).mesh
			for s: int in mesh.get_surface_count():
				tris += (mesh.surface_get_arrays(s)[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
		if tris < 1000 or tris > 80000:
			f.append("arena %s: %d triangles outside 1k–80k" % [id, tris])
		arena.free()
	return f
