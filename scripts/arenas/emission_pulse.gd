class_name EmissionPulse
extends Node3D
## Animates the emission strength of named arena materials (Origin veins,
## neon glyphs, the heart). Works on the per-surface materials ArenaView
## swaps in, matched by resource_name. Hidden (reduced effects) = steady glow.

@export var material_names: PackedStringArray = []
## Seconds per cycle.
@export var period: float = 2.0
## Emission multiplier range relative to the material's own strength.
@export var low: float = 0.7
@export var high: float = 1.3
## Neon-style: mostly steady with short random dips instead of a smooth wave.
@export var flicker: bool = false
## Responds to ArenaView.react() (big hits, knockdowns, KOs) with a flare.
@export var reacts: bool = false

var _flare: float = 0.0

var _mats: Array[Material] = []
var _base: Array[float] = []
var _t: float = 0.0
var _dip: float = 0.0


var _scanned: bool = false


## Children are ready before their ArenaView parent, which is where the
## textured materials are swapped in, so the scan waits for the first frame.
func _scan() -> void:
	_scanned = true
	var root: Node = get_parent()
	while root != null and not (root is ArenaView):
		root = root.get_parent()
	if root == null:
		return
	for n: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n
		for s: int in mi.get_surface_override_material_count():
			var m: Material = mi.get_surface_override_material(s)
			if m == null or not material_names.has(m.resource_name) or _mats.has(m):
				continue
			if m is BaseMaterial3D:
				_mats.append(m)
				_base.append((m as BaseMaterial3D).emission_energy_multiplier)
			elif m is ShaderMaterial and (m as ShaderMaterial).get_shader_parameter("emission_energy") != null:
				_mats.append(m)
				_base.append(float((m as ShaderMaterial).get_shader_parameter("emission_energy")))


func _process(delta: float) -> void:
	if not _scanned:
		_scan()
	_t += delta
	var k: float = 1.0
	if visible:
		if flicker:
			_dip = maxf(0.0, _dip - delta * 6.0)
			if randf() < delta * 0.6:
				_dip = 1.0
			k = lerpf(high, low * 0.4, _dip)
		else:
			k = lerpf(low, high, 0.5 + 0.5 * sin(_t * TAU / maxf(0.05, period)))
	_flare = maxf(0.0, _flare - delta * 1.5)
	k *= 1.0 + _flare
	for i: int in _mats.size():
		_set_energy(_mats[i], _base[i] * k)


## Temporary brightness boost (0..1+), decays over about a second.
func flare(amount: float) -> void:
	if reacts:
		_flare = maxf(_flare, amount)


func _set_energy(m: Material, e: float) -> void:
	if m is BaseMaterial3D:
		(m as BaseMaterial3D).emission_energy_multiplier = e
	elif m is ShaderMaterial:
		(m as ShaderMaterial).set_shader_parameter("emission_energy", e)


func _exit_tree() -> void:
	for i: int in _mats.size():
		_set_energy(_mats[i], _base[i])
