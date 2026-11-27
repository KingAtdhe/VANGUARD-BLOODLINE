extends Node
## Greybox scene: P1 (local) vs P2 = AI opponent or training dummy.
## Versus (best-of-three, P2 = AI at the menu-selected difficulty) or Training
## (P2 = dummy by default), chosen by match_rules.training.
## The P2 controller can be cycled with T / the debug "P2:" button.
##
## Each render frame:
##   1. CombatClock converts the render delta into N fixed 60 Hz ticks.
##   2. For each tick: sample inputs, snapshot previous state, then
##      MatchDirector.step() (which decides whether inputs reach the
##      simulation and handles rounds/timer/results).
##   3. New combat-log events drive presentation (sparks, flash, camera shake).
##   4. Views interpolate between previous and current tick by clock.alpha().
## Gameplay never reads render delta directly.
##
## Milestone 7: when ModeFlow.setup is set (menus, Story/Arcade/Survival),
## it overrides the exported fighters, arena, rules and CPU difficulty, and
## the arena scene is instanced from the ArenaConfig. Player settings
## (SaveManager) are applied to touch controls, camera, audio and ambience.
##
## Pause uses SceneTree.paused: this scene stops processing entirely, the
## PauseMenu keeps running (PROCESS_MODE_ALWAYS). Leaving the scene always
## unpauses the tree.

@export var arena_config: ArenaConfig
@export var p1_definition: FighterDefinition
@export var p2_definition: FighterDefinition
@export var match_rules: MatchRules
@export var combat_tuning: CombatTuning
## Print combat-log events to stdout as they happen.
@export var print_combat_log: bool = true
## Slow motion on a knockout: speed (1 = off) and how long it lasts (real seconds).
@export_range(0.1, 1.0) var ko_slowmo_scale: float = 0.3
@export var ko_slowmo_seconds: float = 0.9

@onready var _fighter_views: Array[FighterView] = [%Fighter1, %Fighter2]
@onready var _camera_rig: CameraRig = %CameraRig
@onready var _overlay: DebugOverlay = %DebugOverlay
@onready var _hitbox_view: HitboxDebugView = %HitboxDebugView
@onready var _effects: EffectsManager = %EffectsManager
@onready var _hud: MatchHUD = %MatchHUD
@onready var _pause_menu: PauseMenu = %PauseMenu
@onready var _results: MatchResults = %MatchResults
@onready var _touch: TouchControls = %TouchControls
@onready var _training_panel: TrainingPanel = %TrainingPanel
@onready var _audio: CombatAudio = %CombatAudio

var simulation := CombatSimulation.new()
var clock := CombatClock.new()
var dummy := TrainingDummyController.new()
## P2 controllers, cycled in this order.
enum P2Mode { AI_BEGINNER, AI_STANDARD, AI_EXPERT, DUMMY_STAND, DUMMY_BLOCK, DUMMY_JAB }
var p2_mode: P2Mode = P2Mode.AI_STANDARD
var ai: AIController = null
## Optional CPU for P1 (demo / attract mode, automated full-match tests).
var p1_ai: AIController = null
var _matches_started: int = 0
var director: MatchDirector
var _previous: Array[FighterState] = []
var _seen_events: int = 0
var _slowmo_left: float = 0.0
var input_history := InputHistory.new()
## The menu-built setup this match runs with (null = scene's exported data).
var setup: MatchSetup = null
var arena_view: Node3D = null
var outcome: ModeFlow.Outcome = null


