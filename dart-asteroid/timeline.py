"""Shot timeline for "NASA Slammed a Spacecraft Into an Asteroid", derived from the narration timing.

One space set. 1 unit = 10 m. Didymos (780 m wide) sits at the origin; its moon Dimorphos (~150 m)
orbits 1.19 km away in the xy plane. The DART impact point is on Dimorphos' side facing +x.
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


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def lerp(a, b, x):
    return a + (b - a) * x


def lerpv(a, b, x):
    return tuple(lerp(p, q, x) for p, q in zip(a, b))


def add(*v):
    return tuple(sum(c) for c in zip(*v))


def mul(a, s):
    return tuple(c * s for c in a)


def norm(a):
    n = math.sqrt(sum(c * c for c in a))
    return tuple(c / n for c in a)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(p * q for p, q in zip(a, b))


# ---------------------------------------------------------------- word times
T_SLAM = W("hook", "slammed")[0]
T_ASTER = W("hook", "asteroid")[0]
T_14K = W("hook", "14000")[0]
T_TARGET = W("moon", "target")[0]
T_TINY = W("moon", "tiny")[0]
T_CIRC = W("moon", "circling")[0]
T_BIGGER = W("moon", "bigger")[0]
T_HIT = W("orbit", "hit")[0]
T_ORBIT = W("orbit", "orbit")[0]
T_33 = W("orbit", "33")[0]
T_BLAST = W("tail", "blasted")[0]
T_TAIL = W("tail", "tail")[0]
T_6K = W("tail", "6000")[0]
T_EUROPE = W("hera", "europe")[0]
T_HERA = W("hera", "hera")[0]
T_ARRIVED = W("hera", "arrived")[0]
T_CRATER = W("hera", "crater")[0]
T_NOCRATER = W("twist", "crater")[0]
T_WHOLE = W("twist", "whole")[0]
T_CHANGED = W("twist", "changed")[0]
T_SAND = W("twist", "sandcastle")[0]
T_ALL = W("loop", "all")[0]

# ---------------------------------------------------------------- geometry
ORBIT_R = 119.0                       # 1.19 km
DIMO_AX = (8.9, 8.7, 5.8)             # semi-axes before the impact (177 x 174 x 116 m)
DIDY_R = 39.0                         # 780 m
M0 = (0.0, ORBIT_R, 0.0)              # Dimorphos where the impact happens
N_IMP = norm((1.0, 0.28, 0.16))       # impact direction from Dimorphos' centre
SUN = norm((0.75, -0.55, 0.38))       # direction towards the sun
SIDE = norm(cross((0.0, 0.0, 1.0), N_IMP))
UP = cross(N_IMP, SIDE)


def dimo_surface_r(d):
    """Distance from Dimorphos' centre to its (pre-impact) ellipsoid surface along unit direction d."""
    a, b, c = DIMO_AX
    return 1.0 / math.sqrt((d[0] / a) ** 2 + (d[1] / b) ** 2 + (d[2] / c) ** 2)


