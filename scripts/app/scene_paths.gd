class_name ScenePaths
extends RefCounted
## Central list of routable scenes. Add new screens here, not as string
## literals scattered through scripts.

const BOOT: String = "res://scenes/app/boot.tscn"
const MAIN_MENU: String = "res://scenes/menus/main_menu.tscn"
const COMBAT_GREYBOX: String = "res://scenes/combat/combat_greybox.tscn"
const TRAINING_GREYBOX: String = "res://scenes/combat/training_greybox.tscn"

const ALL: Array[String] = [BOOT, MAIN_MENU, COMBAT_GREYBOX, TRAINING_GREYBOX]
