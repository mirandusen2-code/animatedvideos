"""Three thumbnail candidates (1080x1920) from the most striking frames, with a short title in the safe zone.
Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
f_glass = int((T.T_GLASS + 0.9) * T.FPS)
f_flash = int((T.T_POP + 0.12) * T.FPS)
f_snail = int((T.T_SNAIL + 0.25) * T.FPS)
for name, f, lines, colors, y in [
    ("thumb_glass", f_glass, [["IT", "PUNCHES"], ["THROUGH", "GLASS"]], {1: post.AMBER, 3: post.ICE}, 1250),
    ("thumb_flash", f_flash, [["7,000°F"], ["PUNCH"]], {0: post.AMBER}, 1250),
    ("thumb_snail", f_snail, [["50", "MPH"], ["PUNCH"]], {0: post.AMBER, 1: post.AMBER}, 1250),
]:
    t = f / T.FPS
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), t)
    post.text_block(img, lines, post.CX, y, 118, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
