extends SceneTree
## Minimal headless test runner (no third-party plugins).
##
## Run:  godot --headless --path . --script res://tests/run_tests.gd
## Exit code 0 = all tests passed, 1 = at least one failure.
##
## Each test file in TEST_DIRS extends RefCounted and exposes methods named
## test_*() that return an Array[String] of failure messages (empty = pass).
##
## Tests run on the first idle frame (not in _initialize) so the scene tree is
## live and integration tests can add scenes whose _ready() actually runs.
## GDScript cannot catch runtime script errors, so CI also fails the run if
## "SCRIPT ERROR" appears in the output — always check the log, not just PASS.

const TEST_DIRS: Array[String] = ["res://tests/unit", "res://tests/integration"]
## Tests never touch the player's real save.
const TEST_SAVE: String = "user://test_save.json"


var _done: bool = false


func _process(_delta: float) -> bool:
	if not _done:
		_done = true
		_run_all()
	return false


func _run_all() -> void:
	var passed: int = 0
	var failed: int = 0
	for dir_path: String in TEST_DIRS:
		for file_name: String in _list_test_files(dir_path):
			var script: GDScript = load(dir_path.path_join(file_name)) as GDScript
			if script == null:
				print("FAIL  %s (could not load)" % file_name)
				failed += 1
				continue
			var suite: Object = script.new()
			for method: Dictionary in suite.get_method_list():
				var name: String = method.name
				if not name.begins_with("test_"):
					continue
				_fresh_state()
				var failures: Array = suite.call(name)
				if failures.is_empty():
					print("PASS  %s::%s" % [file_name, name])
					passed += 1
				else:
					print("FAIL  %s::%s" % [file_name, name])
					for f: Variant in failures:
						print("        - %s" % f)
					failed += 1
	_fresh_state()
	print("\n%d passed, %d failed" % [passed, failed])
	quit(0 if failed == 0 else 1)


func _list_test_files(dir_path: String) -> PackedStringArray:
	var result: PackedStringArray = []
	var dir: DirAccess = DirAccess.open(dir_path)
	if dir == null:
		return result
	for f: String in dir.get_files():
		if f.begins_with("test_") and f.ends_with(".gd"):
			result.append(f)
	result.sort()
	return result


## Every test starts from a clean save file and no pending mode run.
func _fresh_state() -> void:
	SaveManager.path = TEST_SAVE
	for suffix: String in ["", ".tmp"]:
		if FileAccess.file_exists(TEST_SAVE + suffix):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_SAVE + suffix))
	var corrupt: String = TEST_SAVE.get_basename() + ".corrupt.json"
	if FileAccess.file_exists(corrupt):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(corrupt))
	SaveManager.unload()
	ModeFlow.setup = null
	ModeFlow.mode = MatchSetup.Mode.VERSUS
	ModeFlow.p1_id = &"kairo"
	SessionSettings.ai_difficulty = 1
