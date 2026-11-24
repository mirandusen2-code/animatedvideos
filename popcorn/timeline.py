"""Shot timeline for "This Corn Kernel Explodes Inside Out", derived from the narration timing.

Sets (one Blender scene, far apart). 1 unit = ~2.5 mm (a kernel is ~2 units tall).
  pan:     a hot dark steel pan with kernels; the hero kernel pops (origin).
  section: the hero kernel cut in half: hard shell, starch, a drop of water that turns to steam (at SECTION).
Every shot of the pan set has its own "burst clock" for the hero kernel (burst(t) below).
"""
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = {k: tuple(v) for k, v in TIMING["lines"].items()}
WORDS = TIMING["words"]

FPS = 30
NFRAMES = round((L["loop"][1] + 0.07) * FPS)
DUR = NFRAMES / FPS

SECTION = (1000.0, 0.0, 0.0)


def W(line, word, n=0):
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


T_EXPL = W("hook", "explodes")[0]
T_356 = W("hook", "356")[0]
T_INSIDE = W("water", "inside")[0]
T_DROP = W("water", "drop")[0]
T_SHELL = W("water", "shell")[0]
T_HEAT = W("steam", "heat")[0]
T_STEAM = W("steam", "steam")[0]
T_9 = W("steam", "9")[0]
T_CRACK = W("burst", "cracks")[0]
T_FOAM = W("burst", "foam")[0]
T_40 = W("burst", "40")[0]
T_LEG = W("leg", "leg")[0]
T_FLIPS = W("leg", "flips")[0]
T_POP = W("pop", "pop")[0]
T_ESC = W("pop", "escaping")[0]
T_NOT = W("pop", "not")[0]
T_HEATUP = W("loop", "heat")[0]


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    s = lambda x, y, z: add(SECTION, (x, y, z))
    s1 = 2.3
    s2 = l["water"][0] - 0.05
    s3 = l["steam"][0] - 0.1
    s4 = l["burst"][0] - 0.1
    s5 = l["leg"][0] - 0.1
    s6 = l["pop"][0] - 0.1
    s7 = l["loop"][0] - 0.25
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, set
        # S0 hook: the hero kernel mid-burst, close; the camera eases back as the foam grows
        (0.0, s1, (-2.0, -12.5, 4.2), (-3.2, -20.0, 7.2), (0.4, -0.3, 2.4), (0.6, -0.45, 3.3), 50, 50, "pan"),
        # S1 the whole pan: kernels popping all around (356 F)
        (s1, s2, (1.5, -21.0, 10.0), (-1.0, -18.5, 8.0), (0.5, 2.5, 2.5), (0.5, 2.0, 2.8), 40, 44, "pan"),
        # S2 cut-away: hard shell, starch, a drop of water (3/4 view swinging to face-on, pushing in)
        (s2, s3, s(-3.0, -6.6, 1.6), s(-0.3, -5.2, 0.35), s(0.0, 0.0, 0.1), s(0.0, 0.0, 0.0), 50, 50, "section"),
        # S3 heat: the drop turns to steam, the pressure climbs to 9x (swing to the other side, pull back)
        (s3, s4, s(0.6, -4.8, 0.2), s(2.4, -6.2, 1.4), s(0.0, 0.0, 0.0), s(0.0, 0.0, 0.15), 50, 50, "section"),
        # S4 the shell cracks, the foam puffs out 40x: pull back to the unpopped kernel beside it
        (s4, s5, (0.8, -6.0, 2.2), (-0.8, -21.0, 7.5), (0.1, 0.0, 0.9), (0.5, -0.6, 3.0), 50, 46, "pan"),
        # S5 the leg and the flip: side view at pan level
        (s5, s6, (0.0, -19.0, 5.2), (0.3, -18.5, 5.4), (0.5, 0.0, 5.0), (0.5, 0.0, 5.2), 40, 40, "pan"),
        # S6 the pop: close on the crack, steam jets and the sound ring
        (s6, s7, (1.4, -4.6, 2.4), (0.6, -6.0, 2.8), (0.1, 0.0, 1.0), (0.1, 0.0, 1.3), 50, 50, "pan"),
        # S7 heat it up: the kernel trembles, glows, bursts -> blends into the opening shot
        (s7, DUR, (-1.0, -7.5, 2.4), None, (0.1, 0.0, 0.9), None, 50, 50, "pan"),
    ]