func _ready() -> void:
	var problems: Array[String] = []
	if ModeFlow.setup != null and ModeFlow.setup.is_training() == (match_rules != null and match_rules.training):
		problems.append_array(_apply_setup(ModeFlow.setup))
	if arena_config == null or p1_definition == null or p2_definition == null \
			or match_rules == null or combat_tuning == null:
		problems.append("missing arena, fighter, match or tuning data")
	else:
		problems.append_array(arena_config.validate())
		problems.append_array(p1_definition.validate())
		problems.append_array(p2_definition.validate())
		problems.append_array(match_rules.validate())
		problems.append_array(combat_tuning.validate())
	if not problems.is_empty():
		push_error("CombatScene: invalid setup: %s" % ", ".join(problems))
		set_process(false)
		return

	_spawn_arena()
	_apply_player_settings()
	simulation.combat_log.echo_to_stdout = print_combat_log
	simulation.setup(arena_config, p1_definition, p2_definition, combat_tuning)
	# Fighters keep their own Origin colour; a mirror match recolours P2.
	_fighter_views[0].setup(p1_definition, false)
	_fighter_views[1].setup(p2_definition, p2_definition.model_scene == p1_definition.model_scene)
	for v: FighterView in _fighter_views:
		v.set_fighter_lighting(arena_config.fighter_key_color, arena_config.fighter_key_energy,
			arena_config.fighter_rim_color, arena_config.fighter_rim_energy)
	director = MatchDirector.new(match_rules)
	if setup != null:
		director.opening_health = [setup.p1_opening_health, -1]
	director.round_started.connect(_on_round_started)
	if match_rules.training:
		p2_mode = P2Mode.DUMMY_STAND
	elif setup != null:
		p2_mode = setup.ai_difficulty as P2Mode
	else:
		p2_mode = SessionSettings.ai_difficulty as P2Mode
	director.fight_started.connect(_on_fight_started)
	director.round_ended.connect(_on_round_ended)
	director.match_ended.connect(_on_match_ended)

	_camera_rig.configure(arena_config)
	var training: bool = match_rules.training
	_hud.setup(simulation.definitions, match_rules.rounds_to_win, training)
	_training_panel.visible = training
	_training_panel.reset_requested.connect(reset_positions)
	# Player-facing build: debug panel and hitboxes start hidden (F3 / F4).
	_overlay.set_panel_visible(false)
	_overlay.set_tools_visible(training)
	_hitbox_view.visible = false
	_pause_menu.set_training(training)
	_pause_menu.set_left_handed(_touch.left_handed)
	_pause_menu.handedness_toggled.connect(toggle_handedness)
	_touch.touched.connect(_skip_cinematic)
	_hud.pause_pressed.connect(toggle_pause)
	_pause_menu.resume_requested.connect(resume)
	_pause_menu.restart_requested.connect(func() -> void: resume(); restart())
	_pause_menu.quit_requested.connect(_return_to_menu)
	_results.rematch_requested.connect(start_match)
	_results.menu_requested.connect(_return_to_menu)
	_results.continue_requested.connect(_continue_after_match)
	if setup != null:
		_hud.set_banner(setup.banner)
	_overlay.dummy_cycle_requested.connect(cycle_dummy_mode)
	_overlay.hitboxes_toggle_requested.connect(func() -> void: _hitbox_view.visible = not _hitbox_view.visible)
	start_match()
	print("[Combat] greybox ready: mode=%s arena=%s P1=%s P2=%s tick=%dHz rounds_to_win=%d time=%ds buffer=%d" % [
		"training" if training else "versus", arena_config.arena_id, p1_definition.fighter_id,
		p2_definition.fighter_id, CombatConstants.TICK_RATE, match_rules.rounds_to_win,
		match_rules.round_time_seconds, combat_tuning.input_buffer_ticks])
	print("[Combat] P2 controller: %s" % p2_mode_name())


func _exit_tree() -> void:
	# Never leave the whole tree paused behind us.
	if is_inside_tree() and get_tree().paused:
		get_tree().paused = false


func _process(delta: float) -> void:
	if get_tree().paused or director == null:
		return
	# The final blow of a round plays in slow motion (presentation: the
	# simulation just receives fewer ticks per real second for a moment).
	if _slowmo_left > 0.0:
		_slowmo_left -= delta
		delta *= ko_slowmo_scale
	var ticks: int = clock.advance(delta)
	for _i: int in ticks:
		_previous = simulation.snapshot()
		var inputs: Array[FighterInputFrame] = _gather_inputs()
		if director.phase == MatchDirector.Phase.FIGHT:
			input_history.record(inputs[0])
		director.step(simulation, inputs)
	_present_new_events()
	_render(delta)


func _unhandled_input(event: InputEvent) -> void:
	if _camera_rig.in_cinematic() and event.is_pressed() and not event.is_echo():
		_skip_cinematic()
	if event.is_action_pressed(InputActions.PAUSE):
		toggle_pause()
	elif event.is_action_pressed(InputActions.DEBUG_RESET):
		restart()
	elif event.is_action_pressed(InputActions.DEBUG_CYCLE_DUMMY):
		cycle_dummy_mode()


func _notification(what: int) -> void:
	match what:
		NOTIFICATION_WM_GO_BACK_REQUEST:
			# Android back: open the pause menu (back again resumes via PauseMenu).
			if get_tree().paused:
				resume()
			else:
				pause()
		NOTIFICATION_APPLICATION_PAUSED, NOTIFICATION_APPLICATION_FOCUS_OUT:
			# Phone call, home button, notification shade… never keep fighting.
			pause()


