#!/usr/bin/env bash
# Render every frame that does not exist yet in <out_dir>, 40 at a time, each batch in a fresh Blender
# process. Safe to stop and restart at any time. Usage: ./render_missing.sh <out_dir> [scene.py args...]
OUT=$1; shift
cd "$(dirname "$0")"
N=$(python3 -c "import timeline as T; print(T.NFRAMES)")
while true; do
  MISSING=$(python3 -c "
import os
m=[str(f) for f in range($N) if not os.path.exists(os.path.join('$OUT', f'f_{f:04d}.png'))]
print(','.join(m[:40]))")
  [ -z "$MISSING" ] && break
  SPACE_TEX=${SPACE_TEX:-} python3 scene.py "$OUT" --frames "$MISSING" "$@" > /dev/null 2>&1
  echo "rendered up to $(ls "$OUT"/f_*.png | wc -l)/$N"
done
echo "FULL DONE"
