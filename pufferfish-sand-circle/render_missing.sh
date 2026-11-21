#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${FRAME_DIR:?Set FRAME_DIR to a directory outside the repository}"
mkdir -p "$FRAME_DIR"
start=${1:-0}
total=$(python -c 'from timeline import NFRAMES;print(NFRAMES)')
end=${2:-$total}
python - "$start" "$end" <<'PY'
from pathlib import Path
from PIL import Image
import os,sys
d=Path(os.environ['FRAME_DIR'])
for i in range(int(sys.argv[1]),int(sys.argv[2])):
    p=d/f'{i:05}.png'
    if not p.exists():continue
    try:
        with Image.open(p) as im:
            im.load()
            if im.size!=(1080,1920):raise ValueError(im.size)
    except (OSError,ValueError):
        p.unlink()
PY
for ((a=start; a<end && a<total; a+=40)); do
    last=$((a+40))
    if ((last>end)); then last=$end; fi
    python scene.py "$a" "$last" > "$FRAME_DIR/render.log" 2>&1 || { tail -55 "$FRAME_DIR/render.log"; exit 1; }
    echo "Rendered frames $a through $((last-1))"
done