P_IMP = add(M0, mul(N_IMP, dimo_surface_r(N_IMP)))
V_DART = norm(add(mul(N_IMP, -0.95), mul(SIDE, 0.25), mul(UP, -0.12)))   # DART's flight direction
DART_SPEED = 24.0                     # units/s in the (slow-motion) final approach


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    s1 = T_SLAM + 1.95                                 # hook close-up -> wide plume
    s2 = l["moon"][0] - 0.05
    s3 = l["orbit"][0] - 0.1
    s4 = l["tail"][0] - 0.1
    s5 = l["hera"][0] - 0.1
    s6 = l["twist"][0] - 0.1
    s7 = l["loop"][0] - 0.25
    c0 = add(P_IMP, mul(N_IMP, 5.0), mul(SIDE, 19.0), mul(UP, 6.0))
    c1 = add(P_IMP, mul(N_IMP, 11.0), mul(SIDE, 36.0), mul(UP, 11.0))
    tg0 = add(P_IMP, mul(N_IMP, 1.5))
    tg1 = add(P_IMP, mul(N_IMP, 4.0))
    w0 = add(M0, mul(SIDE, 125.0), mul(N_IMP, 40.0), (0.0, 0.0, 24.0))
    w1 = add(M0, mul(SIDE, 140.0), mul(N_IMP, 50.0), (0.0, 0.0, 28.0))
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1
        # S0 hook: the impact, close; rocks fly at the lens; the camera eases back
        (0.0, s1, c0, c1, tg0, tg1, 30, 30),
        # S1 wide: the ejecta cone blooming out of Dimorphos, Didymos behind (14,000 MPH)
        (s1, s2, w0, w1, add(M0, mul(N_IMP, 12.0)), add(M0, mul(N_IMP, 16.0)), 45, 45),
        # S2 before the hit: the tiny moon circling the big asteroid (orbiting camera)
        (s2, s3, (150.0, -250.0, 135.0), (85.0, -285.0, 115.0), (0.0, 35.0, 0.0), (0.0, 35.0, 0.0), 32, 32),
        # S3 top-down: the hit, the orbit shrinks, -33 minutes
        (s3, s4, (0.0, -25.0, 540.0), (0.0, -12.0, 500.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 35, 35),
        # S4 the tail of rock streaming away from the sun
        (s4, s5, None, None, None, None, 30, 30),
        # S5 Hera arrives
        (s5, s6, None, None, None, None, 30, 30),
        # S6 no crater: the whole moon changed shape
        (s6, s7, add(M0, mul(N_IMP, 30.0), mul(SIDE, -14.0), (0.0, 0.0, 9.0)),
         add(M0, mul(N_IMP, 26.0), mul(SIDE, 12.0), (0.0, 0.0, 6.0)), M0, M0, 35, 35),
        # S7 all because: chase DART into the surface -> blends into the opening shot
        (s7, DUR, None, None, None, None, 30, 30),
    ]


SHOTS = _shots()


def shot_index(t):
    for i, s in enumerate(SHOTS):
        if s[0] <= t < s[1]:
            return i
    return len(SHOTS) - 1


def env_t(t):
    """Loop clock: the last shot runs at negative time, so it flows straight into frame 0."""
    return t - DUR if shot_index(t) == len(SHOTS) - 1 else t


TE_IMP = -0.3                         # impact time on the loop clock (just before the seam)
CAM0_K = 1.6


def cam0(te):
    s0 = SHOTS[0]
    n = 1 - math.exp(-CAM0_K * s0[1])
    if te >= 0:
        f = (1 - math.exp(-CAM0_K * te)) / n
    else:                                # bounded, C1-smooth extension before the seam
        f = (CAM0_K / n) * -0.25 * (1 - math.exp(te / 0.25))
    return lerpv(s0[2], s0[3], f), lerpv(s0[4], s0[5], f), s0[6]


# ---------------------------------------------------------------- Dimorphos' orbit (S2, S3)
PERIOD_VIS = 7.0                        # seconds per orbit on screen (sped up)


def dimo_pos(t):
    i = shot_index(t)
    if i in (2, 3):
        th0 = math.pi / 2
        if i == 2:
            th = th0 - 2 * math.pi * (SHOTS[3][0] - t) / PERIOD_VIS
            return (ORBIT_R * math.cos(th), ORBIT_R * math.sin(th), 0.0)
        # S3: hit at T_HIT, then the orbit tightens (exaggerated 12 %) and speeds up
        u = t - T_HIT
        r = ORBIT_R * (1 - 0.12 * smoother(u / 0.9)) if u > 0 else ORBIT_R
        w = 2 * math.pi / PERIOD_VIS
        th = th0 + w * (t - SHOTS[3][0]) + (0.55 * w * (u - 0.45) if u > 0.45 else 0.0)
        return (r * math.cos(th), r * math.sin(th), 0.0)
    return M0


def orbit_rings(t):
    """(old ring alpha, new ring alpha, new ring radius) of the drawn orbits."""
    i = shot_index(t)
    if i == 2:
        return smoother((t - T_CIRC + 0.1) / 0.5), 0.0, ORBIT_R
    if i == 3:
        u = t - T_HIT
        return 1.0, smoother((u - 0.1) / 0.4), ORBIT_R * (1 - 0.12 * smoother(u / 0.9))
    return 0.0, 0.0, ORBIT_R


# ---------------------------------------------------------------- the impact (S0, S1, S7, flash in S3)
def impact_age(t):
    """Seconds since DART hit, in the current shot (None = no impact visible)."""
    i = shot_index(t)
    if i == 0:
        return t - TE_IMP
    if i == 1:
        return t - TE_IMP
    return None


