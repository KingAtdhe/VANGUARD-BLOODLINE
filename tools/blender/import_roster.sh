#!/usr/bin/env bash
# Rebuilds the six playable fighters from the owner-supplied sources (D-054)
# with the per-fighter settings that were checked by eye (pose renders from
# four angles). Run from the repo root with Blender's Python (bpy) on PATH as
# BLENDER_PY, after exporting move timing:
#   godot --headless --path . --script res://tools/blender/export_move_timing.gd -- /tmp/kairo_moves.json
#   BLENDER_PY=python tools/blender/import_roster.sh
#
# Why the flags:
# - kairo: his sash hangs right beside the hand at rest; the arm rule (nearer the arm
#   than the torso and legs) keeps it off the arm, the gauntlets on.
# - kairo, nox: supplied joints are good, supplied weights are not (Kairo's sash
#   was skinned to his arm, Nox's hood and cloak to his arms) -> --force-reskin.
# - ryuen, vexa: supplied rigs are broken, and the joints measured on the body
#   land inside the wide sleeves / short of the long hands -> arm joints read off
#   a measuring-grid render of the rest pose (--joint; depth comes from the mesh).
# - drakon: supplied rig and weights kept. seraphina: measured joints are fine.
set -euo pipefail
PY="${BLENDER_PY:-python}"
SRC=assets/characters/_source
MOVES="${MOVES:-/tmp/kairo_moves.json}"
MOCAP="${MOCAP:-/tmp/cmu_mocap}"          # tools/mocap/fetch_clips.sh
OUT="${OUT:-assets/characters}"
run() { "$PY" tools/blender/import_rigged.py --moves "$MOVES" --out "$OUT" --mocap-dir "$MOCAP" "$@"; }
run --src $SRC/kairo_heroic_warrior.glb --fighter kairo --force-reskin
run --src $SRC/drakon_armored_warrior.glb --fighter drakon
run --src $SRC/nox_purple_hooded_warrior.glb --fighter nox --force-reskin --hand-reach 0.06 --sleeve-reach 0.12
run --src $SRC/seraphina_superhero_female.glb --fighter seraphina
run --src $SRC/vexa_female_warrior.glb --fighter vexa \
    --joint shoulder=0.18,0,1.43 --joint elbow=0.28,0,1.12 --joint wrist=0.31,0,0.9 --joint hand_tip=0.32,0,0.72
run --src $SRC/ryuen_elder_monk.glb --fighter ryuen \
    --joint shoulder=0.2,0,1.36 --joint elbow=0.3,0,1.02 --joint wrist=0.33,0,0.8 --joint hand_tip=0.33,0,0.64
