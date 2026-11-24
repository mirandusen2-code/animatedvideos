"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_explodes", 4, [["IT", "EXPLODES"], ["INSIDE", "OUT"]], {1: post.HOT}, 1320),
    ("thumb_40x", int((T.T_40 + 0.2) * T.FPS), [["40×"], ["BIGGER"]], {0: post.AMBER}, 1360),
    ("thumb_backflip", int((T.T_FLIPS + 0.1) * T.FPS), [["POPCORN"], ["BACKFLIP?!"]], {1: post.AMBER}, 1380),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
