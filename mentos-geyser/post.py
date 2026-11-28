"""Post-production for the Mentos + Diet Coke Short: grade + bloom, captions & counters in the Shorts
safe zone, original music + sound effects + processed voice, loudness -14 LUFS, H.264 1080x1920.

Usage: python3 post.py <frames_dir> <out.mp4> [--preview f1,f2,...]   (preview writes PNGs only)
Also writes <out>.srt (subtitles).
"""
import json
import math
import os
import re
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timeline as T  # noqa: E402
import geo as G  # noqa: E402
from script import LINES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
FONT_DIR = os.path.join(HERE, "..", "viral-hooks", "fonts")
AMBER = (255, 181, 71)
ICE = (127, 216, 255)
WHITE = (255, 255, 255)
INK = (8, 12, 24)
# Shorts safe zone: top 250 px (search bar), bottom 420 px (title/channel), right ~200 px (buttons)
# Measured on a real phone screenshot of a published Short (YouTube crops ~46 px per side on tall phones):
# top ~260 px = status/search icons, right x>880 (y 1050-1760) = like/comment/share, bottom from y~1580 =
# channel name + title. Everything essential stays inside this column:
SAFE = (92, 300, 860, 1540)
CX = (SAFE[0] + SAFE[2]) / 2                         # 476: centre of the safe column
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = T.L
_f = {}


def font(size, kind="Black"):
    k = (int(size), kind)
    if k not in _f:
        _f[k] = ImageFont.truetype(os.path.join(FONT_DIR, f"Montserrat-{kind}.otf"), k[0])
    return _f[k]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def back_out(x):
    x = clamp(x)
    c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def window(t, a, b, fade=0.18):
    return clamp((t - a) / fade) * clamp((b - t) / fade)


