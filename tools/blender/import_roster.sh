#!/usr/bin/env bash
# Rebuilds the six playable fighters from the owner's Tripo models (D-058):
# FBX + textures in assets/characters/_source/<id>/, Mixamo skeleton and
# Tripo's own skin weights (kept), real motion capture for the animations.
# Each fighter is animated from its own move data:
#   for f in kairo drakon seraphina nox vexa ryuen; do
#     godot --headless --path . --script res://tools/blender/export_move_timing.gd -- /tmp/moves_$f.json $f; done
#   tools/mocap/fetch_clips.sh /tmp/cmu_mocap
#   BLENDER_PY=python tools/blender/import_roster.sh
set -euo pipefail
PY="${BLENDER_PY:-python}"
SRC=assets/characters/_source
MOVES_DIR="${MOVES_DIR:-/tmp}"
MOCAP="${MOCAP:-/tmp/cmu_mocap}"
OUT="${OUT:-assets/characters}"
run() { "$PY" tools/blender/import_rigged.py --src "$SRC/$1/$1.fbx" --fighter "$1" --moves "$MOVES_DIR/moves_$1.json" --out "$OUT" --mocap-dir "$MOCAP" "${@:2}"; }
run kairo
for f in drakon seraphina nox vexa ryuen; do run "$f"; done