# --- match flow -----------------------------------------------------------------

## Starts (or restarts) a clean best-of-N match.
func start_match() -> void:
	_results.hide_results()
	_hud.clear_announce()
	_touch.release_all()
	input_history.clear()
	_training_panel.clear()
	_matches_started += 1
	outcome = null
	ModeFlow.note_match_start()
	_apply_p2_mode()
	clock.reset()
	director.start_match(simulation)
	_previous = simulation.snapshot()
	_seen_events = simulation.combat_log.total_count()
	_render(0.0)


## Ultimate cinematic is presentation-only: skipping just returns the camera.
func _skip_cinematic() -> void:
	if _camera_rig.in_cinematic():
		_camera_rig.skip_cinematic()


## Debug R / pause-menu restart: training resets positions, versus restarts.
func restart() -> void:
	if match_rules.training:
		reset_positions()
	else:
		start_match()


## Training reset (spec M4): spawn positions and full health.
func reset_positions() -> void:
	director.training_reset(simulation)
	_previous = simulation.snapshot()


func toggle_handedness() -> void:
	_touch.set_left_handed(not _touch.left_handed)
	SaveManager.set_setting("left_handed", _touch.left_handed)
	_pause_menu.set_left_handed(_touch.left_handed)


func is_paused() -> bool:
	return get_tree().paused


## Pauses offline play. Ignored once the match is over (results are shown).
func pause() -> void:
	if director == null or director.is_match_over() or get_tree().paused:
		return
	_touch.release_all()  # no stuck walk/attack after resuming
	get_tree().paused = true
	_pause_menu.open()


func resume() -> void:
	_pause_menu.close()
	get_tree().paused = false


func toggle_pause() -> void:
	if get_tree().paused:
		resume()
	else:
		pause()


## Cycles P2 between AI difficulties and dummy modes (debug T / P2 button).
func cycle_dummy_mode() -> void:
	p2_mode = ((p2_mode + 1) % P2Mode.size()) as P2Mode
	_apply_p2_mode()


func p2_mode_name() -> String:
	match p2_mode:
		P2Mode.AI_BEGINNER, P2Mode.AI_STANDARD, P2Mode.AI_EXPERT:
			return "AI %s" % SessionSettings.AI_DIFFICULTY_NAMES[p2_mode]
	return "Dummy %s" % dummy.mode_name()


func _apply_p2_mode() -> void:
	if p2_mode <= P2Mode.AI_EXPERT:
		var profile: AIProfile = load(SessionSettings.ai_profile_path(p2_mode))
		# Seeded per match: reproducible, but not the same fight every rematch.
		ai = AIController.new(profile, 1, p2_definition, p1_definition, 9000 + _matches_started)
		ai.decision_log.echo_to_stdout = print_combat_log and OS.is_debug_build()
	else:
		ai = null
		dummy.mode = (p2_mode - P2Mode.DUMMY_STAND) as TrainingDummyController.Mode
	_overlay.set_dummy_mode(p2_mode_name())
	var cpu: String = "CPU %s" % SessionSettings.AI_DIFFICULTY_NAMES[p2_mode] if ai != null else "Dummy"
	if setup != null and setup.p2_display_name != "":
		_hud.set_fighter_name(1, "%s — %s" % [setup.p2_display_name, cpu])
	else:
		_hud.set_fighter_name(1, "%s — %s" % [p2_definition.display_name, cpu])


func _on_round_started(round_number: int) -> void:
	# The simulation was reset: don't interpolate from last round's positions.
	_previous = simulation.snapshot()
	for v: FighterView in _fighter_views:
		if v.animator != null:
			v.animator.set_override(&"")
	if ai != null:
		ai.reset()
	if p1_ai != null:
		p1_ai.reset()
	if match_rules.training:
		return
	var final_round: bool = director.round_wins[0] == match_rules.rounds_to_win - 1 \
			and director.round_wins[1] == match_rules.rounds_to_win - 1
	_hud.announce("FINAL ROUND" if final_round else "ROUND %d" % round_number, true)


func _on_fight_started(_round_number: int) -> void:
	if not match_rules.training:
		_hud.announce("FIGHT!")
		_audio.play(&"round")


