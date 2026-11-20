"""Shot timeline for the immortal jellyfish video, derived from the real narration timing (vo/timing.json)."""
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = {k: tuple(v) for k, v in TIMING["lines"].items()}
WORDS = TIMING["words"]

FPS = 30
NFRAMES = round((L["loop"][1] + 0.05) * FPS)  # loop restarts right after the last word
DUR = NFRAMES / FPS                            # exact loop period: picture, sound and motion share it

OCEAN = (0.0, 0.0, 0.0)
CELLS = (500.0, 0.0, 0.0)


def W(line, word, n=0):
    """(start, end) of the n-th caption word in `line` containing `word` (case-insensitive)."""
    a, b = L[line]
    k = 0
    for s, e, w, *_ in WORDS:
        if a - 0.01 <= s <= b + 0.01 and word.lower() in re.sub(r"[^a-z0-9]", "", w.lower()):
            if k == n:
                return s, e
            k += 1
    raise KeyError((line, word, n))


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smoother(x):
    x = clamp(x)
    return x * x * x * (x * (6 * x - 15) + 10)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def lerp(a, b, x):
    return a + (b - a) * x


def lerpv(a, b, x):
    return tuple(lerp(p, q, x) for p, q in zip(a, b))


def add(a, b):
    return tuple(p + q for p, q in zip(a, b))


# ---------------------------------------------------------------- key moments (all on spoken words)
T_OLD = W("old", "old")[0]
T_HURT = W("old", "hurt")[0]
T_DIE = W("old", "die")[0]
T_MELT = W("melt", "melts")[0]
T_SINK = W("melt", "sinks")[0]
T_FLOOR = W("melt", "floor")[1]
T_TURNS = W("baby", "turns")[0]
T_BABY = W("baby", "baby")[0]
T_CELLS = L["cells"][0]
T_BECOME = W("cells", "become")[0]
T_NEW = W("cells", "new")[0]
T_GROWS = W("cells", "grows")[0]
T_RELEASE = W("cells", "again")[0]
T_AGAIN = [W("again", "again", k)[0] for k in range(3)]
T_EATS = W("loop", "eats")[0]

HERO = (0.0, 0.0, 2.0)             # where the adult floats
FLOOR_SPOT = (0.15, 0.25, 0.0)     # where the blob lands and the polyp grows
POLYP_H = 0.62                     # polyp height


def pulse(t):
    """Bell contraction 0..1 (swim stroke). Strokes stop when it 'should die'."""
    if t > T_DIE + 0.6:
        return 0.0
    per = 1.05 if t < T_OLD else 1.05 + 0.6 * smoother((t - T_OLD) / 1.5)
    ph = ((t + 0.95) / per) % 1.0                      # a stroke starts right at frame 0
    v = math.sin(math.pi * clamp(ph / 0.35)) if ph < 0.35 else 0.0
    return v * (1 - 0.6 * smoother((t - T_OLD) / 1.8))


def age(t):
    """0 = young and vivid, 1 = old, pale and ragged."""
    return smoother((t - T_OLD + 0.1) / 1.6)


def hurt(t):
    """A tentacle chunk is torn on 'hurt' (0..1)."""
    return smoother((t - T_HURT) / 0.25)


def melt(t):
    """Bell + tentacles collapse into a blob (0..1)."""
    return smoother((t - T_MELT + 0.15) / 1.6)


def sink(t):
    """Blob drops from the water column to the floor (0..1), with a soft landing."""
    return smoother((t - T_SINK + 0.2) / (T_FLOOR - T_SINK + 0.15))


def stolon(t):
    return smoother((t - T_TURNS + 0.1) / 0.8)


def polyp(t):
    return smoother((t - T_TURNS - 0.2) / 1.0)


def crown(t):
    """Polyp tentacle crown opens on 'baby'."""
    return smoother((t - T_BABY) / 0.4)


def renew(t):
    """Cell renewal wave progress (0..1)."""
    return clamp((t - T_BECOME + 0.1) / (T_NEW - T_BECOME + 0.5))


def bud(t):
    """New medusa grows on the polyp (0..1)."""
    return smoother((t - T_GROWS + 0.65) / 1.0)


def released(t):
    return t >= T_RELEASE


def swim_up(t):
    """Seconds since the new jellyfish broke free."""
    return t - T_RELEASE


def cycle(t):
    """Fast rejuvenation cycles on each 'again': returns (shrink 0..1, glow 0..1, life number)."""
    s, g, n = 0.0, 0.0, 1
    for k, t0 in enumerate(T_AGAIN):
        u = t - t0 + 0.12
        if u >= 0:
            n = k + 2
        s = max(s, math.exp(-((u - 0.12) / 0.12) ** 2) if u > -0.3 else 0.0)
        g = max(g, math.exp(-((u - 0.22) / 0.14) ** 2))
    return s, g, n


FISH_P0 = (2.7, 2.1, 2.3)       # enters behind, right
FISH_PA = (0.85, 0.75, 1.98)    # lunges at the jellyfish on "eats"
FISH_P2 = (3.4, 0.9, 2.35)      # gives up and darts out of frame before the loop restarts


