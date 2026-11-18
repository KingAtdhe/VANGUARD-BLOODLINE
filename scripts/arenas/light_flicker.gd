extends Light3D
## Torch/neon flicker. Render-time only: never touches gameplay state.

@export var base_energy: float = 2.0
@export var amount: float = 0.25
@export var speed: float = 9.0

var _t: float = 0.0
var _seed: float = 0.0


func _ready() -> void:
	_seed = float(get_instance_id() % 997)
	base_energy = light_energy if base_energy <= 0.0 else base_energy


func _process(delta: float) -> void:
	_t += delta * speed
	var n: float = sin(_t + _seed) * 0.5 + sin(_t * 2.3 + _seed * 1.7) * 0.3 + sin(_t * 5.1) * 0.2
	light_energy = base_energy * (1.0 + n * amount)
