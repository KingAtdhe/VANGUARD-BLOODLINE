class_name PauseMenu
extends CanvasLayer
## Pause menu for offline modes (spec §2.3). Runs while the tree is paused.
## The pause action (Esc / P / Start) or Android back resumes.

signal resume_requested
signal restart_requested
signal quit_requested

@onready var _resume: Button = %ResumeButton


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false
	_resume.pressed.connect(func() -> void: resume_requested.emit())
	%RestartButton.pressed.connect(func() -> void: restart_requested.emit())
	%QuitButton.pressed.connect(func() -> void: quit_requested.emit())


func open() -> void:
	visible = true
	_resume.grab_focus()


func close() -> void:
	visible = false


func _unhandled_input(event: InputEvent) -> void:
	if visible and event.is_action_pressed(InputActions.PAUSE):
		get_viewport().set_input_as_handled()
		resume_requested.emit()