func _on_round_ended(result: MatchDirector.RoundResult) -> void:
	# Victory pose for the winner; a time-out loser slumps (a KO'd one stays down).
	if result.winner >= 0:
		var w: FighterView = _fighter_views[result.winner]
		if w.animator != null:
			w.animator.set_override(simulation.definitions[result.winner].anim_victory)
		var l: FighterView = _fighter_views[1 - result.winner]
		if l.animator != null and result.reason == MatchDirector.Reason.TIME_OUT:
			l.animator.set_override(simulation.definitions[1 - result.winner].anim_defeat)
	_audio.play(&"ko" if result.reason != MatchDirector.Reason.TIME_OUT else &"round")
	if result.winner >= 0:
		ModeFlow.note_round(result.winner, simulation.fighters[result.winner].health,
			simulation.definitions[result.winner].base_health)
	var text: String
	match result.reason:
		MatchDirector.Reason.KO:
			text = "K.O."
		MatchDirector.Reason.DOUBLE_KO:
			text = "DOUBLE K.O."
		MatchDirector.Reason.TIME_OUT:
			text = "TIME"
		MatchDirector.Reason.TIME_OUT_DRAW:
			text = "TIME — DRAW"
	_hud.announce(text, true)


func _on_match_ended(winner: int) -> void:
	_hud.clear_announce()
	_touch.release_all()
	if setup != null:
		outcome = ModeFlow.on_match_end(winner, director.round_wins[0], simulation.fighters[0].health,
			simulation.definitions[0].base_health, director.timer_seconds())
	_results.show_results(director, simulation.definitions, outcome)


# --- per-frame -------------------------------------------------------------------

func _gather_inputs() -> Array[FighterInputFrame]:
	var p2: FighterInputFrame
	if ai != null:
		# The AI only ever receives what is visible on screen (AIObservation);
		# it outputs a normal input frame like a player.
		ai.observe(AIObservation.from_sim(simulation))
		p2 = ai.next_input()
	else:
		p2 = dummy.input_for_tick(simulation.tick + 1)
	var p1: FighterInputFrame
	if p1_ai != null:
		p1_ai.observe(AIObservation.from_sim(simulation))
		p1 = p1_ai.next_input()
	else:
		p1 = LocalInputReader.read()
	return [p1, p2]


func _present_new_events() -> void:
	var combat_log: CombatLog = simulation.combat_log
	for ev: CombatEvent in combat_log.events_since(_seen_events):
		if match_rules.training:
			_training_panel.on_event(ev, simulation)
		_audio.on_event(ev, simulation)
		match ev.type:
			CombatEvent.Type.HIT:
				var m: MoveData = simulation.definitions[ev.actor].move_for_id(ev.move_id)
				_effects.spawn_for(ev, _attack_dir(ev), m)
				_fighter_views[ev.target].flash()
				_camera_rig.add_shake((0.015 + ev.damage / 2500.0) * (1.6 if ev.counter_hit else 1.0))
				_fire_hit(m, ev)
				if m != null and m.tags.has("ultimate"):
					var mid: float = (simulation.fighters[0].position_x + simulation.fighters[1].position_x) * 0.5
					_camera_rig.start_cinematic(mid, float(m.hitstop_frames) / CombatConstants.TICK_RATE)
			CombatEvent.Type.ATTACK_START:
				# D-141 (owner: "ultimate: wind-up pose and camera push-in"): the camera
				# pushes in on the attacker through the wind-up, then the hits carry on
				# with their own cinematic (below). Presentation only.
				var um: MoveData = simulation.definitions[ev.actor].move_for_id(ev.move_id) if ev.actor in [0, 1] else null
				if um != null and um.tags.has("ultimate"):
					var ax: float = simulation.fighters[ev.actor].position_x
					var ox: float = simulation.fighters[1 - ev.actor].position_x
					_camera_rig.start_cinematic(lerpf(ax, ox, 0.3), float(um.startup_frames + 12) / CombatConstants.TICK_RATE)
			CombatEvent.Type.BLOCK:
				_effects.spawn_for(ev, _attack_dir(ev))
				_camera_rig.add_shake(0.008)
			CombatEvent.Type.KNOCKDOWN:
				_fighter_views[ev.target].watch_landing(1.6, 1.0)
			CombatEvent.Type.KO:
				if ev.target == 0 or ev.target == 1:
					_fighter_views[ev.target].watch_landing(2.0, 1.5)
				if not match_rules.training and ko_slowmo_scale < 1.0:
					_slowmo_left = ko_slowmo_seconds
			CombatEvent.Type.PROJECTILE_CLASH, CombatEvent.Type.THROW_BREAK:
				_effects.spawn_for(ev)
				if ev.type == CombatEvent.Type.THROW_BREAK:
					_camera_rig.add_shake(0.01)
			CombatEvent.Type.COUNTER:
				# the caught attacker flashes; the follow-up brings its own hit
				_fighter_views[ev.target].flash()
				_camera_rig.add_shake(0.012)
		_arena_react(ev)
	_seen_events = combat_log.total_count()


