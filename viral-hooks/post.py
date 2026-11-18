"""Post-production: upscale Blender frames to 1080x1920, add captions/HUD/labels, sound, encode MP4.

Usage:  python3 post.py <frames_dir> <out.mp4>
"""
import json
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timeline as TL  # noqa: E402

W, H = 1080, 1920
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
YELLOW = (255, 214, 64)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
CYAN = (110, 210, 255)
_f = {}

# Defaults (no voiceover). main() swaps these for the voiceover's timing when vo.json is given.
CAPS = TL.CAPTIONS
BEATS = {"jump": 2.4, "center": 15.1, "crazy": 18.2, "stop": 28.1}
REMAP = [(0.0, 0.0), (TL.DUR, TL.DUR)]          # (output time, source animation time)
# with voiceover: ease into the arrival, hold the 'peek' while he says "stop", then speed up the fall back
REMAP_VO = [(0.0, 0.0), (26.0, 26.0), (29.6, 28.0), (32.1, 29.6), (TL.DUR, TL.DUR)]


def src_time(t):
    """Map output time to animation (render) time."""
    xs, ys = zip(*REMAP)
    return float(np.interp(t, xs, ys))


def font(size, bold=True):
    k = (int(size), bold)
    if k not in _f:
        _f[k] = ImageFont.truetype(FONT_B if bold else FONT_R, k[0])
    return _f[k]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_back(x):
    x = clamp(x)
    c = 1.8
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def wrap(words, f, maxw, d):
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if cur and d.textlength(test, font=f) > maxw:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def is_hot(w):
    core = "".join(ch for ch in w if ch.isalpha())
    return len(core) > 1 and core.isupper() or any(ch.isdigit() for ch in w)