SHOTS = _shots()


def shot_index(t):
    for i, s in enumerate(SHOTS):
        if s[0] <= t < s[1]:
            return i
    return len(SHOTS) - 1


def shot_set(t):
    return SHOTS[shot_index(t)][8]


def env_t(t):
    """Loop clock: the last shot runs at negative time, so it flows straight into frame 0."""
    return t - DUR if shot_index(t) == len(SHOTS) - 1 else t


CAM0_K = 2.0


def cam0(te):
    s0 = SHOTS[0]
    n = 1 - math.exp(-CAM0_K * s0[1])
    if te >= 0:
        f = (1 - math.exp(-CAM0_K * te)) / n
    else:                        # before the seam: C1-smooth, saturating (the exponential would fly off)
        f = (CAM0_K / n) * -0.25 * (1 - math.exp(te / 0.25))
    return lerpv(s0[2], s0[3], f), lerpv(s0[4], s0[5], f), s0[6]


def camera(t):
    i = shot_index(t)
    t0, t1, p0, p1, a0, a1, l0, l1, _set = SHOTS[i]
    x = clamp((t - t0) / (t1 - t0))
    if i == 0:
        return cam0(t)
    if i == len(SHOTS) - 1:
        cp, ct, cl = cam0(env_t(t))
        w = smoother(x / 0.9)
        return lerpv(p0, cp, w), lerpv(a0, ct, w), lerp(l0, cl, w)
    if i == 5:                                     # side view follows the flip a little
        loc, tgt, lens = lerpv(p0, p1, x), lerpv(a0, a1, x), l0
        return loc, tgt, lens
    u = smoother(x) * 0.7 + 0.3 * x
    return lerpv(p0, p1, u), lerpv(a0, a1, u), lerp(l0, l1, u)


# ---------------------------------------------------------------- shared event lists (picture AND sound)
BURST_LEN = 1.15                     # crack -> fully puffed foam (slow motion)
TE_BURST = -0.2                      # the hero burst starts just before frame 0 (loop clock)
FLIP_T0 = None                       # set below


def burst_start(t):
    """Start time of the hero kernel's burst in the shot at time t (None = stays unpopped)."""
    i = shot_index(t)
    if i == 0 or i == len(SHOTS) - 1:
        return TE_BURST + (DUR if i == len(SHOTS) - 1 else 0.0)
    if i == 1:
        return -99.0                 # already popped in the wide shot
    if i == 4:
        return T_FOAM - 0.45
    if i == 5:
        return T_LEG - 0.55
    return None


def burst(t):
    """0 = intact kernel, 1 = fully popped (hero kernel in the pan set)."""
    b0 = burst_start(t)
    if b0 is None:
        return 0.0
    return clamp((t - b0) / BURST_LEN)


def crack(t):
    """0..1 glowing crack lines on the shell before it splits (pressure building)."""
    i = shot_index(t)
    if i == 6:
        return smoother((t - (T_POP - 0.1)) / 0.4)
    b0 = burst_start(t)
    if b0 is None:
        return 0.0
    if i == 4:
        return smoother((t - (T_CRACK - 0.35)) / 0.35)
    if i == 6:
        return smoother((t - (T_POP - 0.1)) / 0.4)
    if i == len(SHOTS) - 1:
        return smoother((t - T_HEATUP) / 0.7)
    return 1.0


def heat(t):
    """0..1 heat glow of the pan and tremble of the kernel."""
    i = shot_index(t)
    if i == len(SHOTS) - 1:
        return smoother((t - SHOTS[i][0]) / 0.6)
    return 1.0 if shot_set(t) == "pan" else 0.0


