"""Post-production for the burning-diamond Short: grade + bloom + grain, captions & counters in the Shorts
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


def big(img, value, unit, alpha, pop=1.0, color=AMBER):
    text_block(img, [[value]], CX, 420, 132, alpha=alpha, scale=pop, colors={0: color})
    pill(img, unit, CX, 530, 46, alpha=alpha, accent=color)


def label_at(img, text, p, t, alpha, accent=ICE, dy=-120):
    x, y = project(p, t)
    x = min(max(x, SAFE[0] + 140), SAFE[2] - 140)
    pill(img, text, x, y + dy, 46, alpha=alpha, accent=accent)


def overlays(img, t):
    """Big, readable labels (>= 44 px), max 2 text elements at once."""
    S = T.SHOTS
    i = T.shot_index(t)
    last = len(S) - 1
    if i == 0:                                   # the hook: the temperature on screen from frame 0
        big(img, "1,500\u00b0F", "DIAMOND ON FIRE", 1 - T.smoother((t - S[0][1] + 0.25) / 0.2), color=AMBER)
    if i == last:
        big(img, "1,500\u00b0F", "DIAMOND ON FIRE", T.smoother((t - T.T_LOOK + 0.25) / 0.3), color=AMBER)
    if i == 1:
        big(img, "C", "100% CARBON ATOMS", window(t, T.T_PURE - 0.1, S[1][1], 0.15), color=ICE)
    if i == 2:
        a = window(t, S[2][0] + 0.05, S[2][1], 0.12)
        label_at(img, "DIAMOND", (0.0, 0.0, 1.5), t, a)
        label_at(img, "CHARCOAL", (2.75, 0.5, 1.4), t, a)
    if i == 3:
        u = T.smoother((t - T.T_1500 + 0.3) / (T.T_BURNS - T.T_1500 + 0.1))
        v = 70 + (1500 - 70) * u
        v = 1500 if u > 0.999 else int(round(v / 10) * 10)
        pop = 1 + 0.25 * math.exp(-max(0, t - T.T_BURNS) / 0.08) if t > T.T_BURNS else 1.0
        big(img, f"{v:,}\u00b0F", "IN PURE OXYGEN" if t > T.T_OXY - 0.05 else "HEATING UP",
            window(t, T.T_1500 - 0.35, S[3][1], 0.15), pop=pop, color=AMBER if t > T.T_BURNS - 0.05 else ICE)
    if i == 4:
        big(img, "CO2", "CARBON DIOXIDE GAS", window(t, T.T_CO2 - 0.1, S[4][1], 0.15), color=AMBER)
    if i == 6:
        big(img, "GRAPHITE", "PENCIL LEAD IS CARBON TOO", window(t, S[6][0] + 0.1, S[6][1], 0.12), color=ICE)
    if i == 7:
        u = T.smoother((t - S[7][0] - 0.1) / (S[7][1] - S[7][0] - 0.35))
        n = int(round(1_000_000 * u ** 2 / 1000) * 1000) if u < 0.999 else 1_000_000
        big(img, f"{n:,} YEARS", "STILL A DIAMOND", window(t, S[7][0] + 0.05, S[7][1], 0.12), color=AMBER)


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
    ka, kr = int(a * SR), int(r * SR)
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

    # dark, deep bed: Dm Bb F C | Dm Bb Gm A -> back to Dm at the loop. Exactly 8 bars per loop.
    chords = [[40, 52, 55, 59], [36, 52, 55, 60], [43, 50, 55, 59], [38, 50, 54, 57],
              [40, 52, 55, 59], [36, 52, 55, 60], [45, 52, 57, 60], [35, 51, 54, 59]]
    bar = T.DUR / 8
    for k in range(8):
        t0 = k * bar
        ch = chords[k]
        for m in ch[1:]:
            v = pad_voice(note_hz(m), bar + 1.6, bright=2.0)
            add(music, t0, v * env(len(v), 0.6, 1.2), 0.035)
        st = np.arange(int(2.2 * SR)) / SR
        add(music, t0, np.sin(2 * np.pi * note_hz(ch[0] - 12) * st) * np.exp(-st * 1.2) * env(len(st), 0.01, 0.4), 0.22)
        arp = [ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 24]
        for e in range(8):
            add(music, t0 + e * bar / 8, keys(note_hz(arp[e % 4]), 0.9) * np.exp(-np.arange(int(0.9 * SR)) / SR * 3), 0.035)
    music = fold(reverb(music, 3.0, 0.45, seed=1), n)            # no fades: the loop is circular

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

    fire = curve(lambda x: 1.0 if T.shot_set(x) == "fire" else 0.0, 0.06)
    atoms = curve(lambda x: 1.0 if T.shot_set(x) == "atoms" else 0.0, 0.06)
    # the oxygen torch: a roaring hiss exactly while the flame is on screen
    rng_ = np.random.default_rng(70)
    noise = rng_.standard_normal(ext)
    roar = noise - np.convolve(noise, np.ones(5) / 5, mode="same") * 0.7
    low = np.convolve(noise, np.ones(80) / 80, mode="same") * 6
    torch_env = curve(T.torch) * fire
    sfx[:] += (0.10 * roar + 0.12 * low) * torch_env
    # the burning diamond: crackles whose density follows the heat (none when it is cold)
    heat_env = curve(lambda x: T.heat(x) ** 2) * fire
    clicks = (rng_.random(ext) < 45 / SR).astype(float) * rng_.uniform(0.3, 1.0, ext)
    ck = np.exp(-np.arange(int(0.006 * SR)) / SR * 900)
    crack_bed = np.convolve(clicks, ck, mode="same") * rng_.choice([-1, 1], ext)
    sfx[:] += 0.5 * crack_bed * heat_env
    # heating up: a sizzle that rises in pitch with the temperature counter (S3)
    a3, b3 = T.T_1500 - 0.3, T.bursts()[0]
    st = np.arange(int((b3 - a3) * SR)) / SR
    f_ = 180 + 900 * (st / st[-1]) ** 2
    sizzle = np.sin(2 * np.pi * np.cumsum(f_) / SR) * (st / st[-1]) ** 1.5 * 0.5 + hiss(len(st) / SR, 71) * (st / st[-1])
    add(sfx, a3, sizzle, 0.12)
    # every spark burst: a whoomp of flame + a shower of sparks
    for b in T.bursts():
        add(sfx, b, whoomp(), 0.55)
        add(sfx, b, crackle(0.9, 72, 40), 0.35)
    add(sfx, 0.0, thump(140, 45, 0.8), 0.45)                                  # the hit on frame 0
    # atom scale: a soft airy bed
    air = np.convolve(noise, np.ones(30) / 30, mode="same") * 4
    sfx[:] += 0.05 * air * atoms
    for k in range(1, len(S)):                                                # every cut: a short air swish
        add(sfx, S[k][0] - 0.12, pulse_swish(0.35, 80 + k), 0.07)
    add(sfx, T.T_PURE, shimmer(1.2), 0.04)                                    # "pure carbon"
    add(sfx, S[2][0] + 0.05, clink(1760, 0.5), 0.10)                          # the two labels pop on
    add(sfx, S[2][0] + 0.12, plop(300, 140, 0.15), 0.12)
    add(sfx, S[3][0] + 0.15, swoosh(0.35, 73, up=True), 0.10)                 # the torch lights
    add(sfx, S[last][0] + 0.3, swoosh(0.35, 74, up=True), 0.10)
    for j in range(T.N_MOL):                                                  # each CO2 molecule
        td = T.mol_depart(j)
        add(sfx, td - 0.45, beep(1300 + 37 * (j % 7), 0.08), 0.018)           # oxygens swoop in
        add(sfx, td, plop(620 + 23 * (j % 9), 260, 0.14), 0.09)               # ... and it pops off
    add(sfx, S[5][0] + 0.1, shimmer(2.4), 0.07)                               # the ring sparkles
    for k, dt in enumerate((0.35, 1.25, 2.1)):
        add(sfx, S[5][0] + dt, clink(2637 + 300 * k, 0.9), 0.05)
    # the pencil: scratching while it moves
    pen = curve(lambda x: 1.0 if T.shot_index(x) == 6 and 0 < T.pencil_u(x) < 1 else 0.0, 0.03)
    scratch = noise - np.convolve(noise, np.ones(3) / 3, mode="same")
    grain = 0.6 + 0.4 * np.sin(2 * np.pi * 13 * tt) ** 2
    sfx[:] += 0.10 * scratch * pen * grain
    # the time-lapse: each day the sun sweeps over with a whoosh, the counter ticks
    for tp in T.day_peaks():
        add(sfx, tp - 0.3, swoosh(0.6, 75, up=True), 0.12)
    for k in range(12):
        add(sfx, S[7][0] + 0.06 + k * 0.12, beep(2600, 0.06), 0.03)
    add(sfx, T.DUR - 0.8, swoosh(0.8, 76, up=True), 0.12)                    # rising into the loop
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
        proper = {"LOOK.": "Look."}

        def norm(w):
            m = re.match(r"^(\W*)(.*?)(\W*)$", w)
            pre, core, post_ = m.groups()
            if core.isupper() and len(core) > 1:
                core = proper.get(core, core.lower())
            return pre + core + post_
        words = [norm(w) for w in cap.split() if w != "|"]
        text = " ".join(words)
        text = text[0].upper() + text[1:]
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
