"""Shot timeline for "This Diamond Is Burning Into Thin Air", derived from the narration timing.

Sets (one Blender scene, far apart):
  fire:   a brilliant-cut diamond in a ceramic dish on dark slate, an oxygen torch, a lump of charcoal.
          1 unit = ~3 mm (the diamond's girdle radius is 1).
  atoms:  the diamond crystal lattice at atom scale (1 unit = one unit cell), at ATOMS.
  ring:   a gold ring with the same diamond on velvet, at RING.
  pencil: a pencil drawing on white paper, at PENCIL.
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

ATOMS = (500.0, 0.0, 0.0)
RING = (1000.0, 0.0, 0.0)
PENCIL = (1500.0, 0.0, 0.0)
GIRDLE_Z = 0.95                  # height of the diamond's girdle above the slate in the dish


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


T_FIRE = W("hook", "fire")[0]
T_THIN = W("hook", "thin")[0]
T_PURE = W("carbon", "pure")[0]
T_CHAR = W("carbon", "charcoal")[0]
T_HEAT = L["heat"][0]
T_1500 = W("heat", "1500")[0]
T_OXY = W("heat", "oxygen")[0]
T_BURNS = W("heat", "burns")[0]
T_ATOM = W("gas", "atom")[0]
T_CO2 = W("gas", "carbon")[0]
T_BREATHE = W("gas", "breathe")[0]
T_RING = W("ring", "ring")[0]
T_PENCIL = W("ring", "pencil")[0]
T_SLOWLY = W("slow", "slowly")[0]
T_FOREVER = W("loop", "forever")[0]
T_LOOK = W("loop", "look")[0]


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    a = lambda x, y, z: add(ATOMS, (x, y, z))
    r = lambda x, y, z: add(RING, (x, y, z))
    p = lambda x, y, z: add(PENCIL, (x, y, z))
    s1 = l["carbon"][0] - 0.08
    s2 = T_CHAR - 0.3
    s3 = l["heat"][0] - 0.08
    s4 = l["gas"][0] - 0.1
    s5 = l["ring"][0] - 0.1
    s6 = T_PENCIL - 0.25
    s7 = T_SLOWLY - 0.2
    s8 = l["loop"][0] - 0.1
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, set
        # S0 hook: the diamond is already white-hot, sparks flying; the camera rises with the heat ("thin air")
        (0.0, s1, (0.9, -5.4, 1.5), (2.4, -4.9, 2.4), (0.0, 0.0, 0.85), (0.0, 0.0, 1.35), 50, 50, "fire"),
        # S1 pure carbon: flying through the crystal lattice
        (s1, s2, a(-2.2, -9.5, 3.4), a(0.4, -6.2, 2.6), a(0.0, 0.0, 1.9), a(0.6, 0.0, 2.0), 30, 30, "atoms"),
        # S2 just like charcoal: the cold diamond next to a lump of charcoal
        (s2, s3, (1.0, -10.5, 2.9), (1.5, -9.6, 2.6), (1.35, 0.0, 0.8), (1.4, 0.0, 0.8), 38, 38, "fire"),
        # S3 heat it: the oxygen torch heats the diamond until it bursts into flame
        (s3, s4, (-1.2, -6.4, 1.1), (0.4, -5.0, 1.5), (0.0, 0.0, 0.9), (0.0, 0.0, 1.0), 50, 50, "fire"),
        # S4 every atom flies off as CO2: the hot crystal surface sheds molecules
        (s4, s5, a(-3.1, -7.6, 7.0), a(-2.0, -7.0, 8.2), a(0.0, 0.0, 4.0), a(0.0, 0.0, 5.2), 32, 32, "atoms"),
        # S5 even in a ring: a sparkling diamond ring on velvet
        (s5, s6, r(0.0, -6.0, 3.4), r(1.4, -4.6, 2.9), r(0.0, 0.0, 1.55), r(0.0, 0.0, 1.75), 50, 50, "ring"),
        # S6 pencil lead: a pencil drawing a graphite line
        (s6, s7, p(-1.4, -4.3, 1.7), p(0.7, -4.1, 1.5), p(-0.8, 0.1, 0.0), p(1.3, 0.1, 0.0), 50, 50, "pencil"),
        # S7 way too slowly: a time-lapse of the ring, a million years of days
        (s7, s8, r(2.4, -6.6, 4.2), r(1.4, -6.0, 3.6), r(0.0, 0.0, 1.2), r(0.0, 0.0, 1.3), 50, 50, "ring"),
        # S8 aren't forever. Look: the torch heats the diamond again and the camera glides into the opening shot
        (s8, DUR, (1.6, -7.6, 2.6), None, (0.0, 0.0, 0.9), None, 50, 50, "fire"),
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


CAM0_K = 0.9


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
        w = smoother(x / 0.9)
        return lerpv(p0, cp, w), lerpv(a0, ct, w), lerp(l0, cl, w)
    u = smoother(x) * 0.7 + 0.3 * x
    return lerpv(p0, p1, u), lerpv(a0, a1, u), lerp(l0, l1, u)


# ---------------------------------------------------------------- the diamond's state
def heat(t):
    """0 = cold clear diamond, 1 = white-hot and burning."""
    i = shot_index(t)
    if i == 0:
        return 1.0
    if i == 3:
        if t >= T_BURNS - 0.04:
            return 1.0
        return 0.78 * smoother((t - T_1500 + 0.35) / (T_BURNS - T_1500 + 0.2))
    if i == len(SHOTS) - 1:
        return smoother((t - T_FOREVER + 0.2) / (DUR - T_FOREVER + 0.15)) ** 1.4
    return 0.0


def torch(t):
    """0..1: the oxygen torch flame."""
    i = shot_index(t)
    if i == 0:
        return 1.0
    if i == 3:
        return smoother((t - SHOTS[3][0] - 0.1) / 0.3)
    if i == len(SHOTS) - 1:
        return smoother((t - SHOTS[i][0] - 0.25) / 0.35)
    return 0.0


def diamond_scale(t):
    """The diamond shrinks a little as it burns away in the hook (back to full size at the loop point)."""
    if shot_index(t) == 0:
        return 1.0 - 0.10 * smoother(t / SHOTS[0][1])
    return 1.0
