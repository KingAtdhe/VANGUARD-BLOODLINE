class_name FighterView
extends Node3D
## Visual representation of one fighter. Reads FighterState, never writes it.
## Placeholder capsule until the Blender model arrives (Milestone 6).

@export var body_color: Color = Color(0.8, 0.2, 0.2)
@export var label_text: String = "FIGHTER"

@onready var _body: MeshInstance3D = %Body
@onready var _facing_marker: Node3D = %FacingMarker
@onready var _label: Label3D = %NameLabel

var _material: StandardMaterial3D


func _ready() -> void:
	_material = StandardMaterial3D.new()
	_material.albedo_color = body_color
	_material.roughness = 0.7
	_body.material_override = _material
	_label.text = label_text


## Places the view between two tick states. [param alpha] in 0..1.
func sync(previous: FighterState, current: FighterState, alpha: float) -> void:
	if previous == null or current == null:
		return
	position.x = lerpf(previous.position_x, current.position_x, alpha)
	# Facing flips instantly; turning animations come with real models.
	_facing_marker.scale.x = float(current.facing)