## +1 / -1: the direction along X the blow travels (attacker toward target);
## 0 when unknown (a projectile clash).
func _attack_dir(ev: CombatEvent) -> float:
	if ev.actor < 0 or ev.target < 0 or ev.actor > 1 or ev.target > 1:
		return 0.0
	return signf(simulation.fighters[ev.target].position_x - simulation.fighters[ev.actor].position_x)


## A hit by a fire move (D-101): fire bursts from the contact point and the
## target catches fire — long for the ultimate (tag ignite, refreshed by every
## hit), briefly for the fireball (ignite_short). Presentation only: burning
## does no damage.
func _fire_hit(m: MoveData, ev: CombatEvent) -> void:
	if m == null or not (m.tags.has("ignite") or m.tags.has("ignite_short")):
		return
	_effects.spawn_fire_burst(Vector3(ev.point.x, ev.point.y, 0.35), 0.9 if m.tags.has("ignite") else 0.7)
	if ev.target == 0 or ev.target == 1:
		_fighter_views[ev.target].ignite(3.5 if m.tags.has("ignite") else 1.3)


## Lets the arena answer the fight (dust, crowd, glow). Presentation only.
func _arena_react(ev: CombatEvent) -> void:
	if not (arena_view is ArenaView):
		return
	var av: ArenaView = arena_view
	var x: float = (simulation.fighters[0].position_x + simulation.fighters[1].position_x) * 0.5
	if ev.target == 0 or ev.target == 1:
		x = simulation.fighters[ev.target].position_x
	match ev.type:
		CombatEvent.Type.HIT:
			av.react(&"hit", x, clampf(float(ev.damage) / 120.0, 0.0, 1.0))
		CombatEvent.Type.KNOCKDOWN:
			av.react(&"knockdown", x, 1.0)
		CombatEvent.Type.KO:
			av.react(&"ko", x, 1.0)


func _render(delta: float) -> void:
	var alpha: float = clock.alpha()
	var frozen: bool = simulation.hitstop_remaining > 0
	var xs: Array[float] = []
	for i: int in 2:
		_fighter_views[i].sync(_previous[i], simulation.fighters[i], alpha, frozen, delta)
		xs.append(lerpf(_previous[i].position_x, simulation.fighters[i].position_x, alpha))
	_effects.sync_projectiles(simulation.projectiles, 0.0 if frozen else alpha)
	for v: FighterView in _fighter_views:
		var landed: Vector3 = v.consume_landing()
		if landed != Vector3.INF:
			_effects.spawn_ground_slam(landed.x, landed.z, v.landing_strength())
			_camera_rig.add_shake(0.03 * v.landing_strength())
	_hitbox_view.show_boxes(simulation, xs)
	_camera_rig.follow(xs[0], xs[1], delta, maxf(_fighter_views[0].position.y, _fighter_views[1].position.y))
	_hud.refresh(simulation, director, delta)
	_touch.set_action_enabled(InputActions.ULTIMATE, _ultimate_available(0))
	if match_rules.training:
		_training_panel.refresh(simulation, input_history)
	_overlay.set_text(_debug_text(), _log_text())


## True if P1 could use Surge or the ultimate right now (drives the ULT button).
func _ultimate_available(i: int) -> bool:
	var f: FighterState = simulation.fighters[i]
	for m: MoveData in simulation.definitions[i].moves_for(&"ULTIMATE"):
		if OriginMeter.can_use(f, simulation.definitions[i], m, simulation.tuning):
			return true
	return false


func _debug_text() -> String:
	var f: Array[FighterState] = simulation.fighters
	return "\n".join([
		"M5 GREYBOX — F3 panel  F4 boxes  R restart/reset  T cycle P2  Esc/P pause   P2: %s%s" % [
			p2_mode_name(), "  [%s]" % AIController.State.keys()[ai.state] if ai != null else ""],
		"round %d  %s  phase tick %d  timer %d  wins %d-%d" % [
			director.round_number, director.phase_name(), director.phase_ticks,
			director.timer_ticks, director.round_wins[0], director.round_wins[1]],
		"tick %d (60 Hz)  fps %d  hitstop %d  dropped %d  sep %.2f" % [
			simulation.tick, Engine.get_frames_per_second(), simulation.hitstop_remaining,
			clock.dropped_ticks(), simulation.separation()],
		_fighter_line(0, f[0]),
		_fighter_line(1, f[1]),
	])


