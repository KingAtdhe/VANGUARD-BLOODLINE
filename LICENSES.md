# Licenses and Asset Ownership

All shipped assets must be original or properly licensed (spec §1.3, §16).
Record every third-party asset, font, sound, plugin or tool output here
**before** it is committed.

| Asset / dependency | Source | License | Used in | Added |
|---|---|---|---|---|
| Godot Engine 4.7.2 | godotengine.org | MIT | Engine | 2026-11-17 |
| Default Godot UI font | Bundled with Godot | (engine default font license — verify before release) | All UI text | 2026-11-17 |
| `icon.svg` placeholder | Original, made for this project | Project-owned | Project icon | 2026-11-17 |
| `assets/characters/*/*.glb` (8 fighters) | Generated from scratch by `tools/blender/character_builder.py` (no base mesh/external assets) | Project-owned | Fighter models | 2026-11-18 |
| `assets/arenas/*/*_arena.glb` | Generated from scratch by `tools/blender/arena_builder.py` | Project-owned | Arena geometry | 2026-11-18 |
| Story text, signage text, fighter names | Original, written for this project | Project-owned | Story/arenas | 2026-11-18 |
| `audio/sfx/placeholder_*.wav` | Synthesized by `tools/audio/generate_placeholder_sfx.py` (no samples) | Project-owned | Placeholder SFX | 2026-11-18 |
| Blender 5.3 (tool only, not shipped) | blender.org | GPL (tool output is not GPL) | Build pipeline | 2026-11-18 |

Project code license: **not yet chosen** (repository is public — decide before
outside contributions; until then all rights reserved by the owner).
