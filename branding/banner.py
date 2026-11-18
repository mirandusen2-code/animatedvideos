"""YouTube banner for 'MindBlown 3D' (2560x1440).

Logo + text sit inside YouTube's safe area (1546x423, centred), which is visible on every device;
the rest is decoration that TVs/desktops may show.
Usage: python3 banner.py [out.png] [--guides]
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from profile_picture import icon, star

W, H = 2560, 1440
SAFE = (W - 1546) // 2, (H - 423) // 2, (W + 1546) // 2, (H + 423) // 2
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viral-hooks", "fonts")
YELLOW = (255, 214, 64)


def background():
    y, x = np.mgrid[0:H, 0:W]
    r = np.sqrt(((x - W / 2) / (W * 0.55)) ** 2 + ((y - H / 2) / (H * 0.75)) ** 2)
    inner = np.array([130, 35, 235], float)
    outer = np.array([18, 6, 52], float)
    t = np.clip(r, 0, 1)[..., None]
    img = Image.fromarray((inner * (1 - t) + outer * t).astype(np.uint8), "RGB").convert("RGBA")
    # faint bursts and sparkles across the full width
    deco = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(deco)
    rnd = random.Random(11)
    for _ in range(9):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        if SAFE[0] - 150 < x < SAFE[2] + 150 and SAFE[1] - 150 < y < SAFE[3] + 150:
            continue
        r = rnd.uniform(90, 220)
        d.polygon(star(x, y, r, r * 0.55, 10, rot=rnd.uniform(0, 1), jitter=0.12, seed=rnd.randint(0, 99)),
                  fill=(255, 150, 60, 40))
    img.alpha_composite(deco.filter(ImageFilter.GaussianBlur(3)))
    d = ImageDraw.Draw(img)
    for _ in range(70):
        x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(6, 26)
        if SAFE[0] - 40 < x < SAFE[2] + 40 and SAFE[1] - 40 < y < SAFE[3] + 40:
            continue                                   # keep the logo/text area clean
        a = int(rnd.uniform(90, 230))
        d.polygon(star(x, y, r, r * 0.28, 4, rot=-math.pi / 2), fill=(255, 255, 255, a))
    return img


def fit_font(path, text, max_w, start):
    size = start
    while size > 20:
        f = ImageFont.truetype(path, size)
        if f.getlength(text) <= max_w:
            return f
        size -= 4
    return ImageFont.truetype(path, size)


def main():
    out = next((a for a in sys.argv[1:] if not a.startswith("--")), "mindblown3d_banner.png")
    img = background()
    sx0, sy0, sx1, sy1 = SAFE
    cy = (sy0 + sy1) / 2

    # logo (exploding brain) on the left of the safe area
    ic = icon(background=False).resize((420, 420), Image.LANCZOS)
    img.alpha_composite(ic, (sx0 + 10, sy0 + 2))

    # title + tagline to the right of it
    d = ImageDraw.Draw(img)
    tx0 = sx0 + 450
    max_w = sx1 - tx0 - 10
    black = os.path.join(FONTS, "Montserrat-Black.otf")
    semi = os.path.join(FONTS, "Montserrat-SemiBold.otf")
    f_title = fit_font(black, "MINDBLOWN 3D", max_w, 190)
    f_tag = fit_font(semi, "Mind-blowing facts, animated in 3D", max_w, 64)
    ty = cy - 40
    sw = max(6, f_title.size // 14)
    w_mind = f_title.getlength("MINDBLOWN ")
    for dx, dy, col, part, x in [(8, 10, (0, 0, 0, 150), "MINDBLOWN 3D", tx0),
                                 (0, 0, (255, 255, 255, 255), "MINDBLOWN", tx0),
                                 (0, 0, YELLOW + (255,), "3D", tx0 + w_mind)]:
        d.text((x + dx, ty + dy), part, font=f_title, fill=col, anchor="lm",
               stroke_width=sw, stroke_fill=(30, 5, 50, 255) if dx == 0 else col)
    d.text((tx0 + 6, ty + f_title.size * 0.78), "Mind-blowing facts, animated in 3D", font=f_tag,
           fill=(235, 220, 255), anchor="lm", stroke_width=4, stroke_fill=(30, 5, 50))

    if "--guides" in sys.argv:
        d.rectangle(SAFE, outline=(0, 255, 0), width=4)
    img.convert("RGB").save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
