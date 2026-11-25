class_name CombatAudio
extends Node
## Plays combat sounds from combat-log events (presentation only).
## Placeholder synthesized SFX until final audio (audio/sfx/placeholder_*).

const VOICES: int = 8
const SFX: Dictionary = {
	&"hit_light": "res://audio/sfx/placeholder_hit_light.wav",
	&"hit_heavy": "res://audio/sfx/placeholder_hit_heavy.wav",
	&"block": "res://audio/sfx/placeholder_block.wav",
	&"whiff": "res://audio/sfx/placeholder_whiff.wav",
	&"special": "res://audio/sfx/placeholder_special.wav",
	&"surge": "res://audio/sfx/placeholder_surge.wav",
	&"ultimate": "res://audio/sfx/placeholder_ultimate.wav",
	&"knockdown": "res://audio/sfx/placeholder_knockdown.wav",
	&"ko": "res://audio/sfx/placeholder_ko.wav",
	&"round": "res://audio/sfx/placeholder_ui_round.wav",
}

@export_range(0.0, 1.0) var volume: float = 0.8

var _players: Array[AudioStreamPlayer] = []
var _streams: Dictionary = {}
var _next: int = 0
## Headless runs (tests/CI) have no audio output and fast-forward time, so
## sounds are only recorded in [member played], never started.
var _silent: bool = DisplayServer.get_name() == "headless"
## Names played so far (for tests/debug).
var played: Array[StringName] = []


func _ready() -> void:
	for k: StringName in SFX:
		_streams[k] = load(SFX[k])
	for i: int in VOICES:
		var p := AudioStreamPlayer.new()
		add_child(p)
		_players.append(p)


func _exit_tree() -> void:
	# Stop and release playbacks so nothing outlives the scene (avoids a
	# leaked AudioStreamPlayback when quitting mid-sound).
	for p: AudioStreamPlayer in _players:
		p.stop()
		p.stream = null


func play(name: StringName, pitch: float = 1.0) -> void:
	if not _streams.has(name):
		return
	played.append(name)
	if _silent:
		return
	var p: AudioStreamPlayer = _players[_next]
	_next = (_next + 1) % VOICES
	p.stream = _streams[name]
	p.pitch_scale = pitch
	p.volume_db = linear_to_db(maxf(0.001, volume))
	p.play()


func on_event(ev: CombatEvent, sim: CombatSimulation) -> void:
	var move: MoveData = null
	if ev.actor >= 0 and ev.move_id != &"":
		move = sim.definitions[ev.actor].move_for_id(ev.move_id)
	match ev.type:
		CombatEvent.Type.ATTACK_START:
			if move != null and move.tags.has("special"):
				play(&"special")
		CombatEvent.Type.WHIFF:
			play(&"whiff", 1.1)
		CombatEvent.Type.HIT:
			if move != null and move.tags.has("ultimate"):
				play(&"ultimate")
			else:
				play(&"hit_heavy" if ev.damage >= 60 else &"hit_light", 1.0 + 0.04 * ev.combo_hits)
		CombatEvent.Type.BLOCK:
			play(&"block")
		CombatEvent.Type.COUNTER:
			play(&"block", 1.35)
		CombatEvent.Type.THROW_BREAK:
			play(&"block", 0.85)
		CombatEvent.Type.SURGE_START:
			play(&"surge")
		CombatEvent.Type.KNOCKDOWN:
			play(&"knockdown")
		CombatEvent.Type.KO:
			play(&"ko")