def fish_pos(t):
    ta, tb = L["loop"][0] - 0.12, T_EATS + 0.12
    if t <= tb:
        u = smoother((t - ta) / (tb - ta)) * 0.7 + 0.3 * clamp((t - ta) / (tb - ta))
        return lerpv(FISH_P0, FISH_PA, u)
    u = clamp((t - tb) / (DUR - 0.12 - tb))
    u = u * u * (3 - 2 * u)
    bend = (0.0, -0.35 * math.sin(math.pi * u), 0.0)
    return add(lerpv(FISH_PA, FISH_P2, u), bend)


def fish_mouth(t):
    return math.exp(-((t - T_EATS - 0.12) / 0.22) ** 2)


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    o = lambda x, y, z: add(OCEAN, (x, y, z))
    c = lambda x, y, z: add(CELLS, (x, y, z))
    hx, hy, hz = HERO
    fx, fy, _ = FLOOR_SPOT
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, fstop, focus, set
        (0.0, l["old"][0] - 0.12, o(0.35, -2.6, 1.55), o(0.25, -2.05, 1.65), o(0, 0, 1.92), o(0, 0, 1.92), 40, 40, 2.8, "hero", "ocean"),
        (l["old"][0] - 0.12, l["melt"][0] - 0.08, o(-1.6, -2.7, 2.6), o(-1.2, -2.5, 2.35), o(0, 0, 1.85), o(0, 0, 1.85), 42, 42, 3.2, "hero", "ocean"),
        (l["melt"][0] - 0.08, T_SINK - 0.2, o(0.9, -1.8, 1.7), o(0.7, -1.5, 1.75), o(0, 0, 1.8), o(0, 0, 1.75), 45, 45, 3.2, "blob", "ocean"),
        (T_SINK - 0.2, l["baby"][0] - 0.03, o(1.2, -2.4, 1.4), o(0.9, -1.6, 0.3), o(0.05, 0.1, 1.3), o(fx, fy, 0.12), 35, 35, 3.2, "blob", "ocean"),
        (l["baby"][0] - 0.03, T_CELLS - 0.06, o(fx + 0.55, fy - 1.5, 0.38), o(fx + 0.42, fy - 1.3, 0.46), o(fx, fy, 0.34), o(fx, fy, 0.44), 40, 40, 3.5, "polyp", "ocean"),
        (T_CELLS - 0.06, T_GROWS - 0.42, c(0.0, -3.2, 0.25), c(0.0, -2.6, 0.15), c(0, 0, 0), c(0, 0, 0), 45, 45, 11, "cells", "cells"),
        (T_GROWS - 0.42, l["again"][0] - 0.1, o(fx - 0.6, fy - 1.3, 0.55), o(fx - 0.8, fy - 2.6, 1.6), o(fx, fy, 0.62), o(fx, fy, 1.45), 38, 38, 3.5, "baby", "ocean"),
        (l["again"][0] - 0.1, l["loop"][0] - 0.12, o(-0.6, -3.0, 1.75), o(-0.45, -2.7, 1.85), o(0, 0, 1.9), o(0, 0, 1.92), 40, 40, 3.2, "hero", "ocean"),
        # last shot glides back into the exact opening framing: the loop restarts as a match cut
        (l["loop"][0] - 0.12, DUR, o(0.95, -3.4, 1.62), o(0.35, -2.6, 1.55), o(0.45, 0.45, 1.88), o(0, 0, 1.92), 34, 40, 3.2, "hero", "ocean"),
    ]


SHOTS = _shots()


def shot_index(t):
    for i, s in enumerate(SHOTS):
        if s[0] <= t < s[1]:
            return i
    return len(SHOTS) - 1


def shot_set(t):
    return SHOTS[shot_index(t)][10]


def drift(t, amp):
    return (amp * math.sin(t * 0.9) + amp * 0.5 * math.sin(t * 2.3), amp * 0.6 * math.sin(t * 1.3 + 1),
            amp * math.sin(t * 1.1 + 2) + amp * 0.4 * math.sin(t * 2.9))


def env_t(t):
    """Clock for everything that moves on its own (swimming, tentacles, snow, caustics, weeds).
    In the last shot it runs from -1.6 s up to 0, so the final frame flows straight into frame 0."""
    return t - DUR if shot_index(t) == len(SHOTS) - 1 else t


def camera(t):
    i = shot_index(t)
    t0, t1, p0, p1, a0, a1, l0, l1, fstop, focus, _set = SHOTS[i]
    x = clamp((t - t0) / (t1 - t0))
    if i == len(SHOTS) - 1:
        # ease in, then arrive with the same slow speed the opening push-in starts with
        h0 = SHOTS[0]
        v0 = 0.15 / (h0[1] - h0[0])                         # opening shot's start speed (fraction / s)
        d_end = math.dist(p0, p1)
        k = clamp(v0 * math.dist(h0[2], h0[3]) / max(d_end, 1e-6) * (t1 - t0), 0.0, 0.9)
        u = (1 - k) * smoother(x) + k * x
    else:
        u = smoother(x) * 0.85 + 0.15 * x
    p = lerpv(p0, p1, u)
    p = tuple(a + b for a, b in zip(p, drift(env_t(t), 0.008)))
    return p, lerpv(a0, a1, u), lerp(l0, l1, u), fstop, focus
