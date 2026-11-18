extends Node
var t := 0
func _process(_d):
	t += 1
	var s := get_tree().current_scene
	if t == 120: print("[cap] scene=", s.name); s.get_node("%FightButton").pressed.emit()
	if t == 200: print("[cap] scene=", s.name); s.get_node("%DebugOverlay").get_node("%BackButton").pressed.emit()
	if t == 260: print("[cap] scene=", s.name)
