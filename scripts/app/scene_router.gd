extends Node
## Autoload "SceneRouter": the single place that changes the active screen.
##
## Guarantees only one transition runs at a time, so two combat scenes can
## never be active together (spec §9.3).

signal scene_changed(path: String)
signal scene_change_failed(path: String, error: Error)

var _transitioning: bool = false
var _current_path: String = ""


func current_path() -> String:
	return _current_path


func is_transitioning() -> bool:
	return _transitioning


## Requests a deferred switch to [param path]. Returns false if rejected.
func goto(path: String) -> bool:
	if _transitioning:
		push_warning("SceneRouter: transition already in progress, ignoring %s" % path)
		return false
	if not ResourceLoader.exists(path):
		push_error("SceneRouter: scene not found: %s" % path)
		scene_change_failed.emit(path, ERR_FILE_NOT_FOUND)
		return false
	_transitioning = true
	_change_scene.call_deferred(path)
	return true


func _change_scene(path: String) -> void:
	var err: Error = get_tree().change_scene_to_file(path)
	_transitioning = false
	if err != OK:
		push_error("SceneRouter: failed to change to %s (error %d)" % [path, err])
		scene_change_failed.emit(path, err)
		return
	_current_path = path
	print("[SceneRouter] -> %s" % path)
	scene_changed.emit(path)