def caption(img, text, cy, size, scale=1.0, alpha=1.0, maxw=940):
    """Shorts-style caption: bold, thick outline, key words in yellow."""
    if alpha <= 0.01:
        return
    size = int(size * scale)
    f = font(size)
    layer = Image.new("RGBA", (W, int(size * 4.2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lines = wrap(text.split(), f, maxw * scale, d)
    lh = size * 1.18
    top = layer.height / 2 - lh * len(lines) / 2
    sw = max(3, size // 9)
    for i, ln in enumerate(lines):
        total = d.textlength(" ".join(ln), font=f)
        x = W / 2 - total / 2
        y = top + i * lh
        for w in ln:
            col = YELLOW if is_hot(w) else WHITE
            d.text((x, y), w, font=f, fill=col, stroke_width=sw, stroke_fill=BLACK)
            x += d.textlength(w + " ", font=f)
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(layer, (0, int(cy - layer.height / 2)))


def pill(d, x, y, text, size, fg=WHITE, bg=(0, 0, 0, 170), anchor="l"):
    f = font(size)
    tw = d.textlength(text, font=f)
    pad = size * 0.45
    if anchor == "c":
        x -= (tw + 2 * pad) / 2
    d.rounded_rectangle([x, y - size * 0.75, x + tw + 2 * pad, y + size * 0.75], radius=size * 0.75, fill=bg)
    d.text((x + pad, y), text, font=f, fill=fg, anchor="lm")
    return x + tw + 2 * pad


def window(t, a, b, fade=0.2):
    return clamp((t - a) / fade) * clamp((b - t) / fade)


def overlay(img, t, pr, tc=None):
    """t = animation time (HUD, labels), tc = output time (captions)."""
    tc = t if tc is None else tc
    d = ImageDraw.Draw(img, "RGBA")

    # hook title (first ~2.7 s)
    a = window(t, 0.0, 2.7, 0.15) if t > 0.15 else 1.0
    if a > 0:
        s = 0.6 + 0.4 * ease_out_back(t / 0.35) if t < 0.35 else 1.0
        caption(img, "WHAT IF YOU JUMPED THROUGH THE EARTH?", 300, 92, s, a, maxw=980)

    # HUD: timer + speed
    ha = window(t, 2.4, 31.6, 0.3)
    if ha > 0:
        mins = TL.minutes(t)
        mm, ss = int(mins), int((mins % 1) * 60)
        kmh = 28400 * TL.speed_frac(t)
        spd = int(round(kmh, -2))
        mph = int(round(kmh * 0.621371, -2))
        bg = (0, 0, 0, int(160 * ha))
        fg = tuple(int(c) for c in WHITE) + (int(255 * ha),)
        hot = (YELLOW if spd > 25000 else WHITE) + (int(255 * ha),)
        y0 = 520 if t < 2.7 else 170
        x = pill(d, 70, y0, f"TIME  {mm:02d}:{ss:02d} min", 40, fg, bg)
        pill(d, x + 24, y0, f"SPEED  {spd:,} km/h", 40, hot, bg)
        pill(d, x + 24, y0 + 72, f"= {mph:,} mph", 40, hot, bg)
        # speed bar
        bw, by = 940, y0 + 132
        d.rounded_rectangle([70, by, 70 + bw, by + 16], radius=8, fill=(255, 255, 255, int(50 * ha)))
        d.rounded_rectangle([70, by, 70 + max(16, bw * TL.speed_frac(t)), by + 16], radius=8,
                            fill=(255, 140, 40, int(230 * ha)))

    # layer labels
    for name, _p, t0, t1 in TL.LABELS:
        la = window(t, t0, t1, 0.3)
        if la <= 0 or name not in pr:
            continue
        sx, sy, sz = pr[name]
        if sz <= 0 or not (0.02 < sx < 0.98 and 0.05 < sy < 0.95):
            continue
        px, py = sx * W, sy * H
        if py > 1230:          # anchor inside the caption band: skip
            continue
        lx, ly = min(px + 120, 640), min(py - 60, 1110)
        al = int(255 * la)
        d.line([px, py, lx, ly], fill=(255, 255, 255, al), width=4)
        d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=(255, 255, 255, al))
        sub = {"INNER CORE": "~5,200°C / 9,400°F", "OUTER CORE": "liquid metal"}.get(name)
        pill(d, lx, ly, name, 38, (255, 255, 255, al), (0, 0, 0, int(170 * la)))
        if sub:
            pill(d, lx, ly + 62, sub, 34, YELLOW + (al,), (0, 0, 0, int(170 * la)))

    # "YOU" pointer in wide shots (skipped where it would sit behind the captions)
    ya = max(window(t, 5.0, 8.4, 0.3), window(t, 32.2, 40, 0.3))
    if ya > 0 and "person" in pr:
        px, py = pr["person"][0] * W, pr["person"][1] * H
        if not 1180 < py < 1520:
            tipx = px - 30 + 8 * math.sin(t * 8)
            al = int(255 * ya)
            d.polygon([(tipx, py), (tipx - 34, py - 22), (tipx - 34, py + 22)], fill=YELLOW + (al,))
            d.text((tipx - 44, py), "YOU", font=font(54), fill=YELLOW + (al,), anchor="rm",
                   stroke_width=6, stroke_fill=BLACK + (al,))

    # disclaimer
    da = window(t, 5.5, 9.5, 0.3)
    if da > 0:
        d.text((W / 2, 1580), "*ignoring air resistance and heat (physics only)", font=font(30, False),
               fill=(230, 230, 230, int(220 * da)), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0, int(200 * da)))

    # captions (voiceover script)
    for t0, t1, text in CAPS:
        if t0 <= tc < t1:
            s = ease_out_back((tc - t0) / 0.18)
            caption(img, text, 1340, 76, 0.85 + 0.15 * s)
            break


def punch(t):
    """Little zoom 'punch' on key beats."""
    z = 1.0
    for tb in BEATS.values():
        if tb <= t < tb + 0.35:
            z = max(z, 1 + 0.05 * (1 - (t - tb) / 0.35) ** 2)
    return z


# ---------------------------------------------------------------- audio
def make_audio(path, music_gain=1.0):
    sr = 44100
    n = int(TL.DUR * sr)
    au = np.zeros(n)

    def fade(x, ms=40):
        k = int(sr * ms / 1000)
        x[-k:] *= np.linspace(1, 0, k)   # no click when a note is cut off
        return x

    # music: 120 bpm pulse bass + minor arpeggio
    bpm = 120
    beat = 60 / bpm
    notes = [57, 60, 64, 67, 69, 67, 64, 60]          # A minor arpeggio (MIDI)
    roots = [45, 45, 41, 41, 43, 43, 40, 40]          # A F G E
    def hz(m): return 440 * 2 ** ((m - 69) / 12)
    nb = int(TL.DUR / beat * 2)
    for k in range(nb):
        t0 = k * beat / 2
        bar = int(t0 / (beat * 4)) % len(roots)
        st = np.arange(int(0.25 * sr)) / sr
        f = hz(notes[k % 8] + (12 if bar % 2 else 0) - (roots[0] - roots[bar]) * 0)
        pluck = fade(np.sin(2 * np.pi * f * st) * np.exp(-st * 14) * 0.05)
        i = int(t0 * sr)
        j = min(n, i + len(pluck))
        au[i:j] += pluck[: j - i]
        if k % 2 == 0:
            st2 = np.arange(int(0.35 * sr)) / sr
            fb = hz(roots[bar] - 12)
            bass = fade(np.sin(2 * np.pi * fb * st2) * np.exp(-st2 * 6) * 0.16)
            j = min(n, i + len(bass))
            au[i:j] += bass[: j - i]

    def add(t0, sig):
        i = int(t0 * sr)
        j = min(n, i + len(sig))
        if i < n:
            au[i:j] += sig[: j - i]

    def sweep(d, f0, f1, vol, decay=0.0):
        st = np.arange(int(d * sr)) / sr
        f = f0 + (f1 - f0) * st / d
        return vol * np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-st * decay)

    # boom at the centre + punch hits
    for key, v in (("jump", 0.5), ("center", 0.9), ("crazy", 0.8), ("stop", 0.5)):
        add(BEATS[key], fade(sweep(0.8, 90, 35, v, decay=5)))
    # riser before 'crazy part'
    st = np.arange(int(1.6 * sr)) / sr
    add(BEATS["crazy"] - 1.6, sweep(1.6, 200, 1200, 0.08) * (st / 1.6) ** 2)

    au /= np.max(np.abs(au)) / (0.85 * music_gain)
    pcm = (au * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.stack([pcm, pcm], 1).tobytes())


def main():
    """python3 post.py <frames_dir> <out.mp4> [voiceover_dir]"""
    global CAPS, BEATS, REMAP
    frames, out = sys.argv[1], sys.argv[2]
    vo_dir = sys.argv[3] if len(sys.argv) > 3 else None
    pr = json.load(open(os.path.join(frames, "projections.json")))
    if vo_dir:
        vo = json.load(open(os.path.join(vo_dir, "vo.json")))
        CAPS = [tuple(c) for c in vo["captions"]]
        BEATS = {"jump": 2.4, "center": 15.1,
                 "crazy": next(c[0] for c in CAPS if "CRAZY" in c[2]),
                 "stop": next(c[0] for c in CAPS if c[2].startswith("STOP"))}
        REMAP = REMAP_VO
    wav = out + ".wav"
    make_audio(wav, music_gain=0.45 if vo_dir else 1.0)
    inputs = ["-i", wav]
    if vo_dir:
        # warm 'documentary' voice: low-mid warmth, presence, gentle compression, small room;
        # music ducks under the voice (sidechain), then everything to -14 LUFS
        inputs += ["-i", os.path.join(vo_dir, "vo.wav")]
        audio = ["-filter_complex",
                 "[2:a]aformat=channel_layouts=stereo,highpass=f=70,equalizer=f=170:t=q:w=1.2:g=3,"
                 "equalizer=f=3200:t=q:w=1:g=2,acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=2,"
                 "aecho=0.8:0.7:30|55:0.10|0.06,asplit=2[v1][v2];"
                 "[1:a][v1]sidechaincompress=threshold=0.02:ratio=5:attack=15:release=350[m];"
                 "[m][v2]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
                 "-map", "0:v", "-map", "[a]"]
    else:
        audio = ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    cmd = (["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
            "-r", str(TL.FPS), "-i", "-"] + inputs + audio +
           ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-ar", "44100", "-c:a", "aac", "-b:a", "192k", "-t", str(TL.DUR), "-movflags", "+faststart", out])
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(TL.NFRAMES):
        t = f / TL.FPS
        ts = src_time(t)
        fs = min(TL.NFRAMES - 1, int(round(ts * TL.FPS)))
        src = Image.open(os.path.join(frames, f"f_{fs:04d}.png")).convert("RGB")
        z = punch(t)
        if z > 1.0:
            w2, h2 = src.width / z, src.height / z
            x0, y0 = (src.width - w2) / 2, (src.height - h2) / 2
            src = src.crop((int(x0), int(y0), int(x0 + w2), int(y0 + h2)))
        img = src.resize((W, H), Image.LANCZOS).convert("RGBA")
        overlay(img, ts, pr.get(str(fs), {}), tc=t)
        ff.stdin.write(img.convert("RGB").tobytes())
    ff.stdin.close()
    ff.wait()
    os.remove(wav)
    print("done:", out)


if __name__ == "__main__":
    main()
