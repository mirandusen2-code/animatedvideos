"""Shot timeline for "Scientists Blast a Fuel Pellet With 192 Lasers", derived from the narration timing.

Sets live far apart in one world; each shot uses one (see SET_OF). The implosion runs on its own clock
(imp_clock): the loop shot runs at negative time and flows straight into frame 0.
Picture and sound read the same event functions below.
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


def lerp(a, b, x):
    return a + (b - a) * x


def lerpv(a, b, x):
    return tuple(lerp(p, q, x) for p, q in zip(a, b))


def add(*v):
    return tuple(sum(c) for c in zip(*v))


def norm(a):
    n = math.sqrt(sum(c * c for c in a))
    return tuple(c / n for c in a)


# ---------------------------------------------------------------- set origins
CAP_O = (0.0, 0.0, 0.0)
CH_O = (5000.0, 0.0, 0.0)
SUN_O = (0.0, 6000.0, 0.0)
DROP_O = (0.0, 0.0, -6000.0)
PEP_O = (-5000.0, 0.0, 0.0)
SUN_BODY = (60.0, 520.0, 60.0)
SUN_RAD = 300.0
NEUTRON_DIR = norm((0.45, -1.0, 0.25))

# ---------------------------------------------------------------- word times
T_BLAST = W("hook", "blast")
T_PELLET = W("hook", "pellet")
T_192 = W("hook", "192")
T_LASERS = W("hook", "lasers")
T_WHY = W("why", "why")
T_STAR = W("why", "star")
T_EARTH = W("why", "earth")
T_FUSION = W("sun", "fusion")
T_SUN = W("sun", "sun")
T_NOCARB = W("sun", "no")
T_CARBON = W("sun", "carbon")
T_FUEL = W("sun", "fuel")
T_SEA = W("sun", "seawater")
T_CLASERS = W("crush", "lasers")
T_CRUSH = W("crush", "crush")
T_SMALLER = W("crush", "smaller")
T_PEPPER = W("crush", "peppercorn")
T_CORE = W("hot", "core")
T_HOTTER = W("hot", "hotter")
T_CENTER = W("hot", "center")
T_HSUN = W("hot", "sun")
T_LAST = W("record", "last")
T_SHOT = W("record", "shot")
T_4X = W("record", "4")
T_ENERGY = W("record", "energy")
T_REAL = W("twist", "real")
T_PLANT = W("twist", "plant")
T_YEARS = W("twist", "years")
T_THATS = W("loop", "that")
T_OVER = W("loop", "over")


def _shots():
    l = L
    s1 = W("hook", "with")[0] - 0.05
    s2 = l["sun"][0] - 0.1
    s3 = T_NOCARB[0] - 0.08
    s4 = l["crush"][0] - 0.1
    s5 = T_SMALLER[0] - 0.05
    s6 = l["hot"][0] - 0.1
    s7 = l["record"][0] - 0.1
    s8 = l["twist"][0] - 0.1
    s9 = l["loop"][0] - 0.25
    C, H, S, D, P = CAP_O, CH_O, SUN_O, DROP_O, PEP_O
    return [
        # t0, t1, set, loc0, loc1, target0, target1, lens
        (0.0, s1, "cap", add(C, (1.2, -4.6, 1.3)), add(C, (1.9, -7.6, 2.1)), C, C, 30),            # S0 hook
        (s1, s2, "chamber", add(H, (-8.0, -33.0, 5.0)), add(H, (-12.0, -45.0, 9.0)), H, H, 16),     # S1 192 beams, star
        (s2, s3, "sun", add(S, (-1.5, -12.0, 1.5)), add(S, (1.0, -20.0, 3.0)), add(S, (0, 0, 0.3)),
         add(S, (0.0, 0.0, 1.5)), 30),                                                             # S2 fusion in the Sun
        (s3, s4, "drop", add(D, (-4.0, -29.0, 4.0)), add(D, (4.0, -27.0, 2.0)), D, D, 42),          # S3 seawater
        (s4, s5, "cap", add(C, (-2.0, -22.0, 6.0)), add(C, (1.5, -17.5, 4.0)), C, C, 35),           # S4 lasers crush
        (s5, s6, "pepper", add(P, (0.0, -16.0, 8.0)), add(P, (0.6, -13.5, 6.4)), add(P, (0.4, 0, 1.6)),
         add(P, (0.5, 0, 1.8)), 35),                                                               # S5 peppercorn
        (s6, s7, "cap", add(C, (0.9, -3.4, 1.0)), add(C, (0.4, -2.4, 0.6)), C, C, 50),              # S6 core heats
        (s7, s8, "cap", add(C, (1.0, -12.0, 3.0)), add(C, (2.0, -19.0, 5.0)), C, C, 30),            # S7 burn, 4x
        (s8, s9, "chamber", add(H, (6.0, -30.0, -4.0)), add(H, (10.0, -43.0, -7.0)), H, H, 20),     # S8 years away
        (s9, DUR, "cap", None, None, None, None, 30),                                               # S9 loop
    ]


SHOTS = _shots()
SET_OF = [s[2] for s in SHOTS]


def shot_index(t):
    for i, s in enumerate(SHOTS):
        if s[0] <= t < s[1]:
            return i
    return len(SHOTS) - 1


# ---------------------------------------------------------------- implosion clock (cap set)
def imp_clock(t):
    i = shot_index(t)
    s = SHOTS
    if i == 0:
        return t
    if i == 9:
        return t - DUR
    if i == 4:
        return t - (T_CRUSH[0] + 0.05)
    if i == 6:
        return 0.9 + (t - s[6][0]) * 0.9
    if i == 7:
        return 0.9 + (s[7][0] - s[6][0]) * 0.9 + (t - s[7][0]) * 0.6
    return None


def capsule_r(te):
    return 1.0 - 0.8 * smoother((te + 0.35) / 2.6) if te > -0.35 else 1.0


def compression(te):
    return smoother((te - 0.6) / 1.8)


def cap_beam(t):
    te = imp_clock(t)
    if te is None or shot_index(t) in (6, 7):
        return 0.0
    return smoother((te + 1.2) / 0.15) * (1 - smoother((te - 0.6) / 0.4))


def wall_glow(t):
    te = imp_clock(t)
    if te is None:
        return 0.0
    return smoother((te + 1.0) / 0.7) * (1 - 0.55 * smoother((te - 1.2) / 1.5))


def burn_age(t):
    if shot_index(t) != 7:
        return None
    return t - (T_SHOT[1] + 0.02)


def shards_on(t):
    return shot_index(t) not in (6, 7)


# ---------------------------------------------------------------- chamber
def chamber_beams(t):
    if shot_index(t) != 1:
        return 0.0, 0.0
    t0 = T_192[0] - 0.1
    if t < t0:
        return 0.0, 0.0
    return smoother((t - t0) / 0.35), 1 - smoother((t - T_STAR[0]) / 0.3)


def star(t):
    i = shot_index(t)
    if i == 1:
        ta = T_192[0] + 0.25
        if t < ta:
            return 0.0, 0.0
        a = t - ta
        big = smoother((t - T_STAR[0] + 0.1) / 0.5)
        r = lerp(0.9 + 0.3 * math.exp(-a / 0.3), 5.0, big)
        br = max(0.9 * math.exp(-a / 0.5) + 0.3, big)
        return r, br
    if i == 8:
        x = smoother((t - T_YEARS[0] + 0.1) / 0.7)
        flick = 1 - 0.12 * (math.sin(t * 37) * math.sin(t * 23)) * smoother((t - T_REAL[0]) / 0.3)
        return 5.0 * (1 - 0.7 * x), (1 - x) * flick
    return 0.0, 0.0


# ---------------------------------------------------------------- sun / drop
def fuse_age(t):
    if shot_index(t) != 2:
        return None
    return t - (T_FUSION[1] + 0.05)


def deut_glow(t):
    if shot_index(t) != 3:
        return 0.0
    return smoother((t - T_SEA[0] + 0.05) / 0.3)


# ---------------------------------------------------------------- camera
CAM0_K = 1.4


def cam0(te):
    s0 = SHOTS[0]
    n = 1 - math.exp(-CAM0_K * s0[1])
    if te >= 0:
        f = (1 - math.exp(-CAM0_K * te)) / n
    else:                                # bounded, C1-smooth extension before the seam
        f = (CAM0_K / n) * -0.3 * (1 - math.exp(te / 0.3))
    return lerpv(s0[3], s0[4], f), lerpv(s0[5], s0[6], f), s0[7]


def camera(t):
    i = shot_index(t)
    t0, t1, _s, p0, p1, a0, a1, lens = SHOTS[i]
    if i == 0:
        return cam0(t)
    if i == 9:
        return cam0(t - DUR)
    x = clamp((t - t0) / (t1 - t0))
    u = smoother(x) * 0.6 + 0.4 * x
    return lerpv(p0, p1, u), lerpv(a0, a1, u), lens


def shake(t):
    a = burn_age(t)
    if a is None or a < 0:
        return 0.0
    return 0.12 * math.exp(-a / 0.3)


def sun_nuclei(t):
    """Positions (relative to SUN_O) of the deuterium, tritium, helium nuclei and the free neutron."""
    a = fuse_age(t)
    if a is None:
        a = -3.0
    if a < 0:
        x = 1.15 + 3.0 * (-a) + 1.0 * a * a
        return {"D": (-x, 0.0, 0.25 * a), "T": (x * 1.05, 0.0, -0.2 * a), "He": None, "n": None, "age": a}
    return {"D": None, "T": None, "He": (-1.2 * a, 0.0, -0.4 * a),
            "n": tuple(c * (1.5 + 14.0 * a) for c in NEUTRON_DIR), "age": a}
