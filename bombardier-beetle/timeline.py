"""Shot timeline for the bombardier beetle video, derived from the real narration timing (vo/timing.json)."""
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = {k: tuple(v) for k, v in TIMING["lines"].items()}
WORDS = TIMING["words"]

FPS = 30
DUR = round(L["loop"][1] + 0.08, 2)           # loop restarts right after the last word
NFRAMES = int(DUR * FPS)

# set origins (each world lives far from the others)
GROUND = (0.0, 0.0, 0.0)
LAB = (500.0, 0.0, 0.0)
XRAY = (1000.0, 0.0, 0.0)


def W(line, word):
    """(start, end) of the first caption word in `line` containing `word` (case-insensitive)."""
    a, b = L[line]
    for s, e, w, *_ in WORDS:
        if a - 0.01 <= s <= b + 0.01 and word.lower() in re.sub(r"[^a-z0-9]", "", w.lower()):
            return s, e
    raise KeyError((line, word))


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


# ---------------------------------------------------------------- key moments (all on spoken words)
T_SPRAY1 = W("hook", "shoots")[0]              # first blast at the ant
T_SPRAY2 = W("hook", "out")[0] + 0.05          # close-up blast: "out of its BUTT"
T_CHEM = W("temp", "chemicals")[0]             # x-ray: the two reservoirs light up
T_MIX = W("temp", "mix")[0]                    # they flow into the chamber
T_BOOM = W("temp", "explode")[0] + 0.05        # the chamber explodes
T_REVEAL = W("crazy", "crazy")[0]              # the toad opens its eyes
T_TONGUE = W("swallow", "swallows")[0]         # tongue strike
T_FIRE = W("swallow", "firing")[0]             # explosions inside the stomach
T_OPEN = W("vomit", "throws")[0] - 0.1         # the toad opens its mouth...
T_EJECT = W("vomit", "back")[0]                # ...and throws the beetle back up
T_ALIVE = W("vomit", "alive")[0]               # the beetle flips back onto its feet
T_WALK = L["loop"][0]


def spray(t):
    """Spray strength 0..1 (first blast in the wide shot, second in the close-up)."""
    def burst(t0, d):
        if t < t0 or t > t0 + d:
            return 0.0
        u = (t - t0) / d
        return min(1.0, u / 0.08) * (1 - smoother((u - 0.6) / 0.4))
    return max(burst(T_SPRAY1, 0.9), burst(T_SPRAY2, 0.95))


def spray_start(t):
    """Start time of the blast that is active at t (for puff ages)."""
    return T_SPRAY2 if t >= T_SPRAY2 - 0.01 else T_SPRAY1


def ant_hit(t):
    """Seconds since the ant was hit (negative = before)."""
    return t - (T_SPRAY1 + 0.12)


def chem(t):
    """Reservoirs glowing (0..1)."""
    return smoother((t - T_CHEM + 0.1) / 0.4)


def flow(t):
    """Chemicals flowing into the chamber (0..1)."""
    return clamp((t - T_MIX) / (T_BOOM - T_MIX))


def chamber(t):
    """Reaction chamber glow: builds while mixing, explodes at T_BOOM, then rapid pulses."""
    if t < T_MIX:
        return 0.0
    if t < T_BOOM:
        return 0.35 * flow(t) ** 2
    u = t - T_BOOM
    return 0.55 + 0.45 * (0.5 + 0.5 * math.cos(u * 2 * math.pi * 3.0)) * math.exp(-u * 0.15)


def lab_jet(t):
    """Jet strength in the x-ray set."""
    if t < T_BOOM - 0.02:
        return 0.0
    return 0.65 + 0.35 * (0.5 + 0.5 * math.cos((t - T_BOOM) * 2 * math.pi * 3.0))


def toad_eyes(t):
    """Eyelid openness: shut (asleep) until the reveal, blink while swallowing (toads swallow with their eyes)."""
    o = smoother((t - T_REVEAL + 0.05) / 0.25)
    gulp = T_TONGUE + 0.35
    o *= 1 - 0.9 * math.exp(-((t - gulp) / 0.15) ** 2)
    return o


def tongue(t):
    """Tongue extension 0..1 (fast out, holds a frame, pulls back with the beetle)."""
    if t < T_TONGUE - 0.12 or t > T_TONGUE + 0.25:
        return 0.0
    if t < T_TONGUE:
        return ease_out((t - T_TONGUE + 0.12) / 0.12)
    return 1 - smoother((t - T_TONGUE) / 0.25)


def caught(t):
    return t >= T_TONGUE


def swallowed(t):
    """Beetle is inside the toad between the gulp and the ejection."""
    return T_TONGUE + 0.22 <= t < T_EJECT


def gulp(t):
    """Throat bulge 0..1."""
    return math.exp(-((t - T_TONGUE - 0.38) / 0.18) ** 2)


def fire_pulses(t):
    """Explosion flashes inside the stomach (0..1): one on 'firing', then a few more."""
    v = 0.0
    for k, dt in enumerate((0.0, 0.42, 0.78, 1.1, 1.45)):
        t0 = T_FIRE + dt
        if t >= t0 - 0.02:
            v = max(v, math.exp(-(t - t0) / 0.12) * (1 - 0.1 * k))
    return v


