extends Node
## Greybox versus scene: P1 (local) vs the training dummy in a best-of-three
## match.
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

var simulation := CombatSimulation.new()
var clock := CombatClock.new()
var dummy := TrainingDummyController.new()
var director: MatchDirector
var _previous: Array[FighterState] = []
var _seen_events: int = 0


func _ready() -> void:
	var problems: Array[String] = []
	if arena_config == null or p1_definition == null or p2_definition == null or match_rules == null:
		problems.append("missing arena, fighter or match data")
	else:
		problems.append_array(arena_config.validate())
		problems.append_array(p1_definition.validate())
		problems.append_array(p2_definition.validate())
		problems.append_array(match_rules.validate())
	if not problems.is_empty():
		push_error("CombatScene: invalid setup: %s" % ", ".join(problems))
		set_process(false)
		return

	simulation.combat_log.echo_to_stdout = print_combat_log
	simulation.setup(arena_config, p1_definition, p2_definition)
	director = MatchDirector.new(match_rules)
	director.round_started.connect(_on_round_started)
	director.fight_started.connect(_on_fight_started)
	director.round_ended.connect(_on_round_ended)
	director.match_ended.connect(_on_match_ended)

	_camera_rig.configure(arena_config)
	_hud.setup(simulation.definitions, match_rules.rounds_to_win)
	_hud.pause_pressed.connect(toggle_pause)
	_pause_menu.resume_requested.connect(resume)
	_pause_menu.restart_requested.connect(func() -> void: resume(); start_match())
	_pause_menu.quit_requested.connect(_return_to_menu)
	_results.rematch_requested.connect(start_match)
	_results.menu_requested.connect(_return_to_menu)
	_overlay.dummy_cycle_requested.connect(cycle_dummy_mode)
	_overlay.hitboxes_toggle_requested.connect(func() -> void: _hitbox_view.visible = not _hitbox_view.visible)
	_overlay.set_dummy_mode(dummy.mode_name())

	start_match()
	print("[Combat] greybox ready: arena=%s P1=%s P2=%s tick=%dHz rounds_to_win=%d time=%ds" % [
		arena_config.arena_id, p1_definition.fighter_id, p2_definition.fighter_id,
		CombatConstants.TICK_RATE, match_rules.rounds_to_win, match_rules.round_time_seconds])


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
		director.step(simulation, _gather_inputs())
	_present_new_events()
	_render(delta)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(InputActions.PAUSE):
		toggle_pause()
	elif event.is_action_pressed(InputActions.DEBUG_RESET):
		start_match()
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
	clock.reset()
	director.start_match(simulation)
	_previous = simulation.snapshot()
	_seen_events = simulation.combat_log.total_count()
	_render(0.0)


func is_paused() -> bool:
	return get_tree().paused


## Pauses offline play. Ignored once the match is over (results are shown).
func pause() -> void:
	if director == null or director.is_match_over() or get_tree().paused:
		return
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


func cycle_dummy_mode() -> void:
	dummy.next_mode()
	_overlay.set_dummy_mode(dummy.mode_name())


func _on_round_started(round_number: int) -> void:
	# The simulation was reset: don't interpolate from last round's positions.
	_previous = simulation.snapshot()
	var final_round: bool = director.round_wins[0] == match_rules.rounds_to_win - 1 \
			and director.round_wins[1] == match_rules.rounds_to_win - 1
	_hud.announce("FINAL ROUND" if final_round else "ROUND %d" % round_number, true)


func _on_fight_started(_round_number: int) -> void:
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
	_results.show_results(director, simulation.definitions)


# --- per-frame -------------------------------------------------------------------

func _gather_inputs() -> Array[FighterInputFrame]:
	# P2 is a scripted training dummy until the AI milestone (M5).
	return [LocalInputReader.read(), dummy.input_for_tick(simulation.tick + 1)]


func _present_new_events() -> void:
	var combat_log: CombatLog = simulation.combat_log
	for ev: CombatEvent in combat_log.events_since(_seen_events):
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
	_overlay.set_text(_debug_text(), _log_text())


func _debug_text() -> String:
	var f: Array[FighterState] = simulation.fighters
	return "\n".join([
		"M3 GREYBOX — F3 panel  F4 boxes  R restart match  T dummy  Esc/P pause",
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
	for ev: CombatEvent in simulation.combat_log.recent(4):
		lines.append(ev.to_text())
	return "\n".join(lines)


func _return_to_menu() -> void:
	get_tree().paused = false
	SceneRouter.goto(ScenePaths.MAIN_MENU)
