"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_mentos_geyser", 0, [["MENTOS"], ["+ DIET COKE"]], {1: post.AMBER}, 1340),
    ("thumb_why_craters", 520, [["WHY DOES"], ["IT EXPLODE?"]], {1: post.HOT}, 560),
    ("thumb_3_bottles", 215, [["3 BOTTLES"], ["OF HIDDEN GAS"]], {0: post.ICE}, 1360),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