# ---------------------------------------------------------------- text helpers
def text_block(img, lines, cx, cy, size, alpha=1.0, scale=1.0, colors=None, kind="Black", maxw=None):
    """Centred multi-line text with outline + soft shadow. lines: list of lists of words.
    colors: dict word-index -> colour. Shrinks to fit the safe column."""
    if alpha <= 0.01:
        return
    maxw = maxw or (SAFE[2] - SAFE[0])
    size = int(size * scale)
    while True:
        f = font(size, kind)
        widths = [f.getlength(" ".join(l)) for l in lines]
        if max(widths) <= maxw or size < 30:
            break
        size -= 4
    lh = size * 1.1
    sw = max(4, size // 10)
    pad = sw * 3
    layer = Image.new("RGBA", (int(maxw + 2 * pad), int(lh * len(lines) + 2 * pad)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    k = 0
    for i, (words, wdt) in enumerate(zip(lines, widths)):
        x = layer.width / 2 - wdt / 2
        y = pad + i * lh
        for w in words:
            c = (colors or {}).get(k, WHITE)
            d.text((x + size * 0.05, y + size * 0.07), w, font=f, fill=(0, 0, 0, 140), stroke_width=sw,
                   stroke_fill=(0, 0, 0, 140))
            d.text((x, y), w, font=f, fill=c, stroke_width=sw, stroke_fill=INK)
            x += f.getlength(w + " ")
            k += 1
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    x0, y0 = int(cx - layer.width / 2), int(cy - layer.height / 2)
    assert x0 + pad >= SAFE[0] - 2 and x0 + layer.width - pad <= SAFE[2] + 2, "text outside safe zone"
    img.alpha_composite(layer, (x0, y0))


def number(img, text, cx, cy, size, color, alpha=1.0, suffix=""):
    """Counter with fixed-width digits (no horizontal jitter while it counts) + optional unit."""
    if alpha <= 0.01:
        return
    f = font(size)
    cell = max(f.getlength(d) for d in "0123456789")
    widths = [cell if ch.isdigit() else f.getlength(ch) for ch in text]
    gap = f.getlength(" ")
    total = sum(widths) + (gap + f.getlength(suffix) if suffix else 0)
    sw = max(4, size // 10)
    layer = Image.new("RGBA", (int(total + 6 * sw), int(size * 1.6)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y = 3 * sw, layer.height / 2
    for ch, w_ in zip(text, widths):
        for dx, dy, fill, stroke in ((size * 0.05, size * 0.07, (0, 0, 0, 140), (0, 0, 0, 140)), (0, 0, color, INK)):
            d.text((x + w_ / 2 + dx, y + dy), ch, font=f, fill=fill, anchor="mm", stroke_width=sw, stroke_fill=stroke)
        x += w_
    if suffix:
        x += gap
        for dx, dy, fill, stroke in ((size * 0.05, size * 0.07, (0, 0, 0, 140), (0, 0, 0, 140)), (0, 0, WHITE, INK)):
            d.text((x + dx, y + dy), suffix, font=f, fill=fill, anchor="lm", stroke_width=sw, stroke_fill=stroke)
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def pill(img, text, cx, cy, size=40, fg=WHITE, bg=(10, 16, 32, 200), alpha=1.0, accent=None):
    """Label chip (>= 56 px tall, <= 4 words)."""
    assert size >= 44, "label text must be >= 44 px"
    if alpha <= 0.01:
        return
    f = font(size, "ExtraBold")
    tw = f.getlength(text)
    h = max(56, int(size * 1.6))
    wdt = tw + size * 1.4
    layer = Image.new("RGBA", (int(wdt) + 4, h + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([2, 2, wdt, h], radius=h / 2, fill=bg, outline=(*(accent or ICE), 255), width=3)
    d.text((wdt / 2 + 1, h / 2 + 2), text, font=f, fill=fg, anchor="mm")
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    x0 = int(min(max(cx - layer.width / 2, SAFE[0]), SAFE[2] - layer.width))
    y0 = int(min(max(cy - layer.height / 2, SAFE[1]), SAFE[3] - layer.height))
    img.alpha_composite(layer, (x0, y0))


def project(p, t):
    """World point -> output pixel, using the same camera as Blender (portrait, sensor fit on height)."""
    loc, tgt, lens = T.camera(t)
    loc, tgt, p = np.array(loc), np.array(tgt), np.array(p)
    f = tgt - loc
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    d = p - loc
    z = d @ f
    vh = 18.0 / lens
    return W / 2 + (d @ r / z) / (vh * 9 / 16) * W / 2, H / 2 - (d @ u / z) / vh * H / 2


# ---------------------------------------------------------------- captions (1-3 words, active word amber)
def line_of(t):
    """Index of the narration line a word belongs to."""
    starts = sorted(v[0] for v in L.values())
    return sum(1 for s0 in starts if s0 <= t + 0.06)


def caption_groups():
    """Caption chunks as written in the script ('|' marks), never across narration lines."""
    words = TIMING["words"]
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        last_of_line = i + 1 == len(words) or line_of(words[i + 1][0]) != line_of(w[0])
        if (len(w) > 4 and w[4]) or last_of_line:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    out = []
    for i, g in enumerate(groups):
        t0, t1 = g[0][0], g[-1][1]
        if i == 0:
            t0 = 0.0                               # on screen from frame 0: no empty flash at the loop
        if i + 1 < len(groups):
            t1 = max(t1, min(groups[i + 1][0][0], t1 + 0.5))
        else:
            t1 = T.DUR + 1                         # last chunk stays until the loop restarts
        out.append((t0, t1, g))
    return out


GROUPS = caption_groups()


def draw_captions(img, t):
    for t0, t1, g in GROUPS:
        if t0 <= t < t1:
            words = [w[2].upper() for w in g]
            colors = {}
            for i, w in enumerate(g):
                if w[0] <= t < w[1] + 0.05:
                    colors[i] = AMBER
                elif w[3]:
                    colors[i] = ICE
            s = 0.88 + 0.12 * back_out((t - t0) / 0.14)
            # one line if it fits at full size, else two (decided once per group, so the pop-in never re-wraps)
            f = font(72)
            lines = [words] if f.getlength(" ".join(words)) <= 700 else [words[:2], words[2:]]
            text_block(img, lines, CX, SAFE[3] - 95, 72, scale=s, colors=colors, maxw=700)
            return


# ---------------------------------------------------------------- counters / labels
def fmt(n):
    return f"{int(n):,}"


def big(img, value, unit, alpha, pop=1.0, color=AMBER, size=132):
    assert size >= 96, "numbers must be >= 96 px"
    text_block(img, [[value]], CX, 420, size, alpha=alpha, scale=pop, colors={0: color})
    pill(img, unit, CX, 530, 46, alpha=alpha, accent=color)


def label_at(img, text, p, t, alpha, accent=ICE, dy=-120):
    x, y = project(p, t)
    x = min(max(x, SAFE[0] + 140), SAFE[2] - 140)
    pill(img, text, x, y + dy, 46, alpha=alpha, accent=accent)


HOT = (255, 90, 70)


def reticle(img, p, t, r_world, alpha, color=AMBER):
    """Corner brackets around a world point (target lock)."""
    if alpha <= 0.01:
        return
    x, y = project(p, t)
    loc, tgt, lens = T.camera(t)
    d = np.linalg.norm(np.array(p) - np.array(loc))
    r = max(46.0, r_world / d / (18.0 / lens) * H / 2 * 1.25)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    k = r * 0.4
    a = int(255 * alpha)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = x + sx * r, y + sy * r
            for col_, w_ in (((0, 0, 0, a // 2), 9), ((*color, a), 5)):
                dr.line([(cx, cy - sy * k), (cx, cy), (cx - sx * k, cy)], fill=col_, width=w_)
    img.alpha_composite(layer)


def bars(img, rows, y0, alpha):
    """Horizontal comparison bars: rows = [(label, value_text, fraction, color), ...]."""
    if alpha <= 0.01:
        return
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(46, "ExtraBold")
    x0, x1 = SAFE[0] + 20, SAFE[2] - 20
    for k, (lab, val, frac, colr) in enumerate(rows):
        y = y0 + k * 118
        d.text((x0, y), lab, font=f, fill=(255, 255, 255, 255), anchor="ls", stroke_width=5, stroke_fill=INK)
        d.text((x1, y), val, font=f, fill=(*colr, 255), anchor="rs", stroke_width=5, stroke_fill=INK)
        d.rounded_rectangle([x0, y + 14, x1, y + 50], radius=18, fill=(10, 16, 32, 190))
        if frac > 0.005:
            d.rounded_rectangle([x0, y + 14, x0 + max(36, (x1 - x0) * frac), y + 50], radius=18, fill=(*colr, 255))
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(layer)


def pop(t, t0, k=0.2):
    return 1 + k * math.exp(-max(0.0, t - t0) / 0.12) * (t > t0)


GREEN = (110, 230, 120)
PINK = (255, 120, 200)
YO = np.array(G.YARD_O)
LO = np.array(G.LAB_O)
MO = np.array(G.MICRO_O)
RIM = np.array([G.HOOP_X, G.HOOP_Y - 1 - G.RIM_R - 0.6, G.RIM_Z])
FAIL_P = [MO + np.array([-4.5, 2.0, 15.0]), MO + np.array([3.0, 4.0, 11.0])]
HERO_CRATER = MO + np.array([2.0, 0.0, -1.0])


def hero_top(t):
    te, _ = T.yard_clock(t)
    return YO + np.array([0, 0, T.jet_top(te if te is not None else 0.0, G.GEYSER_H)])


def overlays(img, t):
    """Big, readable labels (>= 44 px), max 2 text elements at once; labels stay above the caption block."""
    S = T.SHOTS
    i = T.shot_index(t)
    last = len(S) - 1
    if i in (0, T.S_WIDE):                       # the hook: MENTOS + DIET COKE on screen from frame 0
        a = 1 - T.smoother((t - (T.T_BLASTS[0] - 0.1)) / 0.2)
        big(img, "MENTOS", "+ DIET COKE", a, color=AMBER)
        if i == T.S_WIDE:
            a2 = window(t, T.T_HIGHER[0] - 0.05, S[i][1] + 0.3, 0.1)
            label_at(img, "HOOP: 10 FT", RIM, t, a2, ICE, 90)
            label_at(img, "13 FT!", hero_top(t), t, window(t, T.T_HOOP[0] - 0.1, S[i][1] + 0.3, 0.1), HOT, -70)
    if i == last:
        pill(img, "STAND BACK!", CX, 430, 58, alpha=window(t, S[last][0] + 0.05, T.T_BACK[1] - 0.1, 0.1), accent=HOT)
        big(img, "MENTOS", "+ DIET COKE", T.smoother((t - (T.T_BACK[1] - 0.05)) / 0.25), color=AMBER)
    if i == T.S_WHY:
        text_block(img, [["WHY?"]], CX, 430, 150, colors={0: AMBER},
                   alpha=window(t, T.T_WHY[0] - 0.05, T.T_3[0] - 0.2, 0.1), scale=pop(t, T.T_WHY[0] - 0.05, 0.25))
        big(img, "3 BOTTLES", "OF GAS INSIDE", window(t, T.T_3[0] - 0.1, S[i][1] + 0.3, 0.1), color=ICE,
            pop=pop(t, T.T_3[0] - 0.1))
    if i == T.S_SQZ:
        pill(img, "SQUEEZED IN", CX, 430, 54, alpha=window(t, T.T_SQUEEZED[0] - 0.05, T.T_DYING[0] - 0.15, 0.1),
             accent=ICE)
        pill(img, "DYING TO GET OUT", CX, 430, 54, alpha=window(t, T.T_DYING[0] - 0.05, S[i][1] + 0.3, 0.1),
             accent=HOT)
    if i == T.S_SEED:
        for k, ft in enumerate(T.T_FAIL):
            label_at(img, "NOPE", FAIL_P[k], t, window(t, ft + 0.05, ft + 0.6, 0.08), HOT, -110)
        a = window(t, T.T_ROUGH[0] - 0.05, S[i][1] + 0.3, 0.1)
        reticle(img, HERO_CRATER, t, 3.4, a, AMBER)
        label_at(img, "ROUGH SPOT", HERO_CRATER, t, a, AMBER, -260)
    if i == T.S_PITSA:
        pill(img, "ONE CANDY", CX, 430, 54, alpha=window(t, S[i][0] + 0.05, S[i][1] + 0.2, 0.1), accent=ICE)
    if i == T.S_PITSB:
        pill(img, "MAGNIFIED", CX, 430, 54, alpha=window(t, S[i][0] + 0.05, T.T_CRATERS[0] - 0.1, 0.1), accent=ICE)
        text_block(img, [["CRATERS"]], CX, 430, 140, colors={0: AMBER},
                   alpha=window(t, T.T_CRATERS[0] - 0.05, S[i][1] + 0.3, 0.1), scale=pop(t, T.T_CRATERS[0] - 0.05))
    if i == T.S_BUB:
        pill(img, "BUBBLE FACTORIES", CX, 430, 54, alpha=window(t, T.T_SPITS[0] - 0.05, T.T_ALL[0] - 0.1, 0.1),
             accent=ICE)
        text_block(img, [["ALL AT ONCE"]], CX, 430, 120, colors={0: AMBER},
                   alpha=window(t, T.T_ALL[0] - 0.05, S[i][1] + 0.3, 0.1), scale=pop(t, T.T_ALL[0] - 0.05))
    if i == T.S_SINK:
        pill(img, "HEAVY: SINKS FAST", CX, 430, 54, alpha=window(t, T.T_HEAVY[0] - 0.05, T.T_MAKING[0] - 0.1, 0.1),
             accent=ICE)
        pill(img, "BUBBLES TOP TO BOTTOM", CX, 430, 50, alpha=window(t, T.T_MAKING[0] - 0.05, S[i][1] + 0.3, 0.1),
             accent=AMBER)
    if i == T.S_PUSH:
        pill(img, "ONE WAY OUT", CX, 430, 54, alpha=window(t, T.T_ONEWAY[0] - 0.05, T.T_UP[0] - 0.1, 0.1),
             accent=ICE)
        text_block(img, [["UP!"]], CX, 430, 170, colors={0: HOT},
                   alpha=window(t, T.T_UP[0] - 0.05, S[i][1] + 0.3, 0.1), scale=pop(t, T.T_UP[0] - 0.05, 0.3))
    if i == T.S_DIET:
        _, td = T.yard_clock(t)
        a = window(t, S[i][0] + 0.1, T.T_SWEET[0] - 0.1, 0.1)
        label_at(img, "REGULAR", YO + np.array([G.DIET_X[0], 0, T.jet_top(td, G.REG_H) + 6]), t, a, ICE, -60)
        label_at(img, "DIET", YO + np.array([G.DIET_X[1], 0, T.jet_top(td, G.GEYSER_H) + 6]), t, a, HOT, -60)
        pill(img, "SWEETENER HELPS BUBBLES", CX, 430, 50, alpha=window(t, T.T_SWEET[0] - 0.05, S[i][1] + 0.3, 0.1),
             accent=AMBER)


# ---------------------------------------------------------------- image finishing
RNG = np.random.default_rng(5)
YY, XX = np.mgrid[0:H, 0:W]
VIGNETTE = (1 - 0.32 * np.clip(((XX - W / 2) / (W * 0.62)) ** 2 + ((YY - H / 2) / (H * 0.62)) ** 2, 0, 1) ** 1.3)[..., None]


def finish(src, t):
    if src.size == (W, H):
        img = src                                   # rendered at full resolution: no upscale needed
    else:
        img = src.resize((W, H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2.2, percent=55, threshold=2))
    a = np.asarray(img).astype(np.float32) / 255.0
    # bloom: blur of the bright parts at quarter resolution
    small = img.resize((W // 4, H // 4), Image.BILINEAR)
    s = np.asarray(small).astype(np.float32) / 255.0
    lum = s.max(axis=2, keepdims=True)
    bright = np.clip((lum - 0.74) / 0.26, 0, 1) * s
    bl = Image.fromarray((bright * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14))
    bl2 = Image.fromarray((bright * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(40))
    bloom = (np.asarray(bl.resize((W, H), Image.BILINEAR)).astype(np.float32) * 0.55 +
             np.asarray(bl2.resize((W, H), Image.BILINEAR)).astype(np.float32) * 0.45) / 255.0
    a = 1 - (1 - a) * (1 - 0.42 * bloom)                      # screen blend
    a = a * VIGNETTE
    # subtle grade: cool shadows, warm highlights
    lum = a.mean(axis=2, keepdims=True)
    a = a + (0.015 * (1 - lum)) * np.array([-0.4, 0.1, 0.6]) + (0.02 * lum) * np.array([0.5, 0.2, -0.4])
    # film grain
    # (no film grain: the image must stay perfectly clean)
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert("RGBA")


HI_RES_DIR = os.environ.get("HI_RES_FRAMES", "")   # optional dir with full-resolution re-renders


def source_frame(frames, f):
    hi = os.path.join(HI_RES_DIR, f"f_{f:04d}.png") if HI_RES_DIR else ""
    return hi if hi and os.path.exists(hi) else os.path.join(frames, f"f_{f:04d}.png")


def render_frame(frames, f):
    t = f / T.FPS
    src = Image.open(source_frame(frames, f)).convert("RGB")
    img = finish(src, t)
    overlays(img, t)
    draw_captions(img, t)
    return img.convert("RGB")


# ---------------------------------------------------------------- audio
SR = 44100


def note_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def reverb(x, seconds=2.4, mix=0.35, seed=0):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    tt = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-tt * 6.0 / seconds)
    ir = np.convolve(ir, np.ones(8) / 8, mode="same")         # darker tail
    ir /= np.sqrt((ir ** 2).sum())
    m = len(x) + n
    nfft = 1 << (m - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x)]
    return (1 - mix) * x + mix * wet * 0.6


def env(n, a, r):
    e = np.ones(n)
    ka, kr = min(n, int(a * SR)), min(n, int(r * SR))
    e[:ka] = np.linspace(0, 1, ka)
    e[-kr:] *= np.linspace(1, 0, kr)
    return e


def pad_voice(freq, dur, bright=4.0):
    tt = np.arange(int(dur * SR)) / SR
    out = np.zeros_like(tt)
    for det in (-0.004, 0.0, 0.0045):
        f = freq * (1 + det)
        for h in range(1, 9):
            out += np.sin(2 * np.pi * f * h * tt + h) * (1 / h) * math.exp(-h / bright)
    return out / 3


def keys(freq, dur=1.6):
    tt = np.arange(int(dur * SR)) / SR
    x = (np.sin(2 * np.pi * freq * tt) + 0.35 * np.sin(2 * np.pi * 2 * freq * tt) * np.exp(-tt * 3)
         + 0.12 * np.sin(2 * np.pi * 3 * freq * tt) * np.exp(-tt * 6))
    return x * np.exp(-tt * 2.2) * env(len(tt), 0.005, 0.2)


def fold(x, n):
    """Wrap everything that rings on past the loop point back onto the start (circular buffer)."""
    out = x[:n].copy()
    k = n
    while k < len(x):
        seg = x[k:k + n]
        out[:len(seg)] += seg
        k += n
    return out


def make_music_and_sfx():
    """Music + effects as one exact loop period: tails past the end continue at the start."""
    n = int(round(T.DUR * SR))
    ext = n + int(6 * SR)
    music = np.zeros(ext)
    sfx = np.zeros(ext)

    def add(buf, t0, sig, g=1.0):
        i = int(t0 * SR)
        j = min(ext, i + len(sig))
        buf[i:j] += g * sig[: j - i]

    # bright, curious bed: C Am F G | C Am F G -> back to C at the loop. Exactly 8 bars per loop.
    chords = [[36, 52, 55, 60], [33, 52, 57, 60], [29, 53, 57, 60], [31, 50, 55, 59],
              [36, 52, 55, 60], [33, 52, 57, 60], [29, 53, 57, 62], [31, 50, 55, 62]]   # C Am F G | C Am F G
    bar = T.DUR / 8
    for k in range(8):
        t0 = k * bar
        ch = chords[k]
        for m in ch[1:]:
            v = pad_voice(note_hz(m), bar + 1.6, bright=2.5)
            add(music, t0, v * env(len(v), 0.6, 1.2), 0.04)
        st = np.arange(int(2.2 * SR)) / SR
        add(music, t0, np.sin(2 * np.pi * note_hz(ch[0]) * st) * np.exp(-st * 1.0) * env(len(st), 0.01, 0.4), 0.26)
        for e in range(8):                                   # pulsing low eighths (tension)
            st2 = np.arange(int(0.25 * SR)) / SR
            add(music, t0 + e * bar / 8, np.sin(2 * np.pi * note_hz(ch[0] + 12) * st2) * np.exp(-st2 * 14), 0.05)
        arp = [ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 24]
        for e in range(4):
            add(music, t0 + e * bar / 4, keys(note_hz(arp[e % 4]), 0.9) * np.exp(-np.arange(int(0.9 * SR)) / SR * 3), 0.025)
    music = fold(reverb(music, 3.4, 0.5, seed=1), n)            # no fades: the loop is circular

    # --- sound effects (only key moments)
    # --- sound effects (only key moments)
    def thump(f0=110, f1=38, d=1.1, g=1.0):
        st = np.arange(int(d * SR)) / SR
        f = f1 + (f0 - f1) * np.exp(-st * 8)
        return g * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-st * 4.5) * env(len(st), 0.002, 0.2)

    def clink(f=1180, d=0.6):
        st = np.arange(int(d * SR)) / SR
        x = sum(a * np.sin(2 * np.pi * f * r * st) * np.exp(-st * dk) for r, a, dk in
                ((1.0, 0.5, 7), (2.3, 0.3, 9), (3.6, 0.15, 12)))
        return x * env(len(st), 0.001, 0.1)

    def shimmer(d=2.2):
        st = np.arange(int(d * SR)) / SR
        x = sum(np.sin(2 * np.pi * f * st + p) for f, p in ((1175, 0), (1480, 1), (1760, 2), (2217, 3)))
        return x / 4 * np.sin(np.pi * st / d) ** 2

    def swoosh(d=0.6, seed=6, up=True):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(int(d * SR))
        for _ in range(3):
            x = np.convolve(x, np.ones(10) / 10, mode="same")
        st = np.arange(len(x)) / SR
        f = (300 + 900 * st / d) if up else (900 - 700 * st / d)
        tone = 0.25 * np.sin(2 * np.pi * np.cumsum(f) / SR)
        return (x / (np.abs(x).max() + 1e-9) + tone) * np.sin(np.pi * st / d) ** 2

    def pulse_swish(d=0.45, seed=20):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(int(d * SR))
        for _ in range(4):
            x = np.convolve(x, np.ones(14) / 14, mode="same")
        st = np.arange(len(x)) / SR
        return x / (np.abs(x).max() + 1e-9) * np.sin(np.pi * st / d) ** 3

    def snap(d=0.25, seed=21):
        rng = np.random.default_rng(seed)
        st = np.arange(int(d * SR)) / SR
        x = rng.standard_normal(len(st)) * np.exp(-st * 40)
        return x + 0.6 * np.sin(2 * np.pi * 220 * st) * np.exp(-st * 25)

    def chomp(d=0.35, seed=22):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(int(d * SR))
        x = np.convolve(x, np.ones(30) / 30, mode="same")
        st = np.arange(len(x)) / SR
        return x / (np.abs(x).max() + 1e-9) * np.exp(-st * 18) + 0.7 * thump(160, 60, d)

    def plop(f0=260, f1=90, d=0.18):
        st = np.arange(int(d * SR)) / SR
        f = f1 + (f0 - f1) * np.exp(-st * 30)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-st * 22) * env(len(st), 0.002, 0.03)

    def squelch(d=0.5, seed=31):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(int(d * SR))
        x = np.convolve(x, np.ones(25) / 25, mode="same")
        st = np.arange(len(x)) / SR
        wob = 1 + 0.6 * np.sin(2 * np.pi * 9 * st)
        return x / (np.abs(x).max() + 1e-9) * wob * np.sin(np.pi * st / d) ** 2

    def drip(f=1400):
        st = np.arange(int(0.12 * SR)) / SR
        ff = f * (1 + 1.5 * st / 0.12)
        return np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.exp(-st * 40)

    def rumble(d=0.8, seed=33):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(int(d * SR))
        for _ in range(4):
            x = np.convolve(x, np.ones(40) / 40, mode="same")
        st = np.arange(len(x)) / SR
        return x / (np.abs(x).max() + 1e-9) * np.sin(np.pi * st / d)

    def beep(f=1760, d=0.12):
        st = np.arange(int(d * SR)) / SR
        return np.sin(2 * np.pi * f * st) * env(len(st), 0.004, 0.04)

    def boom(d=2.0):
        st = np.arange(int(d * SR)) / SR
        f = 30 + 60 * np.exp(-st * 3)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-st * 1.8) * env(len(st), 0.005, 0.3)

    def splash_snd(d=1.4, seed=40):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(int(d * SR))
        x = x - np.convolve(x, np.ones(6) / 6, mode="same") * 0.6
        st = np.arange(len(x)) / SR
        return x / (np.abs(x).max() + 1e-9) * np.exp(-st * 3.2) * env(len(st), 0.003, 0.2)

    def bubbles(d=2.4, seed=41):
        rng = np.random.default_rng(seed)
        out_ = np.zeros(int(d * SR))
        for _ in range(40):
            t0 = rng.uniform(0, d - 0.2)
            b_ = plop(rng.uniform(300, 900), rng.uniform(120, 300), 0.12) * rng.uniform(0.3, 1.0) * (1 - t0 / d)
            i = int(t0 * SR)
            out_[i:i + len(b_)] += b_[: len(out_) - i]
        return out_

    def ping(f=1250, d=1.6):
        st = np.arange(int(d * SR)) / SR
        return np.sin(2 * np.pi * f * st) * np.exp(-st * 3.0) * env(len(st), 0.005, 0.3)

    def hiss(d, seed=50, lp=6):
        rng = np.random.default_rng(seed)
        x = rng.standard_normal(int(d * SR))
        x = x - np.convolve(x, np.ones(lp) / lp, mode="same") * 0.5
        return x / (np.abs(x).max() + 1e-9) * env(int(d * SR), 0.15, 0.25)

    def crackle(d, seed=51, rate=14):
        rng = np.random.default_rng(seed)
        out_ = np.zeros(int(d * SR))
        for _ in range(int(d * rate)):
            i = int(rng.uniform(0, d - 0.05) * SR)
            k = rng.standard_normal(int(0.012 * SR)) * np.exp(-np.arange(int(0.012 * SR)) / SR * 400)
            out_[i:i + len(k)] += k * rng.uniform(0.3, 1.0)
        return out_

    def whoomp(d=1.4):
        w_ = np.concatenate([swoosh(0.5, 52, up=False), np.zeros(int((d - 0.5) * SR))])
        th = thump(150, 45, d)
        n_ = min(len(w_), len(th))
        return 0.6 * w_[:n_] + 0.9 * th[:n_]

    # ---- every sound comes from what is on screen at that moment (same event lists as the picture)
    S = T.SHOTS
    last = len(S) - 1
    tt = np.arange(ext) / SR

    def curve(fn, smooth=0.02):
        """Sample an envelope function of t on a 10 ms grid, wrapping past the loop point."""
        g = np.arange(0, ext / SR, 0.01)
        v = np.array([fn(x % T.DUR) for x in g])
        k = max(1, int(smooth / 0.01))
        v = np.convolve(v, np.ones(k) / k, mode="same")
        return np.interp(tt, g, v)

    rng_ = np.random.default_rng(70)
    noise = rng_.standard_normal(ext)

    def tinkles(d, seed, rate, f_lo=2500, f_hi=7000, decay=2.2):
        """Glass powder: many tiny high pings whose density dies away."""
        r = np.random.default_rng(seed)
        out_ = np.zeros(int(d * SR))
        for _ in range(int(d * rate)):
            t0 = d * r.random() ** decay
            st_ = np.arange(int(0.08 * SR)) / SR
            k = np.sin(2 * np.pi * r.uniform(f_lo, f_hi) * st_) * np.exp(-st_ * r.uniform(40, 90))
            i = int(t0 * SR)
            out_[i:i + len(k)] += k[: len(out_) - i] * r.uniform(0.2, 1.0)
        return out_

    def clang(d=1.8):
        st = np.arange(int(d * SR)) / SR
        x = sum(a * np.sin(2 * np.pi * f * st + p) * np.exp(-st * dk) for f, a, p, dk in
                ((523, 0.5, 0, 3.0), (1187, 0.35, 1, 4.0), (1906, 0.25, 2, 5.5), (2843, 0.18, 3, 7.0), (3720, 0.1, 4, 9.0)))
        return x * env(len(st), 0.001, 0.3)

    def pop_snd(seed, g=1.0, pitch=1.0):
        """The pop: a sharp burst of escaping steam (bright noise snap) + a small body thump."""
        r = np.random.default_rng(seed)
        st_ = np.arange(int(0.35 * SR)) / SR
        x = r.standard_normal(len(st_)) * np.exp(-st_ * 55)
        x = x - np.convolve(x, np.ones(4) / 4, mode="same") * 0.5
        body = thump(260 * pitch, 90 * pitch, 0.35)
        return g * (0.9 * x / (np.abs(x).max() + 1e-9) + 0.6 * body[: len(x)])

    def foam_whoosh(d=0.9, seed=110):
        r = np.random.default_rng(seed)
        x = r.standard_normal(int(d * SR))
        for _ in range(3):
            x = np.convolve(x, np.ones(8) / 8, mode="same")
        st_ = np.arange(len(x)) / SR
        return x / (np.abs(x).max() + 1e-9) * np.exp(-st_ * 4) * env(len(st_), 0.01, 0.2)

    def burst_at(t0, seed, g=1.0):
        add(sfx, t0 + 0.08, pop_snd(seed, 0.9), 0.55 * g)
        add(sfx, t0 + 0.08, crackle(0.25, seed + 1, 200), 0.25 * g)
        add(sfx, t0 + 0.1, foam_whoosh(0.9, seed + 2), 0.18 * g)

    def rocks(d, seed, rate=60):
        """Rock debris: dull low knocks and grit."""
        return crackle(d, seed, rate) * 0.6 + tinkles(d, seed + 1, rate * 0.5, 400, 1400, 1.6) * 0.5

    def zap(d=0.6, f0=2400, f1=300, seed=300):
        """Laser shot: a fast falling sweep + a bright buzz."""
        st_ = np.arange(int(d * SR)) / SR
        f = f1 + (f0 - f1) * np.exp(-st_ * 9)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.35 * np.sign(np.sin(2 * np.pi * np.cumsum(f * 0.5) / SR))
        return x * np.exp(-st_ * 5) * env(len(st_), 0.002, 0.1)

    def hum(d, f=55):
        st_ = np.arange(int(d * SR)) / SR
        x = sum(np.sin(2 * np.pi * f * h * st_) / h for h in (1, 2, 3, 5))
        return x * env(len(st_), 0.08, 0.2)

    def sweep(d, f0, f1):
        st_ = np.arange(int(d * SR)) / SR
        f = f0 * (f1 / f0) ** (st_ / d)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(st_), 0.05, 0.15)

    def blast_at(t0, seed, g=1.0):
        """The capsule bursts: crack, boom, glassy shards and a plasma hiss."""
        add(sfx, t0, snap(0.3, seed), 0.45 * g)
        add(sfx, t0, boom(2.2), 0.55 * g)
        add(sfx, t0 + 0.02, tinkles(1.8, seed + 1, 160, 2500, 8000, 1.8), 0.16 * g)
        add(sfx, t0 + 0.05, hiss(1.6, seed + 2, 5) * np.linspace(1.0, 0.2, int(1.6 * SR)), 0.1 * g)
        for k, tw in enumerate((0.3, 0.7, 1.1)):                   # shards flying past the lens
            add(sfx, t0 + tw, swoosh(0.4, seed + 3 + k, up=False), 0.11 * g)

    def honk(f=420, d=0.22):
        st_ = np.arange(int(d * SR)) / SR
        ff = f * (1 + 0.15 * np.sin(np.pi * st_ / d))
        ph = np.cumsum(ff) / SR
        x = np.sign(np.sin(2 * np.pi * ph)) * 0.5 + np.sin(4 * np.pi * ph) * 0.3
        x = np.convolve(x, np.ones(6) / 6, mode="same")
        return x * env(len(st_), 0.02, 0.06)

    def chirp(f=2600, d=0.18):
        st_ = np.arange(int(d * SR)) / SR
        ff = f * (1 - 0.35 * st_ / d) + 300 * np.sin(2 * np.pi * 30 * st_)
        return np.sin(2 * np.pi * np.cumsum(ff) / SR) * env(len(st_), 0.01, 0.06)

    def poof(d=0.7, seed=500):
        r = np.random.default_rng(seed)
        x = r.standard_normal(int(d * SR))
        for _ in range(5):
            x = np.convolve(x, np.ones(18) / 18, mode="same")
        st_ = np.arange(len(x)) / SR
        return x / (np.abs(x).max() + 1e-9) * np.exp(-st_ * 5) * env(len(st_), 0.004, 0.1)

    def cannon(seed):
        """Air cannon: a deep pneumatic boom + a hiss of escaping air."""
        return boom(2.0)[: int(2.0 * SR)] * 0.8 + np.pad(hiss(1.2, seed, 4) * np.linspace(1, 0, int(1.2 * SR)),
                                                          (0, int(0.8 * SR)))[: int(2.0 * SR)] * 0.5

    def impact_at(t0, seed, g=1.0, glass=False):
        add(sfx, t0, thump(150, 45, 1.0), 0.6 * g)
        add(sfx, t0, snap(0.25, seed), 0.45 * g)
        add(sfx, t0 + 0.01, poof(0.8, seed + 1), 0.35 * g)
        add(sfx, t0 + 0.02, crackle(0.35, seed + 2, 120), 0.18 * g)
        if glass:
            add(sfx, t0, tinkles(2.0, seed + 3, 220, 2500, 8000, 1.6), 0.3 * g)
            add(sfx, t0, clang(1.0), 0.08 * g)
        for k, tw in enumerate((0.25, 0.6)):                       # feathers fly past the lens
            add(sfx, t0 + tw, swoosh(0.45, seed + 4 + k, up=False), 0.1 * g)

    def jet(d, seed=600):
        r = np.random.default_rng(seed)
        x = r.standard_normal(int(d * SR))
        for _ in range(6):
            x = np.convolve(x, np.ones(30) / 30, mode="same")
        st_ = np.arange(len(x)) / SR
        return (x / (np.abs(x).max() + 1e-9) * 0.7 + 0.25 * np.sin(2 * np.pi * 96 * st_)) * env(len(x), 0.15, 0.15)

    # ---- every sound comes from what is on screen at that moment (same clocks as the picture)
    def lowpass(x, k):
        for _ in range(3):
            x = np.convolve(x, np.ones(k) / k, mode="same")
        return x

    def wind(d, seed, k=20):
        r = np.random.default_rng(seed)
        x = lowpass(r.standard_normal(int(d * SR)), k)
        return x / (np.abs(x).max() + 1e-9)

    def tear(d=1.6, seed=900):
        """Metal ripping: dense crackle + a falling screech + low boom."""
        st = np.arange(int(d * SR)) / SR
        cr = crackle(d, seed, 260) * np.exp(-st * 2.2)
        f = 900 * np.exp(-st * 1.5) + 180
        scr = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-st * 2.5) * (1 + 0.5 * np.sin(2 * np.pi * 31 * st))
        return 0.8 * cr + 0.25 * scr + 0.9 * boom(d)[: len(st)]

    def groan(d=1.2, f0=70, seed=901):
        st = np.arange(int(d * SR)) / SR
        r = np.random.default_rng(seed)
        f = f0 * (1 + 0.15 * np.sin(2 * np.pi * 1.3 * st) + 0.05 * lowpass(r.standard_normal(len(st)), 400) * 20)
        x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.3 + np.sin(2 * np.pi * np.cumsum(f * 2.01) / SR)
        return lowpass(x, 6) * np.sin(np.pi * st / d) ** 2

    S = T.SHOTS
    last = len(S) - 1

    def fizz(d, seed, bright=3):
        """Carbonation: dense tiny pops over a soft hiss."""
        return 0.6 * hiss(d, seed, bright) + 0.5 * crackle(d, seed + 1, 900) * env(int(d * SR), 0.05, 0.2)

    def roar(d, seed, strength):
        """The geyser: a wide foamy whoosh-roar following the jet strength curve."""
        r = np.random.default_rng(seed)
        x = r.standard_normal(int(d * SR))
        lo = lowpass(x, 9)
        hi = x - lowpass(x, 4)
        st_ = np.arange(len(x)) / SR
        s = np.array([strength(v) for v in st_[::441]])
        s = np.interp(st_, st_[::441], s)
        y = (0.75 * lo / (np.abs(lo).max() + 1e-9) + 0.35 * hi / (np.abs(hi).max() + 1e-9)) * s
        return y + 0.4 * crackle(d, seed + 1, 500) * s

    def patter(d, seed, rate=70):
        """Soda and foam raining down on the grass."""
        return lowpass(crackle(d, seed, rate), 3) * 2.0 * env(int(d * SR), 0.3, 0.4)

    def clack(seed, f=2100):
        r = np.random.default_rng(seed)
        st_ = np.arange(int(0.06 * SR)) / SR
        return (np.sin(2 * np.pi * f * r.uniform(0.9, 1.1) * st_) * np.exp(-st_ * 90) +
                r.standard_normal(len(st_)) * np.exp(-st_ * 160) * 0.5)

    def ratchet(d, seed, rate=18):
        out_ = np.zeros(int(d * SR))
        for k in range(int(d * rate)):
            c = clack(seed + k, 3200)
            i = int(k / rate * SR)
            out_[i:i + len(c)] += c[: len(out_) - i]
        return out_

    def creak(d, seed):
        st_ = np.arange(int(d * SR)) / SR
        r = np.random.default_rng(seed)
        f = 140 * (1 + 0.25 * np.sin(2 * np.pi * 2.3 * st_) + 0.1 * lowpass(r.standard_normal(len(st_)), 600) * 20)
        x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.4 + np.sin(2 * np.pi * np.cumsum(f * 3) / SR) * 0.3
        return lowpass(x, 5) * np.sin(np.pi * st_ / d) ** 2

    def bloop_up(d=0.6, f0=180, f1=700):
        st_ = np.arange(int(d * SR)) / SR
        f = f0 * (f1 / f0) ** (st_ / d) * (1 + 0.05 * np.sin(2 * np.pi * 14 * st_))
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(st_), 0.03, 0.12)

    def collapse(d=0.3):
        st_ = np.arange(int(d * SR)) / SR
        f = 900 * np.exp(-st_ * 9) + 120
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-st_ * 9) * env(len(st_), 0.002, 0.05)

    def dense_bubbles(d, seed, rate=60, lo=300, hi=1400):
        r = np.random.default_rng(seed)
        out_ = np.zeros(int(d * SR))
        for _ in range(int(d * rate)):
            t0 = r.uniform(0, d - 0.15)
            b_ = plop(r.uniform(lo, hi), r.uniform(100, 300), 0.1) * r.uniform(0.3, 1.0)
            i = int(t0 * SR)
            out_[i:i + len(b_)] += b_[: len(out_) - i]
        return out_

    S = T.SHOTS
    last = len(S) - 1
    # ---- the hero geyser (loop shot -> S0 -> S1, one take across the seam): Mentos clatter in, fizz, ERUPTION
    tb = T.DUR - T.RE0                                               # eruption start (folds round to before frame 0)
    for k in range(G.N_MENTOS):
        tk = tb + T.T_LOOP_DROP + 0.035 * k + math.sqrt(2 * 30.0 / G.G_IN)
        add(sfx, tk, clack(1200 + k, 1800 + 120 * k), 0.12)
        add(sfx, tk + 0.04, plop(500, 160, 0.14), 0.12)
    add(sfx, tb - 0.33, fizz(0.4, 1210) * np.linspace(0.2, 1, int(0.4 * SR)), 0.25)
    d_er = T.DUR - tb + S[T.S_WIDE][1] + 0.1
    er = roar(d_er, 1220, T.geyser_strength)
    er *= env(len(er), 0.01, 0.12)
    add(sfx, tb, er, 0.32)
    add(sfx, tb, thump(120, 45, 0.8), 0.45)
    add(sfx, tb, swoosh(0.6, 1230, up=True), 0.18)
    add(sfx, tb + 1.3, patter(d_er - 1.3, 1240), 0.18)
    for k, tw in enumerate((0.25, 0.55, 0.95)):                     # drops flying past the lens
        add(sfx, tb + tw, swoosh(0.35, 1250 + k, up=False), 0.08)
    # ---- WHY: a thump; three ghost bottles of gas pop out (airy pops + rising chimes)
    add(sfx, T.T_WHY[0] - 0.05, thump(140, 60, 0.5), 0.3)
    add(sfx, S[T.S_WHY][0], fizz(S[T.S_WHY][1] - S[T.S_WHY][0] + 0.1, 1300, 4), 0.05)
    for k in range(3):
        tg = T.T_GHOST + 0.14 * k
        add(sfx, tg, poof(0.5, 1310 + k), 0.2)
        add(sfx, tg + 0.05, ping(1046 * 2 ** (k * 4 / 12), 0.8), 0.05)
    # ---- squeezed in: each ghost slams back in, the cap screws on; the gas rattles and the bottle creaks
    d_s = S[T.S_SQZ][1] - S[T.S_SQZ][0]
    add(sfx, S[T.S_SQZ][0], fizz(d_s + 0.1, 1400, 4), 0.05)
    for k, ts_ in enumerate(T.T_SQZ):
        add(sfx, ts_ + 0.18, thump(170, 70, 0.4), 0.35)
        add(sfx, ts_, swoosh(0.25, 1410 + k, up=False), 0.12)
    add(sfx, T.T_CAP - 0.3, ratchet(0.35, 1420), 0.12)
    add(sfx, T.T_CAP + 0.05, clink(900, 0.3), 0.08)
    dj = S[T.S_SQZ][1] - T.T_JITTER
    add(sfx, T.T_JITTER, crackle(dj, 1430, 160) * np.linspace(0.4, 1, int(dj * SR)), 0.12)
    add(sfx, T.T_JITTER, creak(dj, 1440), 0.08)
    add(sfx, T.T_JITTER, hiss(dj, 1450, 3) * np.linspace(0.2, 1, int(dj * SR)), 0.06)
    # ---- inside the soda: a bubble tries and collapses (twice); in the rough spot it grows
    d_m = S[T.S_SEED][1] - S[T.S_SEED][0]
    add(sfx, S[T.S_SEED][0], wind(d_m + 0.1, 1500, 60) * env(int((d_m + 0.1) * SR), 0.2, 0.2), 0.08)
    for k, ft in enumerate(T.T_FAIL):
        add(sfx, ft, bloop_up(0.22, 300, 650), 0.08)
        add(sfx, ft + 0.25, collapse(0.3), 0.1)
    add(sfx, T.T_HERO, bloop_up(0.9, 140, 520), 0.1)
    add(sfx, T.T_ROUGH[0] - 0.05, ping(1568, 1.0), 0.05)
    # ---- one Mentos up close (zoom in), then the cratered surface appears
    add(sfx, S[T.S_PITSA][0], swoosh(0.7, 1600, up=True), 0.12)
    add(sfx, S[T.S_PITSB][0], swoosh(0.5, 1610, up=False), 0.1)
    add(sfx, T.T_CRATERS[0] - 0.05, shimmer(1.2), 0.05)
    # ---- every crater spits bubbles at once: a dense rush of bloops + fizz
    d_b = S[T.S_BUB][1] - T.T_ALLON
    add(sfx, T.T_ALLON, dense_bubbles(d_b + 0.1, 1700, 110), 0.12)
    add(sfx, T.T_ALLON, fizz(d_b + 0.1, 1710, 3) * np.linspace(0.3, 1, int((d_b + 0.1) * SR)), 0.1)
    add(sfx, T.T_ALL[0] - 0.05, whoomp(0.9), 0.15)
    # ---- the Mentos drop in one by one and sink; bubbles stream up, foam builds
    al = math.sqrt(2 * (3.5 + G.BOT_TOP - G.FILL_Z) / G.G_IN)
    for k in range(G.N_MENTOS):
        tk = T.T_SINK0 + k * T.MENTOS_DT
        add(sfx, tk + al * 0.6, clack(1800 + k, 2000 + 100 * k), 0.08)
        add(sfx, tk + al, plop(380 - 20 * k, 120, 0.2), 0.22)
    d_k = S[T.S_PUSH][1] - T.T_SINK0
    add(sfx, T.T_SINK0 + al, dense_bubbles(d_k, 1800, 70), 0.1)
    add(sfx, T.T_SINK0 + al, fizz(d_k, 1810, 3) * np.linspace(0.2, 1, int(d_k * SR)), 0.12)
    # ---- the foam climbs the neck (rising pressure tone) and bursts out: UP!
    d_p = T.T_JET_LAB - S[T.S_PUSH][0]
    add(sfx, S[T.S_PUSH][0], sweep(d_p, 120, 480) * np.linspace(0.2, 1, int(d_p * SR)), 0.07)
    jl = roar(S[T.S_PUSH][1] - T.T_JET_LAB + 0.15, 1900, lambda x: max(0.0, 1 - x / 1.6))
    add(sfx, T.T_JET_LAB, jl * env(len(jl), 0.005, 0.1), 0.3)
    add(sfx, T.T_JET_LAB, thump(130, 50, 0.7), 0.4)
    # ---- regular vs diet: two eruptions, diet's twice as big
    d_d = S[T.S_DIET][1] - T.T_DIET_GO + 0.1
    for k, (g_, sd) in enumerate(((0.5, 2000), (1.0, 2010))):
        r_ = roar(d_d, sd, T.geyser_strength)
        add(sfx, T.T_DIET_GO, r_ * env(len(r_), 0.01, 0.12), 0.18 * g_)
    add(sfx, T.T_DIET_GO, thump(120, 45, 0.6), 0.3)
    add(sfx, T.T_DIET_GO + 1.3, patter(d_d - 1.3, 2020), 0.14)
    add(sfx, T.T_BEST[0] - 0.05, ping(1318, 1.2), 0.05)
    add(sfx, T.T_SWEET[0] - 0.05, shimmer(1.2), 0.05)
    for k_ in range(1, len(S)):                                               # every cut: a short air swish
        if k_ != last:
            add(sfx, S[k_][0] - 0.12, pulse_swish(0.35, 80 + k_), 0.07)
    sfx = fold(reverb(sfx, 2.2, 0.35, seed=2), n)
    return music, sfx


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- subtitles
def write_srt(path):
    def ts(x):
        h, m = int(x // 3600), int(x % 3600 // 60)
        s = x % 60
        return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    out = []
    wt = TIMING["words"]
    k = 0
    for i, (key, spoken, cap, _p) in enumerate(LINES, 1):
        n = len([w for w in cap.split() if w != "|"])
        a, b = wt[k][0], wt[k + n - 1][1]                 # measured start of first word, end of last word
        k += n
        proper = {}

        def norm(w):
            m = re.match(r"^(\W*)(.*?)(\W*)$", w)
            pre, core, post_ = m.groups()
            if core.isupper() and len(core) > 1:
                core = proper.get(core, core.lower())
            return pre + core + post_
        words = [norm(w) for w in cap.split() if w != "|"]
        text = " ".join(words)
        text = text[0].upper() + text[1:]
        text = re.sub(r"([.?!]) (\w)", lambda m_: m_.group(1) + " " + m_.group(2).upper(), text)
        out.append(f"{i}\n{ts(a)} --> {ts(b)}\n{text}\n")
    open(path, "w").write("\n".join(out))


def main():
    frames, out = sys.argv[1], sys.argv[2]
    if "--preview" in sys.argv:
        for f in [int(v) for v in sys.argv[sys.argv.index("--preview") + 1].split(",")]:
            render_frame(frames, f).save(f"{out}_{f:04d}.png")
        return
    music, sfx = make_music_and_sfx()
    n = len(music)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(HERE, "vo", "vo_raw.wav"), "-ac", "1",
                          "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    voice = fold(np.frombuffer(raw, np.float32).astype(float), n)
    # Mix three loop periods back to back and keep the middle one: echo tails, ducking and compressor
    # state then carry straight across the loop point, exactly as when the Short replays.
    mw, sw, vo = out + ".music.wav", out + ".sfx.wav", out + ".voice.wav"
    write_wav(mw, np.tile(music / (np.abs(music).max() + 1e-9) * 0.8, 3))
    write_wav(sw, np.tile(sfx / (np.abs(sfx).max() + 1e-9) * 0.8, 3))
    write_wav(vo, np.tile(voice / (np.abs(voice).max() + 1e-9) * 0.89, 3))
    filt = (
        # voice: warm documentary chain
        "[1:a]aformat=sample_rates=44100:channel_layouts=mono,highpass=f=75,"
        "equalizer=f=190:t=q:w=1.1:g=2.5,equalizer=f=3000:t=q:w=1.0:g=2,equalizer=f=7500:t=q:w=1.5:g=-1.5,"
        "deesser=i=0.35,acompressor=threshold=-20dB:ratio=3:attack=8:release=140:makeup=2,"
        "aecho=0.85:0.6:28|47:0.07|0.04,alimiter=limit=0.9,asplit=2[v1][v2];"
        # music ~6 dB under the voice and ducked further while he speaks
        "[2:a]volume=0.27[mu];[mu][v1]sidechaincompress=threshold=0.03:ratio=6:attack=25:release=420[md];"
        "[3:a]volume=0.42[fx];"
        "[v2][md][fx]amix=inputs=3:normalize=0,aformat=channel_layouts=stereo,"
        f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100,atrim=start_sample={n}:end_sample={2 * n},asetpts=PTS-STARTPTS[a]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(T.FPS), "-i", "-", "-i", vo, "-i", mw, "-i", sw, "-filter_complex", filt,
           "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-ar", "44100", "-c:a", "aac", "-b:a", "192k", "-t", str(T.DUR),
           "-movflags", "+faststart", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(T.NFRAMES):
        ff.stdin.write(render_frame(frames, f).tobytes())
        if f % 100 == 0:
            print(f"post {f}/{T.NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    for p_ in (mw, sw, vo):
        os.remove(p_)
    write_srt(os.path.splitext(out)[0] + ".srt")
    print("done:", out)


if __name__ == "__main__":
    main()