def tremble(t):
    """Small shake of the hero kernel just before it pops (pressure)."""
    b0 = burst_start(t)
    if b0 is None or b0 < -50:
        return 0.0
    u = b0 - t
    if u < 0 or u > 1.2:
        return 0.0
    return 0.03 * (1 - u / 1.2) ** 1.5


# the flip (S5): the leg pushes on the pan, the kernel jumps and somersaults
FLIP_T0 = T_LEG - 0.55 + 0.38                # leg touches the pan
FLIP_DUR = 0.95
FLIP_H = 2.4


def flip(t):
    """(height offset, rotation in turns) of the hero kernel in S5."""
    if shot_index(t) != 5:
        return 0.0, 0.0
    u = (t - FLIP_T0) / FLIP_DUR
    if u <= 0:
        return 0.0, 0.0
    if u >= 1:
        b = u - 1                           # small bounce after landing
        return 0.25 * abs(math.sin(math.pi * clamp(b / 0.35))) * (1 if b < 0.35 else 0), 1.0
    return FLIP_H * 4 * u * (1 - u), smoother(u)


# other kernels in the pan: (x, y, yaw, pop time in S1). They pop during the wide shot.
def _others():
    import random
    rnd = random.Random(5)
    pts = []
    tries = 0
    while len(pts) < 14 and tries < 4000:
        tries += 1
        x, y = rnd.uniform(-5.0, 5.0), rnd.uniform(-2.0, 9.0)
        if x * x / 22 + (y - 3.5) ** 2 / 34 > 1:
            continue
        if math.hypot(x, y) < 4.6 or math.hypot(x + 1.6, y + 2.8) < 2.0:
            continue
        if any(math.hypot(x - p[0], y - p[1]) < 3.6 for p in pts):
            continue
        pts.append((x, y, rnd.uniform(0, 2 * math.pi)))
    s1, s2 = SHOTS[1][0], SHOTS[1][1]
    out = []
    for k, (x, y, yaw) in enumerate(pts):
        tp = s1 - 0.6 + 2.2 * ((k * 0.618) % 1.0)
        out.append((x, y, yaw, tp))
    return out


OTHERS = _others()


def other_burst(k, t):
    if shot_index(t) == 1:
        return clamp((t - OTHERS[k][3]) / 0.5)
    if shot_index(t) == 4:
        return 0.0
    return 0.0 if shot_index(t) in (0, 7) else 1.0


# section set (S2, S3)
def water_drop(t):
    """Radius factor of the water drop in the section (shrinks as it boils)."""
    return 1.0 - 0.85 * smoother((t - T_STEAM) / 1.4)


def steam(t):
    """0..1 amount of steam inside the section, and the particle speed."""
    x = smoother((t - T_STEAM + 0.15) / 1.0)
    sp = 0.6 + 2.2 * smoother((t - T_9 + 0.4) / 0.8)
    return x, sp


def pressure(t):
    """1 -> 9 (x normal air pressure), reaching 9 on the word 'nine'."""
    if t < T_HEAT:
        return 1.0
    return 1.0 + 8.0 * smoother((t - T_HEAT) / (T_9 + 0.15 - T_HEAT))


def section_heat(t):
    return smoother((t - T_HEAT + 0.1) / 0.6)


def bulge(t):
    """Outward bulge of the section's shell under pressure."""
    p = (pressure(t) - 1) / 8
    return 0.05 * p * (0.8 + 0.2 * math.sin(t * 14))


# S6 the pop: steam jets and the sound ring
def jets(t):
    """0..1 steam jets out of the crack (S6)."""
    if shot_index(t) != 6:
        return 0.0
    return smoother((t - T_ESC + 0.2) / 0.25) * (1 - 0.6 * smoother((t - T_ESC - 1.2) / 0.8))


def sound_rings(t):
    """Ages of the expanding 'pop' rings (S6)."""
    if shot_index(t) != 6:
        return []
    out = []
    for k in range(4):
        a = t - (T_ESC - 0.05 + 0.32 * k)
        if 0 <= a < 1.1:
            out.append(a)
    return out
