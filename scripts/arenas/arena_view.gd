class_name ArenaView
extends Node3D
## Presentation root of an arena scene: geometry (Blender GLB), lighting,
## environment, ambient effects and signage. Purely visual — the gameplay
## bounds come from [member config] (ArenaConfig) only, never from meshes.
##
## Nodes in the group "arena_fx" are optional ambience (particles, flicker)
## and are switched off by the "reduced effects" setting.

const FX_GROUP: StringName = &"arena_fx"

@export var config: ArenaConfig


func _ready() -> void:
	if config == null:
		push_error("ArenaView %s: no ArenaConfig assigned" % name)


## [param enabled] false hides ambient particles for low-end devices.
func set_ambient_effects(enabled: bool) -> void:
	for n: Node in get_tree().get_nodes_in_group(FX_GROUP):
		if not is_ancestor_of(n):
			continue
		if n is GPUParticles3D:
			(n as GPUParticles3D).emitting = enabled
			(n as GPUParticles3D).visible = enabled
		elif n is Node3D:
			(n as Node3D).visible = enabled
