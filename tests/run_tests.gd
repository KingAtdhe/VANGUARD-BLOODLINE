extends SceneTree
## Minimal headless test runner (no third-party plugins).
##
## Run:  godot --headless --path . --script res://tests/run_tests.gd
## Exit code 0 = all tests passed, 1 = at least one failure.
##
## Each test file in TEST_DIRS extends RefCounted and exposes methods named
## test_*() that return an Array[String] of failure messages (empty = pass).

const TEST_DIRS: Array[String] = ["res://tests/unit", "res://tests/integration"]


func _initialize() -> void:
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
				var failures: Array = suite.call(name)
				if failures.is_empty():
					print("PASS  %s::%s" % [file_name, name])
					passed += 1
				else:
					print("FAIL  %s::%s" % [file_name, name])
					for f: Variant in failures:
						print("        - %s" % f)
					failed += 1
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
