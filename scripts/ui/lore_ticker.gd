class_name LoreTicker
extends HBoxContainer
## Broadcast-style ticker for the main menu: a crimson LIVE tag and a line
## of in-world news scrolling past (original text, presentation only).

const LINES: PackedStringArray = [
	"ORIGIN READINGS +3.2% OVER THE NEON DISTRICT",
	"THE PIT SOLD OUT FOR THE ASCENDANT QUALIFIERS",
	"SANCTUARY SKIES CLEAR AT DAWN — CHAINS HOLDING",
	"CONDUIT REPAIR CREWS PULLED BACK FROM THE SEVERED LINE",
	"THE ORDER DENIES ANY LINK TO THE SENTINEL UNITS",
	"SIX BLOODLINES. ONE CROWN.",
]
@export var speed: float = 90.0

var _clip: Control
var _label: Label


func _ready() -> void:
	add_theme_constant_override("separation", 0)
	custom_minimum_size = Vector2(0, 48)
	var tag := PanelContainer.new()
	var sb := UiTheme.box(UiTheme.ACCENT, Color(0, 0, 0, 0), 0, 0, 10, UiTheme.SKEW)
	sb.content_margin_left = 22
	sb.content_margin_right = 26
	tag.add_theme_stylebox_override("panel", sb)
	var tl := Label.new()
	tl.text = "LIVE"
	tl.add_theme_font_override("font", UiTheme.display_font())
	tl.add_theme_font_size_override("font_size", 34)
	tag.add_child(tl)
	add_child(tag)
	_clip = Control.new()
	_clip.clip_contents = true
	_clip.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_clip.custom_minimum_size = Vector2(0, 48)
	var bg := ColorRect.new()
	bg.color = Color(0, 0, 0, 0.55)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	_clip.add_child(bg)
	add_child(_clip)
	_label = Label.new()
	_label.text = "   ◆   ".join(LINES) + "   ◆   "
	_label.add_theme_font_override("font", UiTheme.bold_font())
	_label.add_theme_font_size_override("font_size", 24)
	_label.add_theme_color_override("font_color", UiTheme.TEXT)
	_label.position = Vector2(20, 8)
	_clip.add_child(_label)


func _process(delta: float) -> void:
	if _label == null:
		return
	_label.position.x -= speed * delta
	var w: float = _label.get_minimum_size().x
	if _label.position.x < -w:
		_label.position.x = _clip.size.x
