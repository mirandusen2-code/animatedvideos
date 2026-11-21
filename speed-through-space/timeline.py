"""Shot timeline for "You're Moving at 500,000 MPH", derived from the real narration timing (vo/timing.json).

World layout (one Blender scene, three sets far apart):
  earth:  Earth (radius 1) at the origin, lit by a sun lamp; streaking stars for speed. Also used for Pangaea.
  orbit:  the Sun and a small Earth on its orbit, at ORBIT.
  galaxy: the Milky Way (radius GAL_R) at GAL, with the Sun's marker on its galactic orbit.
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
NFRAMES = round((L["loop"][1] + 0.05) * FPS)  # loop restarts right after the last word
DUR = NFRAMES / FPS                            # exact loop period: picture, sound and motion share it

ORBIT = (1000.0, 0.0, 0.0)
GAL = (3000.0, 0.0, 0.0)
GAL_R = 30.0                 # galaxy disc radius (scene units)
SUN_GAL_R = 0.52 * GAL_R     # the Sun sits about halfway out
EARTH_ORBIT_R = 6.0


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


# ---------------------------------------------------------------- key moments (all on spoken words)
T_500 = W("hook", "500000")[0]
T_SPINS = W("spin", "spins")[0]
T_1000 = W("spin", "1000")[0]
T_RACES = W("orbit", "races")[0]
T_67 = W("orbit", "67000")[0]
T_DRAGS = W("galaxy", "drags")[0]
T_GALAXY = W("galaxy", "galaxy")[0]
T_500B = W("galaxy", "500000")[0]
T_TRIP = W("lap", "trip")[0]
T_230 = W("lap", "230")[0]
T_YEARS = W("lap", "years")[1]
T_HERE = W("dino", "here")[0]
T_DINO = W("dino", "dinosaurs")[0]
T_STILL = W("loop", "still")[0]

# ---------------------------------------------------------------- the "you" beacon and Earth's spin
YOU_LAT, YOU_LON = 39.0, -95.0      # central USA
SPIN0 = math.radians(25.0)          # Earth's rotation angle at t = 0 (the beacon faces the camera)
SPIN_SLOW = 0.045                   # rad/s in the opening (and the loop shot)


def spin_angle(t, te):
    """Earth's rotation angle. Slow in the opening/loop, a fast time-lapse while "Earth spins you around"."""
    i = shot_index(t)
    if i == 1:
        t0, t1 = SHOTS[1][0], SHOTS[1][1]
        u = (t - t0)
        # accelerate to ~1 turn per 2.2 s, then keep going (time-lapse)
        fast = 2 * math.pi / 2.2
        ramp = 0.6
        ang = fast * (u - ramp / 2) if u > ramp else fast * u * u / (2 * ramp)
        return SPIN0 + SPIN_SLOW * t0 + ang
    return SPIN0 + SPIN_SLOW * te


STREAK_V = 9.0                      # streaking stars: speed past the Earth (scene units / s)


# ---------------------------------------------------------------- Earth on its orbit (S2)
def orbit_angle(t):
    t0, t1 = SHOTS[2][0], SHOTS[2][1]
    u = t - t0
    return math.radians(12) + 0.10 * u + 0.006 * u * u


# ---------------------------------------------------------------- the Sun's galactic orbit (S3, S4)
def gal_angle(t):
    """Angle of the Sun on its galactic orbit (the galaxy turns clockwise: its arms trail)."""
    t3 = SHOTS[3][0]
    t4, t5 = SHOTS[4][0], SHOTS[4][1]
    base = math.radians(-60)
    if t < t4:
        return base - 0.05 * (t - t3)
    u = smoother((t - t4 - 0.2) / (t5 - t4 - 0.5))
    return base - 0.05 * (t4 - t3) - 2 * math.pi * u          # one full lap during "230 million years"


