"""Shot timeline for "Wombats Poop Cubes", derived from the real narration timing (vo/timing.json).

World layout (one Blender scene, two sets):
  field set: night meadow. The walking line for the opening/loop runs along +x through the origin.
             The rock (S5/S6) and the cube trail (S4) are behind the opening camera, so they never show
             up in the opening/loop framing.
  gut set:   x-ray close-up of the end of the intestine, far away at GUT.
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

GUT = (500.0, 0.0, 0.0)


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
T_CUBES = W("hook", "cubes")[0]          # first cube lands
T_FLAT = W("real", "flat")[0]
T_CORNERS = W("real", "corners")[0]
T_GUT = W("gut", "gut")[0]
T_STIFF = W("gut", "stiff")[0]
T_STRETCHY = W("gut", "stretchy")[0]
T_SQUEEZE = W("squeeze", "squeeze")[0]
T_INTO = W("squeeze", "corners")[0]
T_DRIES = W("squeeze", "dries")[0]
T_NIGHT = W("night", "night")[0]
T_100 = W("night", "100")[0]
T_ROCKS = W("turf", "rocks")[0]
T_TURF = W("turf", "turf")[0]
T_ROUND = W("roll", "round")[0]
T_ROLL = W("roll", "roll")[0]
T_WHY = W("loop", "why")[0]

# ---------------------------------------------------------------- the walking wombat (opening / loop)
WALK_V = 0.30           # walking speed (m/s)
WALK_A = math.radians(32)                    # walking heading (right and slightly away from the camera)
WALK_D = (math.cos(WALK_A), math.sin(WALK_A), 0.0)
WALK_P0 = (-0.30, -0.10, 0.0)                # body centre at t = 0
STRIDE = 0.34           # distance per full leg cycle
REAR = 0.50             # body centre -> rump distance
CUBE = 0.05             # cube edge (stylised, ~2.5x real size so it reads on a phone)

# the hook cube pops out on "poop" and lands on "CUBES"
T_POP = W("hook", "poop")[0] - 0.05
T_LAND = T_CUBES + 0.04


def walk_pos(te):
    return tuple(p + d * WALK_V * te for p, d in zip(WALK_P0, WALK_D))


T_OUT = T_POP + 0.15             # cube fully out of the rump, starts to fall
CUBE0 = tuple(p - d * (REAR + 0.05) for p, d in zip(walk_pos(T_OUT), WALK_D))[:2] + (0.0,)


# ---------------------------------------------------------------- night time-lapse (S4) and rock (S5/S6)
NIGHT_C = (-6.0, -9.5, 0.0)     # centre of the time-lapse meadow (behind the opening camera)
ROCK = (-3.2, -7.2, 0.0)        # the marking rock
ROCK_TOP = 0.20


def night_path(u):
    """Wombat route in the time-lapse (u 0..1): a lazy S-curve across the meadow."""
    cx, cy, _ = NIGHT_C
    x = cx - 1.8 + 3.6 * u
    y = cy + 0.8 * math.sin(u * 2 * math.pi * 0.9) - 0.3 * u
    return x, y, 0.0


N_TRAIL = 34                     # cubes visible in the time-lapse (the counter says 100)


def trail_drop_u(k):
    return 0.04 + 0.92 * k / (N_TRAIL - 1)


# cubes left on the rock (time, landing offset on the rock top)
ROCK_DROPS = [(W("turf", "leaves")[0], (0.02, -0.05)), (T_ROCKS, (-0.07, 0.03)), (W("turf", "mark")[0], (0.07, 0.06))]
BALL_T = T_ROUND - 0.08          # the round poop appears ...
BALL_ROLL = T_ROLL - 0.25        # ... and rolls off


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    g = lambda x, y, z: add(GUT, (x, y, z))
    rx, ry, _ = ROCK
    nx, ny, _ = NIGHT_C
    cx, cy, _ = CUBE0
    side = (WALK_D[1], -WALK_D[0], 0.0)                       # to the wombat's right, towards the camera
    def wp(t, dist, h, back=0.0):
        p = walk_pos(t)
        return (p[0] + side[0] * dist - WALK_D[0] * back, p[1] + side[1] * dist - WALK_D[1] * back, h)
    def wt(t, h, fwd=0.0):
        p = walk_pos(t)
        return (p[0] + WALK_D[0] * fwd, p[1] + WALK_D[1] * fwd, h)
    s2a0, s2a1 = l["gut"][0] - 0.1, T_STIFF - 0.1
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, fstop, focus, set
        # S0 hook: low rear three-quarter view, the wombat waddles off right, a cube drops out on "CUBES"
        (0.0, l["real"][0] - 0.1, (-0.55, -1.85, 0.64), (-0.20, -1.58, 0.60), (-0.24, -0.04, 0.22), (0.16, 0.22, 0.22), 28, 28, 4.0, "wombat", "field"),
        # S1 macro on the cube: flat sides, sharp corners
        (l["real"][0] - 0.1, l["gut"][0] - 0.1, (cx - 0.26, cy - 0.36, 0.17), (cx + 0.12, cy - 0.38, 0.15), (cx, cy, 0.03), (cx, cy, 0.025), 60, 60, 5.6, "cube0", "field"),
        # S2a x-ray side view of the walking wombat: its gut lights up
        (s2a0, s2a1, wp(s2a0, 2.3, 0.42, 0.25), wp(s2a1, 2.0, 0.40, 0.15), wt(s2a0, 0.28), wt(s2a1, 0.28), 38, 38, 5.6, "wombat", "field"),
        # S2b gut tube side view: stiff and stretchy bands
        (T_STIFF - 0.1, l["squeeze"][0] - 0.02, g(-3.3, -1.45, 1.05), g(-2.8, -1.3, 0.95), g(0.4, 0, 0), g(0.6, 0, 0), 30, 30, 11, "gut", "gut"),
        # S3 squeeze: three-quarter view towards the exit, cubes come out
        (l["squeeze"][0] - 0.02, l["night"][0] - 0.1, g(5.0, -1.9, 1.1), g(4.7, -1.7, 0.95), g(2.3, 0, -0.1), g(2.5, 0, -0.15), 32, 32, 11, "exit", "gut"),
        # S4 night time-lapse from above: up to 100 cubes a night
        (l["night"][0] - 0.1, l["turf"][0] - 0.05, (nx + 0.4, ny - 4.3, 1.6), (nx + 0.2, ny - 3.9, 1.45), (nx, ny + 0.3, 0.2), (nx, ny + 0.3, 0.2), 28, 28, 8, "trail", "field"),
        # S5 the rock: cubes left on top to mark its turf
        (l["turf"][0] - 0.05, l["roll"][0] - 0.12, (rx + 1.05, ry - 2.6, 0.85), (rx + 0.95, ry - 2.35, 0.78), (rx + 0.42, ry, 0.26), (rx + 0.40, ry, 0.24), 30, 30, 5.6, "rock", "field"),
        # S6 round poop rolls off, cubes stay
        (l["roll"][0] - 0.12, l["loop"][0] - 0.15, (rx + 0.25, ry - 1.15, 0.52), (rx + 0.30, ry - 1.05, 0.48), (rx + 0.15, ry, 0.18), (rx + 0.2, ry, 0.16), 40, 40, 5.6, "rock", "field"),
        # S7 last shot glides back into the exact opening framing: the loop restarts as a match cut
        (l["loop"][0] - 0.15, DUR, (-1.15, -2.2, 0.78), (-0.55, -1.85, 0.64), (-0.72, -0.34, 0.26), (-0.24, -0.04, 0.22), 25, 28, 4.0, "wombat", "field"),
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
    """Clock for the opening/loop world (walking wombat, grass, the hook cube).
    In the last shot it runs from about -1.8 s up to 0, so the final frame flows straight into frame 0."""
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
    lens = lerp(l0, l1, smoother(x / 0.7)) if i == len(SHOTS) - 1 else lerp(l0, l1, u)
    p = tuple(a + b for a, b in zip(p, drift(env_t(t), 0.004)))
    return p, lerpv(a0, a1, u), lens, fstop, focus