func _fighter_line(i: int, s: FighterState) -> String:
	var detail: String = ""
	if s.action == FighterState.Action.ATTACK and s.move != null:
		var phase: String = "startup"
		if s.move.is_active_frame(s.move_frame):
			phase = "ACTIVE"
		elif s.move_frame > s.move.startup_frames:
			phase = "recovery"
		detail = "  %s f%d/%d %s" % [s.move.id, s.move_frame, s.move.total_frames(), phase]
	elif s.stun_remaining > 0:
		detail = "  stun %d" % s.stun_remaining
	return "P%d hp %4d  x %+.2f  %s%s" % [i + 1, s.health, s.position_x, s.action_name(), detail]


func _log_text() -> String:
	var lines: PackedStringArray = []
	for ev: CombatEvent in simulation.combat_log.recent(3):
		lines.append(ev.to_text())
	if ai != null:
		for l: String in ai.decision_log.recent(2):
			lines.append(l)
	return "\n".join(lines)


func _return_to_menu() -> void:
	get_tree().paused = false
	SceneRouter.goto(_quit_scene())


## Where "quit"/"menu" leads: the mode's own screen during a run.
func _quit_scene() -> String:
	if outcome != null:
		return outcome.quit_scene
	if setup == null:
		return ScenePaths.MAIN_MENU
	match setup.mode:
		MatchSetup.Mode.STORY:
			return ScenePaths.STORY
		MatchSetup.Mode.ARCADE:
			return ScenePaths.ARCADE
		MatchSetup.Mode.SURVIVAL:
			return ScenePaths.SURVIVAL
	return ScenePaths.MAIN_MENU


func _continue_after_match() -> void:
	get_tree().paused = false
	if outcome != null and outcome.continue_scene != "":
		SceneRouter.goto(outcome.continue_scene)
	else:
		SceneRouter.goto(_quit_scene())


# --- setup, arena, settings ------------------------------------------------------

func _apply_setup(s: MatchSetup) -> Array[String]:
	var problems: Array[String] = s.validate()
	if not problems.is_empty():
		return problems
	setup = s
	p1_definition = Catalog.fighter(s.p1_id)
	p2_definition = Catalog.fighter(s.p2_id)
	arena_config = Catalog.arena(s.arena_id)
	match_rules = load(s.rules_path) as MatchRules
	return problems


## Replaces the placeholder ArenaRoot with the config's arena scene.
func _spawn_arena() -> void:
	var old: Node = get_node_or_null("ArenaRoot")
	if arena_config.scene_path == "" or not ResourceLoader.exists(arena_config.scene_path):
		arena_view = old as Node3D
		return
	var packed: PackedScene = load(arena_config.scene_path)
	var inst: Node3D = packed.instantiate() as Node3D
	if old != null:
		remove_child(old)
		old.queue_free()
	inst.name = "ArenaRoot"
	# Fighters stand on y = 0; a raised stage is brought down to meet them.
	inst.position.y = -arena_config.stage_height
	add_child(inst)
	move_child(inst, 0)
	arena_view = inst


func _apply_player_settings() -> void:
	_touch.left_handed = bool(SaveManager.setting("left_handed"))
	_touch.scale_factor = float(SaveManager.setting("controls_scale"))
	_touch.opacity = float(SaveManager.setting("controls_opacity"))
	match int(SaveManager.setting("touch_controls")):
		1:
			_touch.show_without_touchscreen = true
		2:
			_touch.visible = false
			_touch.show_without_touchscreen = false
	_camera_rig.shake_scale = 0.3 if bool(SaveManager.setting("reduced_shake")) else 1.0
	_camera_rig.cinematics_enabled = bool(SaveManager.setting("cinematics"))
	_audio.volume = float(SaveManager.setting("sfx_volume"))
	AudioServer.set_bus_volume_db(0, linear_to_db(maxf(0.0001, float(SaveManager.setting("master_volume")))))
	if arena_view is ArenaView:
		(arena_view as ArenaView).set_ambient_effects(not bool(SaveManager.setting("reduced_effects")))
