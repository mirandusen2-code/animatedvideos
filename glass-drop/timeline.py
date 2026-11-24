"""Shot timeline for "This Glass Drop Just Exploded", derived from the narration timing.

Sets (one Blender scene, far apart). 1 unit = ~5 mm (the drop's head radius is 1).
  drop:    a Prince Rupert's drop hanging tail-up from a clamp in a dark polariscope, side cutters at the tail.
  water:   a beaker of cold water; a glowing gob of molten glass drips in (at WATER).
  section: the drop cut in half, showing the cool squeezing skin and the hot inside (at SECTION).
  hammer:  the drop lying on a steel anvil, hit by a hammer (at HAMMER).
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

WATER = (500.0, 0.0, 0.0)
SECTION = (1000.0, 0.0, 0.0)
HAMMER = (1500.0, 0.0, 0.0)
Z_SNIP = 6.0                     # where the cutters snip the tail (drop-local height; head centre at 0)
Z_TOP = 8.3                      # tail tip, held by the clamp


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


def ease_in(x):
    x = clamp(x)
    return x * x * x


def lerp(a, b, x):
    return a + (b - a) * x


def lerpv(a, b, x):
    return tuple(lerp(p, q, x) for p, q in zip(a, b))


def add(a, b):
    return tuple(p + q for p, q in zip(a, b))



def radius(z):
    """Profile of the drop (local units, head centre at z=0, tail up)."""
    if z <= 0:
        return math.sqrt(max(0.0, 1 - z * z))
    return max(0.03, 1.0 / (1.0 + (z / 0.9) ** 1.6))


def bend(z):
    """Sideways curl of the thin tail (x offset)."""
    return 0.28 * max(0.0, z / Z_TOP) ** 2.2


T_EXPL = W("hook", "exploded")[0]
T_3000 = W("hook", "3000")[0]
T_PRINCE = W("name", "prince")[0]
T_HOT = W("name", "hot")[0]
T_WATER = W("name", "cold")[0]
T_OUTSIDE = W("skin", "outside")[0]
T_SQ = W("skin", "squeezes")[0]
T_50 = W("skin", "50")[0]
T_HAMMER = W("hammer", "hammer")[0]
T_NOTHING = W("hammer", "nothing")[0]
T_TAIL = W("tail", "tail")[0]
T_WEAK = W("tail", "weak")[0]
T_SNIP = W("loop", "snip")[0] + 0.04
T_HIT = T_HAMMER + 0.08


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    w = lambda x, y, z: add(WATER, (x, y, z))
    s = lambda x, y, z: add(SECTION, (x, y, z))
    h = lambda x, y, z: add(HAMMER, (x, y, z))
    s1 = l["name"][0] - 0.1
    s2 = l["skin"][0] - 0.1
    s3 = l["hammer"][0] - 0.1
    s4 = l["tail"][0] - 0.1
    s5 = l["loop"][0] - 0.25
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, set
        # S0 hook: the head is bursting into glittering powder, the crack front has just raced down the tail
        (0.0, s1, (0.35, -6.0, 0.45), (1.3, -8.8, 1.5), (0.0, 0.0, 0.35), (0.0, 0.0, 1.1), 50, 50, "drop"),
        # S1 hot glass dripped into cold water
        (s1, s2, w(0.9, -13.5, 5.2), w(0.3, -11.8, 4.2), w(0.0, 0.0, 4.4), w(0.0, 0.0, 3.4), 38, 42, "water"),
        # S2 the cut drop: the skin cools first and squeezes (3/4 view swinging to face-on, pushing in)
        (s2, s3, s(5.2, -8.6, 3.4), s(0.35, -5.6, 0.5), s(0.0, 0.0, 2.2), s(0.0, 0.0, 0.25), 50, 50, "section"),
        # S3 the hammer hits the head, nothing happens
        (s3, s4, h(0.5, -11.0, 3.0), h(-0.1, -9.8, 2.6), h(0.45, 0.0, 1.95), h(0.25, 0.0, 1.65), 50, 50, "hammer"),
        # S4 the tail is its weak spot: the whole drop, tilting up to the tail
        (s4, s5, (0.2, -15.5, 3.8), (0.9, -8.6, 5.6), (0.0, 0.0, 3.6), (0.1, 0.0, 5.7), 50, 50, "drop"),
        # S5 snip: the cutters close, the crack races down, the camera follows it into the opening shot
        (s5, DUR, (0.9, -8.0, 5.8), None, (0.1, 0.0, 5.7), None, 50, 50, "drop"),
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


CAM0_K = 0.8


def cam0(te):
    s0 = SHOTS[0]
    f = (1 - math.exp(-CAM0_K * te)) / (1 - math.exp(-CAM0_K * s0[1]))
    return lerpv(s0[2], s0[3], f), lerpv(s0[4], s0[5], f), s0[6]


def camera(t):
    i = shot_index(t)
    t0, t1, p0, p1, a0, a1, l0, l1, _set = SHOTS[i]
    x = clamp((t - t0) / (t1 - t0))
    if i == 0:
        return cam0(t)
    if i == len(SHOTS) - 1:
        cp, ct, cl = cam0(env_t(t))
        w = smoother(x / 0.92)
        wt = smoother(x / 0.75)                       # the aim follows the crack down a little ahead
        return lerpv(p0, cp, w), lerpv(a0, ct, wt), lerp(l0, cl, w)
    u = smoother(x) * 0.7 + 0.3 * x
    return lerpv(p0, p1, u), lerpv(a0, a1, u), lerp(l0, l1, u)


# ---------------------------------------------------------------- shared event lists (picture AND sound use these)
TE_SNIP = T_SNIP - DUR                 # the snip, on the loop clock (negative)
TE_HEAD = -0.12                        # the crack front reaches the head (just before frame 0)
TE_GONE = 2.3                         # the last of the head has burst
Z_HEAD = 0.95


def front_z(t):
    """Height of the crack front in the drop set (above Z_SNIP = intact, nothing broken)."""
    i = shot_index(t)
    if i not in (0, len(SHOTS) - 1):
        return 99.0
    te = env_t(t)
    if te < TE_SNIP:
        return 99.0
    if te < TE_HEAD:                   # racing down the tail
        x = (te - TE_SNIP) / (TE_HEAD - TE_SNIP)
        return lerp(Z_SNIP, Z_HEAD, x ** 1.15)
    x = clamp((te - TE_HEAD) / (TE_GONE - TE_HEAD))
    return lerp(Z_HEAD, -1.08, x ** 0.9)


def front_time(z):
    """Loop-clock time when the front passes height z (inverse of front_z)."""
    if z >= Z_HEAD:
        x = ((Z_SNIP - z) / (Z_SNIP - Z_HEAD)) ** (1 / 1.15)
        return TE_SNIP + x * (TE_HEAD - TE_SNIP)
    y = (Z_HEAD - z) / (Z_HEAD + 1.08)
    x = clamp(y) ** (1 / 0.9)
    return TE_HEAD + x * (TE_GONE - TE_HEAD)


def cutter_close(t):
    """0 = open, 1 = closed on the tail."""
    i = shot_index(t)
    if i == 4:
        return 0.0
    if i == len(SHOTS) - 1:
        return smoother((t - T_SNIP + 0.12) / 0.12)
    return 1.0


def cutter_in(t):
    """0 = cutters out of frame (right), 1 = at the tail."""
    i = shot_index(t)
    if i == 4:
        return smoother((t - T_TAIL) / 0.9)
    if i == len(SHOTS) - 1:
        return 1.0 - smoother((t - T_SNIP - 0.06) / 0.22)   # snip, then pull away before the camera dives
    if i == 0:
        return 1.0
    return 0.0


def tail_glow(t):
    """Red warning glow on the thin tail (S4)."""
    if shot_index(t) == 4:
        x = t - T_WEAK + 0.15
        return smoother(x / 0.3) * (0.75 + 0.25 * math.sin(max(0.0, x) * 9.0))
    return 0.0


def drip_z(t):
    """Height of the molten gob's head centre in the water set (surface at 4.4)."""
    s0 = SHOTS[1][0]
    if t < T_WATER:
        x = clamp((t - s0 + 0.35) / (T_WATER - s0 + 0.35))
        return lerp(10.2, 4.4, x * x)
    return 4.4 - 2.3 * (1 - math.exp(-(t - T_WATER) / 0.6))


