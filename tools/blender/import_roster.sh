#!/usr/bin/env bash
# Rebuilds the six playable fighters from the owner's Tripo models (D-058):
# FBX + textures in assets/characters/_source/<id>/, Mixamo skeleton and
# Tripo's own skin weights (kept), real motion capture for the animations.
#   godot --headless --path . --script res://tools/blender/export_move_timing.gd -- /tmp/kairo_moves.json
#   tools/mocap/fetch_clips.sh /tmp/cmu_mocap
#   BLENDER_PY=python tools/blender/import_roster.sh
set -euo pipefail
PY="${BLENDER_PY:-python}"
SRC=assets/characters/_source
MOVES="${MOVES:-/tmp/kairo_moves.json}"
MOCAP="${MOCAP:-/tmp/cmu_mocap}"
OUT="${OUT:-assets/characters}"
for f in kairo drakon seraphina nox vexa ryuen; do
  "$PY" tools/blender/import_rigged.py --src "$SRC/$f/$f.fbx" --fighter "$f" --moves "$MOVES" --out "$OUT" --mocap-dir "$MOCAP"
done
