"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_vanish", 24, [["EVEREST", "WOULD"], ["VANISH"]], {2: post.AMBER}, 1300),
    ("thumb_7miles", int((T.T_PEAK + 0.3) * T.FPS), [["7", "MILES"], ["DEEP"]], {0: post.AMBER, 1: post.AMBER}, 400),
    ("thumb_8tons", int((T.T_8 + 1.0) * T.FPS), [["8", "TONS"], ["PER", "INCH"]], {0: post.AMBER, 1: post.AMBER}, 560),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
