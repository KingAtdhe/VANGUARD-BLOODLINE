#!/usr/bin/env bash
# Before / now video for the owner: the two side by side at real speed, then
# the same again at half speed.
#
#   bash before_after_video.sh <before.mp4> <now.mp4> <out.mp4>
#
# Make both inputs with tools/review_video.py using the SAME --clips list:
#   python3 tools/review_video.py kairo /root/work/before.mp4 --clips KICK_LOW_01     (before rebuilding)
#   ... rebuild ...
#   python3 tools/review_video.py kairo /root/work/now.mp4 --clips KICK_LOW_01
# If the move's length changed (frame data), the shorter side holds its last
# frame until the other ends.
#
# The owner judges motion from video (CLAUDE.md, D-091). Tell her it was
# checked frame by frame, not watched. Needs ffmpeg.
set -euo pipefail
B="${1:?before.mp4}"; N="${2:?now.mp4}"; OUT="${3:?out.mp4}"
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
[ -f "$FONT" ] || FONT="$(fc-list : file | grep -i -m1 'bold' | cut -d: -f1)"
lab() { echo "drawtext=fontfile=$FONT:text='$1':x=(w-text_w)/2:y=h-42:fontsize=26:fontcolor=white:borderw=2:bordercolor=black"; }
dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
LONG=$(python3 -c "print(max($(dur "$B"), $(dur "$N")))")
ffmpeg -v error -y -i "$B" -i "$N" -filter_complex "
  [0:v]fps=60,scale=-2:560,tpad=stop_mode=clone:stop_duration=$LONG,$(lab BEFORE)[b];
  [1:v]fps=60,scale=-2:560,tpad=stop_mode=clone:stop_duration=$LONG,$(lab NOW)[n];
  [b][n]hstack=inputs=2,trim=duration=$LONG,setpts=PTS-STARTPTS,split[full][s];
  [s]setpts=2*PTS,drawtext=fontfile=$FONT:text='half speed':x=16:y=h-42:fontsize=22:fontcolor=yellow:borderw=2:bordercolor=black[slow];
  [full][slow]concat=n=2:v=1[v]" -map "[v]" -r 60 -pix_fmt yuv420p -c:v libx264 -crf 21 "$OUT"
echo "wrote $OUT ($(dur "$OUT") s: real speed, then half speed)"