def dart_pos(t):
    """DART's position: S2 it leaves the camera for the target; S7 its own camera rushes at the surface."""
    i = shot_index(t)
    if i == len(SHOTS) - 1:
        rem = DUR - t + 0.04
        return add(P_IMP, mul(V_DART, -(18.0 * rem + 12.0 * rem * rem)))
    if i == 2:
        t0 = SHOTS[2][0]
        loc, tgt, _ = camera(t0)
        fwd = norm(add(tgt, mul(loc, -1.0)))
        right = norm(cross(fwd, (0.0, 0.0, 1.0)))
        up = cross(right, fwd)
        start = add(loc, mul(fwd, 3.2), mul(right, 0.4), mul(up, -0.45))
        goal = M0
        u = t - t0
        dirv = norm(add(goal, mul(start, -1.0)))
        return add(start, mul(dirv, 2.0 * u + 6.0 * u * u))
    return None


def dart_dir(t):
    if shot_index(t) == 2:
        t0 = SHOTS[2][0]
        return norm(add(M0, mul(dart_pos(t0), -1.0)))
    return V_DART


def flash(t):
    a = impact_age(t)
    if shot_index(t) == 3:
        a = t - T_HIT
    if a is None or a < 0:
        return 0.0
    return math.exp(-a / 0.09) + 0.25 * math.exp(-a / 0.5) if a < 2.0 else 0.0


# ---------------------------------------------------------------- the tail (S4)
TAIL_DIR = norm(add(mul(SUN, -1.0), (0.0, 0.0, -0.1)))


def tail_grow(t):
    if shot_index(t) != 4:
        return 1.0
    return 0.35 + 0.65 * smoother((t - T_BLAST) / 2.2)


# ---------------------------------------------------------------- Hera (S5)
HERA_A = add(M0, (-150.0, -330.0, 70.0))
HERA_B = add(M0, (-55.0, -150.0, 28.0))


def hera_pos(t):
    i = shot_index(t)
    if i != 5:
        return None
    x = clamp((t - SHOTS[5][0]) / (SHOTS[5][1] - SHOTS[5][0]))
    return lerpv(HERA_A, HERA_B, 1 - (1 - x) ** 1.6)


HERA_DIR = norm(add(HERA_B, mul(HERA_A, -1.0)))


# ---------------------------------------------------------------- reshape (S6)
def reshape(t):
    i = shot_index(t)
    if i == 6:
        return smoother((t - T_WHOLE) / 1.6)
    if i in (4, 5):
        return 0.0
    return 0.0


def ghost(t):
    """Alpha of the 'before' outline (S6)."""
    if shot_index(t) != 6:
        return 0.0
    return smoother((t - T_WHOLE + 0.2) / 0.4)


# ---------------------------------------------------------------- camera
def camera(t):
    i = shot_index(t)
    t0, t1, p0, p1, a0, a1, l0, l1 = SHOTS[i]
    x = clamp((t - t0) / (t1 - t0))
    if i == 0:
        return cam0(t)
    if i == 4:                                       # tail: side view, slow pan along it
        base = add(M0, mul(TAIL_DIR, 30.0))
        side = norm(cross(TAIL_DIR, (0.0, 0.0, 1.0)))
        loc = add(base, mul(side, -170.0), (0.0, 0.0, 30.0), mul(TAIL_DIR, -30.0 + 50.0 * x))
        tgt = add(M0, mul(TAIL_DIR, 28.0 + 32.0 * x))
        return loc, tgt, l0
    if i == 5:                                       # follow Hera from behind and to the side
        h = hera_pos(t)
        side = norm(cross(HERA_DIR, (0.0, 0.0, 1.0)))
        loc = add(h, mul(HERA_DIR, -1.5 + 0.3 * x), mul(side, 0.05), (0.0, 0.0, 0.5))
        tgt = add(h, mul(HERA_DIR, 5.0), (0.0, 0.0, 0.25))
        return loc, tgt, l0
    if i == len(SHOTS) - 1:                          # DART's own camera rushing at the boulders (cut on impact)
        d = dart_pos(t)
        return d, add(d, V_DART), l0
    u = smoother(x) * 0.7 + 0.3 * x
    return lerpv(p0, p1, u), lerpv(a0, a1, u), lerp(l0, l1, u)


def shake(t):
    a = impact_age(t)
    if a is None or a < 0 or shot_index(t) == 1:
        return 0.0
    return 0.35 * math.exp(-a / 0.35)
