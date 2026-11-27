"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_grape_plasma", 0, [["2 GRAPES"], ["= PLASMA"]], {1: post.HOT}, 1340),
    ("thumb_why_grapes", 720, [["WHY DO"], ["GRAPES MAKE"], ["PLASMA?"]], {2: post.HOT}, 560),
    ("thumb_microwave", 840, [["MICROWAVE"], ["PLASMA"]], {1: post.HOT}, 1380),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