def glass_heat(t):
    """1 = glowing molten glass, 0 = cooled (water set)."""
    return 1.0 if t < T_WATER else 0.25 + 0.75 * math.exp(-(t - T_WATER) / 1.1)


def skin(t):
    """Thickness (fraction of the radius) of the cooled, squeezing skin in the section."""
    return 0.3 * smoother((t - T_OUTSIDE + 0.1) / (T_SQ - T_OUTSIDE + 0.1))


def squeeze(t):
    """0..1 arrows pushing in, pulsing from 'squeezes' on."""
    x = t - T_SQ + 0.1
    if x < 0:
        return 0.0, 0.0
    return smoother(x / 0.35), 0.5 + 0.5 * math.cos(2 * math.pi * x / 0.8)


def squeeze_pulses():
    out, tp = [], T_SQ - 0.1
    while tp < SHOTS[3][0] - 0.2:
        out.append(tp)
        tp += 0.8
    return out


def hammer_angle(t):
    """Hammer angle in degrees (0 = hitting the head). Kept low enough that the head never leaves the frame."""
    if t < T_HIT:
        hold = 20 + 5 * smoother(clamp((t - SHOTS[3][0]) / 0.9)) + 0.8 * math.sin(4.0 * (t - SHOTS[3][0]))
        x = clamp((t - (T_HIT - 0.3)) / 0.3)
        return lerp(hold, 0.0, x ** 2.2)
    u = t - T_HIT
    return 2 * smoother(u / 0.9) + 6 * math.sin(math.pi * clamp(u / 0.45))


def flash(t):
    """Photoelastic flash of the drop on the hammer impact."""
    u = t - T_HIT
    return 0.0 if u < 0 else math.exp(-u / 0.35)
