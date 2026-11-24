"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_exploded", 25, [["IT", "JUST"], ["EXPLODED"]], {2: post.AMBER}, 1180),
    ("thumb_hammer", int((T.T_HIT + 0.15) * T.FPS), [["HAMMER"], ["PROOF?"]], {1: post.AMBER}, 1420),
    ("thumb_snip", 556, [["DON'T", "SNIP"], ["THE", "TAIL"]], {3: post.AMBER}, 1300),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