def years_ago(t):
    """Counter during the lap: 0 -> 230 (million years)."""
    t4, t5 = SHOTS[4][0], SHOTS[4][1]
    return 230.0 * smoother((t - t4 - 0.2) / (t5 - t4 - 0.5))


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    o = lambda x, y, z: add(ORBIT, (x, y, z))
    g = lambda x, y, z: add(GAL, (x, y, z))
    sgx = SUN_GAL_R * math.cos(math.radians(-60))
    sgy = SUN_GAL_R * math.sin(math.radians(-60))
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, set, focus
        # S0 hook: Earth close, the beacon on the day side, stars streaking past
        (0.0, l["spin"][0] - 0.15, (0.55, -3.05, 1.15), (0.45, -2.85, 1.05), (0.0, 0.0, 0.55), (0.0, 0.0, 0.52), 34, 34, "earth"),
        # S1 Earth spins (time-lapse), the beacon draws its latitude circle
        (l["spin"][0] - 0.15, l["orbit"][0] - 0.02, (2.2, -3.4, 2.6), (2.0, -3.6, 2.2), (0, 0, 0.1), (0, 0, 0.05), 30, 30, "earth"),
        # S2 the Earth races around the Sun
        (l["orbit"][0] - 0.02, l["galaxy"][0] - 0.12, o(6.6, -10.2, 6.4), o(6.0, -9.4, 5.6), o(2.3, 0.6, -0.4), o(2.7, 0.9, -0.4), 26, 26, "orbit"),
        # S3 pull back from the Sun's neighbourhood to the whole Milky Way
        (l["galaxy"][0] - 0.12, l["lap"][0] - 0.12, g(sgx * 1.08, sgy * 1.08 - 3.0, 2.0), g(4.0, -62.0, 34.0), g(sgx, sgy, 0), g(0, -1.0, 0), 30, 30, "galaxy"),
        # S4 one lap around the galaxy (time-lapse, seen from above)
        (l["lap"][0] - 0.12, l["dino"][0] - 0.12, g(2.0, -40.0, 58.0), g(1.0, -30.0, 63.0), g(0, -2.0, 0), g(0, -1.5, 0), 30, 30, "galaxy"),
        # S5 230 million years ago: Pangaea
        (l["dino"][0] - 0.12, l["loop"][0] - 0.15, (1.6, -3.0, 1.4), (1.3, -3.25, 1.2), (0, 0, 0.15), (0, 0, 0.12), 32, 32, "earth"),
        # S6 last shot glides back into the exact opening framing: the loop restarts as a match cut
        (l["loop"][0] - 0.15, DUR, (1.2, -3.7, 1.9), (0.55, -3.05, 1.15), (0.1, 0.0, 0.62), (0.0, 0.0, 0.55), 30, 34, "earth"),
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
    """Clock for the opening/loop world (Earth's slow spin, clouds, streaking stars).
    In the last shot it runs up to 0, so the final frame flows straight into frame 0."""
    return t - DUR if shot_index(t) == len(SHOTS) - 1 else t


def camera(t):
    i = shot_index(t)
    t0, t1, p0, p1, a0, a1, l0, l1, _set = SHOTS[i]
    x = clamp((t - t0) / (t1 - t0))
    if i == len(SHOTS) - 1:
        # ease in, then arrive with the same slow speed the opening push-in starts with
        h0 = SHOTS[0]
        v0 = 0.15 / (h0[1] - h0[0])
        d_end = math.dist(p0, p1)
        k = clamp(v0 * math.dist(h0[2], h0[3]) / max(d_end, 1e-6) * (t1 - t0), 0.0, 0.9)
        u = (1 - k) * smoother(x) + k * x
        lens = lerp(l0, l1, smoother(x / 0.7))
    elif i == 3:
        u = ease_in(x) * 0.25 + smoother(x) * 0.75       # the big pull-back accelerates away
        lens = lerp(l0, l1, u)
    else:
        u = smoother(x) * 0.85 + 0.15 * x
        lens = lerp(l0, l1, u)
    p = lerpv(p0, p1, u)
    return p, lerpv(a0, a1, u), lens
