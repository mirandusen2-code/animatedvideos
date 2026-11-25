"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_chicken_gun", 2, [["CHICKEN"], ["VS PLANE"]], {0: post.HOT}, 1340),
    ("thumb_why", int((T.T_OLD_HIT + 0.25) * T.FPS), [["WHY THEY"], ["SHOOT CHICKENS"]], {1: post.HOT}, 1360),
    ("thumb_frozen", int((T.T_CANT[0] + 0.3) * T.FPS), [["WHY NOT"], ["FROZEN?"]], {1: post.HOT}, 1360),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    if name == "thumb_frozen":
        post.overlays(img, f / T.FPS)            # keep the red X
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