def retch(t):
    """Toad body heave before vomiting (0..1)."""
    return math.exp(-((t - T_EJECT + 0.2) / 0.3) ** 2)


def mouth(t):
    """Mouth opening 0..1: snaps open for the tongue, gapes for the vomit."""
    a = 0.55 * (smoother((t - T_TONGUE + 0.16) / 0.06) * (1 - smoother((t - T_TONGUE - 0.12) / 0.12)))
    b = smoother((t - T_OPEN) / 0.3) * (1 - smoother((t - T_EJECT - 0.35) / 0.4))
    return max(a, b)


def eject(t):
    """Seconds since the beetle left the toad's mouth (negative = not yet)."""
    return t - T_EJECT


def flip(t):
    """Beetle on its back (0) -> upright (1)."""
    return smoother((t - T_ALIVE + 0.1) / 0.35)


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    g = lambda x, y, z: add(GROUND, (x, y, z))
    b = lambda x, y, z: add(LAB, (x, y, z))
    x_ = lambda x, y, z: add(XRAY, (x, y, z))
    t1 = W("hook", "out")[0] - 0.05
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, fstop, focus, roll0, roll1, set
        (0.0, t1, g(-0.45, -4.2, 0.75), g(-0.6, -3.8, 0.62), g(-0.7, 0, 0.22), g(-0.75, 0, 0.2), 32, 32, 2.8, "beetle", 0, 0, "ground"),
        (t1, l["temp"][0] - 0.07, g(-1.55, -1.25, 0.35), g(-1.45, -1.05, 0.32), g(-0.35, 0, 0.18), g(-0.4, 0, 0.18), 50, 50, 2.8, "tip", 0, 0, "ground"),
        (l["temp"][0] - 0.07, T_BOOM + 0.32, b(0.25, -2.5, 0.8), b(0.05, -2.1, 0.62), b(-0.08, 0, 0.2), b(-0.12, 0, 0.2), 38, 38, 8, "lab", 0, 0, "lab"),
        (T_BOOM + 0.32, l["crazy"][0] - 0.08, b(-0.95, -1.7, 0.75), b(-1.25, -1.45, 0.55), b(-0.4, 0, 0.22), b(-0.55, 0, 0.18), 45, 45, 8, "chamber", 0, 0, "lab"),
        (l["crazy"][0] - 0.08, l["swallow"][0] - 0.04, g(-1.6, -0.9, 0.35), g(-1.2, -0.7, 0.42), g(1.2, 0, 0.6), g(2.0, 0, 1.0), 32, 32, 4.0, "toadeye", 0, 0, "ground"),
        (l["swallow"][0] - 0.04, T_TONGUE + 0.85, g(0.9, -5.2, 1.0), g(1.1, -4.8, 1.0), g(1.5, 0, 0.6), g(1.6, 0, 0.65), 32, 32, 5.6, "mouth", 0, 0, "ground"),
        (T_TONGUE + 0.85, l["vomit"][0] - 0.05, x_(3.4, -8.6, 2.0), x_(3.6, -7.8, 1.8), x_(3.7, 0, 1.1), x_(3.75, 0, 1.1), 35, 35, 8, "stomach", 0, 0, "xray"),
        (l["vomit"][0] - 0.05, T_ALIVE - 0.22, g(0.1, -2.6, 0.45), g(0.2, -2.4, 0.45), g(1.9, 0, 0.8), g(1.8, 0, 0.7), 24, 24, 4.0, "mouth", 0, 0, "ground"),
        (T_ALIVE - 0.22, l["loop"][0] - 0.07, g(0.0, -1.7, 0.45), g(0.1, -1.5, 0.4), g(0.75, 0.6, 0.1), g(0.75, 0.6, 0.12), 45, 45, 3.2, "landed", 0, 0, "ground"),
        (l["loop"][0] - 0.07, DUR + 0.1, g(0.2, -3.0, 0.8), g(0.0, -2.7, 0.7), g(0.6, 0.4, 0.25), g(0.3, 0.2, 0.25), 38, 38, 4.0, "walker", 0, 0, "ground"),
    ]


SHOTS = _shots()


def shot_index(t):
    for i, s in enumerate(SHOTS):
        if s[0] <= t < s[1]:
            return i
    return len(SHOTS) - 1


def shot_set(t):
    return SHOTS[shot_index(t)][12]


def drift(t, amp):
    return (amp * math.sin(t * 0.9) + amp * 0.5 * math.sin(t * 2.3), amp * 0.6 * math.sin(t * 1.3 + 1),
            amp * math.sin(t * 1.1 + 2) + amp * 0.4 * math.sin(t * 2.9))


def camera(t):
    t0, t1, p0, p1, a0, a1, l0, l1, fstop, focus, r0, r1, _set = SHOTS[shot_index(t)]
    u = smoother((t - t0) / (t1 - t0)) * 0.85 + 0.15 * clamp((t - t0) / (t1 - t0))
    p = lerpv(p0, p1, u)
    p = tuple(a + b for a, b in zip(p, drift(t, 0.006)))
    return p, lerpv(a0, a1, u), lerp(l0, l1, u), fstop, focus, lerp(r0, r1, u)
