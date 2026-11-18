class_name ScenePaths
extends RefCounted
## Central list of routable scenes. Add new screens here, not as string
## literals scattered through scripts.

const BOOT: String = "res://scenes/app/boot.tscn"
const MAIN_MENU: String = "res://scenes/menus/main_menu.tscn"
const FIGHTER_SELECT: String = "res://scenes/menus/fighter_select.tscn"
const ARENA_SELECT: String = "res://scenes/menus/arena_select.tscn"
const STORY: String = "res://scenes/menus/story_screen.tscn"
const ARCADE: String = "res://scenes/menus/arcade_screen.tscn"
const SURVIVAL: String = "res://scenes/menus/survival_screen.tscn"
const SETTINGS: String = "res://scenes/menus/settings_screen.tscn"
const PROFILE: String = "res://scenes/menus/profile_screen.tscn"
const COMBAT_GREYBOX: String = "res://scenes/combat/combat_greybox.tscn"
const TRAINING_GREYBOX: String = "res://scenes/combat/training_greybox.tscn"

const ALL: Array[String] = [BOOT, MAIN_MENU, FIGHTER_SELECT, ARENA_SELECT, STORY, ARCADE, SURVIVAL,
	SETTINGS, PROFILE, COMBAT_GREYBOX, TRAINING_GREYBOX]
## Menu screens (all built on MenuScreen; each must offer a way back).
const MENUS: Array[String] = [MAIN_MENU, FIGHTER_SELECT, ARENA_SELECT, STORY, ARCADE, SURVIVAL,
	SETTINGS, PROFILE]
