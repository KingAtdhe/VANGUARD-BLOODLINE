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

var simulation := CombatSimulation.new()
var clock := CombatClock.new()
var dummy := TrainingDummyController.new()
## P2 controllers, cycled in this order.
enum P2Mode { AI_BEGINNER, AI_STANDARD, AI_EXPERT, DUMMY_STAND, DUMMY_BLOCK, DUMMY_JAB }
var p2_mode: P2Mode = P2Mode.AI_STANDARD
var ai: AIController = null
var _matches_started: int = 0
var director: MatchDirector
var _previous: Array[FighterState] = []
var _seen_events: int = 0
var input_history := InputHistory.new()


func _ready() -> void:
	var problems: Array[String] = []
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

	simulation.combat_log.echo_to_stdout = print_combat_log
	simulation.setup(arena_config, p1_definition, p2_definition, combat_tuning)
	director = MatchDirector.new(match_rules)
	director.round_started.connect(_on_round_started)
	p2_mode = P2Mode.DUMMY_STAND if match_rules.training else (SessionSettings.ai_difficulty as P2Mode)
	director.fight_started.connect(_on_fight_started)
	director.round_ended.connect(_on_round_ended)
	director.match_ended.connect(_on_match_ended)

	_camera_rig.configure(arena_config)
	var training: bool = match_rules.training
	_hud.setup(simulation.definitions, match_rules.rounds_to_win, training)
	_training_panel.visible = training
	_training_panel.reset_requested.connect(reset_positions)
	_overlay.set_panel_visible(not training)  # F3 still toggles it
	_pause_menu.set_training(training)
	_pause_menu.set_left_handed(_touch.left_handed)
	_pause_menu.handedness_toggled.connect(toggle_handedness)
	_hud.pause_pressed.connect(toggle_pause)
	_pause_menu.resume_requested.connect(resume)
	_pause_menu.restart_requested.connect(func() -> void: resume(); restart())
	_pause_menu.quit_requested.connect(_return_to_menu)
	_results.rematch_requested.connect(start_match)
	_results.menu_requested.connect(_return_to_menu)
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
	_apply_p2_mode()
	clock.reset()
	director.start_match(simulation)
	_previous = simulation.snapshot()
	_seen_events = simulation.combat_log.total_count()
	_render(0.0)


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
	_hud.set_fighter_name(1, "%s — %s" % [p2_definition.display_name, cpu])


func _on_round_started(round_number: int) -> void:
	# The simulation was reset: don't interpolate from last round's positions.
	_previous = simulation.snapshot()
	if ai != null:
		ai.reset()
	if match_rules.training:
		return
	var final_round: bool = director.round_wins[0] == match_rules.rounds_to_win - 1 \
			and director.round_wins[1] == match_rules.rounds_to_win - 1
	_hud.announce("FINAL ROUND" if final_round else "ROUND %d" % round_number, true)


func _on_fight_started(_round_number: int) -> void:
	if not match_rules.training:
		_hud.announce("FIGHT!")


func _on_round_ended(result: MatchDirector.RoundResult) -> void:
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


func _on_match_ended(_winner: int) -> void:
	_hud.clear_announce()
	_touch.release_all()
	_results.show_results(director, simulation.definitions)


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
	return [LocalInputReader.read(), p2]


func _present_new_events() -> void:
	var combat_log: CombatLog = simulation.combat_log
	for ev: CombatEvent in combat_log.events_since(_seen_events):
		if match_rules.training:
			_training_panel.on_event(ev, simulation)
		match ev.type:
			CombatEvent.Type.HIT:
				_effects.spawn_for(ev)
				_fighter_views[ev.target].flash()
				_camera_rig.add_shake(0.015 + ev.damage / 2500.0)
			CombatEvent.Type.BLOCK:
				_effects.spawn_for(ev)
				_camera_rig.add_shake(0.008)
	_seen_events = combat_log.total_count()


func _render(delta: float) -> void:
	var alpha: float = clock.alpha()
	var frozen: bool = simulation.hitstop_remaining > 0
	var xs: Array[float] = []
	for i: int in 2:
		_fighter_views[i].sync(_previous[i], simulation.fighters[i], alpha, frozen, delta)
		xs.append(lerpf(_previous[i].position_x, simulation.fighters[i].position_x, alpha))
	_hitbox_view.show_boxes(simulation, xs)
	_camera_rig.follow(xs[0], xs[1], delta)
	_hud.refresh(simulation, director, delta)
	if match_rules.training:
		_training_panel.refresh(simulation, input_history)
	_overlay.set_text(_debug_text(), _log_text())


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
	SceneRouter.goto(ScenePaths.MAIN_MENU)
