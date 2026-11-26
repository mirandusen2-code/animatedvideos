"""Shared geometry (1 unit = 1 ft) for "Why airplane windows are round".

Set origins (each set is far from the others; only the active set renders):
  rip    a close-up fuselage section with a row of windows; the hero window W0 tears open (frame 0 / loop)
  cut    a cabin cross-section that swells like a balloon
  map    a flat skin panel with one window, coloured by stress, with "push" lines flowing around it
  comet  a 1950s jetliner over the sea that breaks apart
  tank   the same airframe in a water tank, pressure cycled until it splits at a window corner
"""
import math

import numpy as np

RIP_O = np.array([0.0, 0.0, 0.0])
CUT_O = np.array([400.0, 0.0, 0.0])
MAP_O = np.array([800.0, 0.0, 0.0])
COMET_O = np.array([0.0, 0.0, 30000.0])
TANK_O = np.array([1600.0, 0.0, 0.0])

# ---------------------------------------------------------------- rip fuselage (axis +Y = forward, windows on -X)
RIP_R = 5.5
WIN_PHI = math.radians(-78)          # angle from the top, negative = -X side (window band slightly above the middle)
WIN_PITCH = 3.1                      # window spacing along the fuselage (ft)
WIN_A, WIN_B = 0.62, 0.78            # window half width (along Y) and half height (around the fuselage) (ft)
WIN_YS = [WIN_PITCH * k for k in range(-7, 9)]   # window centres; W0 = y 0


def rip_surf(y, s, r=RIP_R):
    """Point on the fuselage: y along the axis, s = arc length from the window band centre (+ = up)."""
    y, s = np.broadcast_arrays(np.asarray(y, float), np.asarray(s, float))
    phi = WIN_PHI + s / r
    return np.stack([r * np.sin(phi), y, r * np.cos(phi)], -1)


def rip_normal(s):
    phi = WIN_PHI + np.asarray(s, float) / RIP_R
    return np.stack([np.sin(phi), np.zeros_like(phi), np.cos(phi)], -1)


W0_CORNER = (WIN_A * 0.93, WIN_B * 0.93)          # the tear starts at the window's forward-upper corner (y, s)


# ---------------------------------------------------------------- superellipse windows (n = 2 round ... 14 square)
def se_boundary(a, b, n, m=400):
    """Closed boundary points (m, 2) and curvature (m,) of |x/a|^n + |y/b|^n = 1."""
    th = np.linspace(0, 2 * math.pi, m, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    x = a * np.sign(c) * np.abs(c) ** (2.0 / n)
    y = b * np.sign(s) * np.abs(s) ** (2.0 / n)
    p = np.stack([x, y], -1)
    d1 = (np.roll(p, -1, 0) - np.roll(p, 1, 0)) / 2
    d2 = np.roll(p, -1, 0) - 2 * p + np.roll(p, 1, 0)
    k = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.maximum(np.linalg.norm(d1, axis=1) ** 3, 1e-9)
    return p, k


def se_halfwidth(a, b, n, y):
    """Half width of the window at height y (0 outside)."""
    u = np.clip(np.abs(np.asarray(y, float)) / b, 0, 1)
    w = a * np.clip(1 - u ** n, 0, 1) ** (1.0 / n)
    return np.where(np.abs(y) < b, w, 0.0)


# ---------------------------------------------------------------- the stress map panel (x across, z up; faces -Y)
MAP_A, MAP_B = 1.5, 1.9              # window half width / half height on the map panel (ft)
MAP_W, MAP_H = 9.0, 15.0             # panel half extents
N_SQUARE, N_ROUND = 14.0, 2.6        # superellipse exponents (squarish Comet window, rounded modern window)
MAP_CORNER = None                    # filled below: the window corner (x, z) where stress peaks for N_SQUARE


def stress(px, pz, n, gain=1.0):
    """Stress concentration factor around the window (1 = plain skin). Hoop push runs vertically."""
    p, k = se_boundary(MAP_A, MAP_B, n, 360)
    nx = np.abs(np.gradient(p[:, 1]))          # boundary tangent mostly vertical -> normal horizontal
    nrm = nx / np.maximum(np.hypot(np.gradient(p[:, 0]), np.gradient(p[:, 1])), 1e-9)
    kk = np.minimum(k, 60.0)
    K = (1.0 + 0.09 * kk ** 1.8) * (0.55 + 0.45 * nrm + 0.35 * (kk > 3))
    lam = 0.2 + 0.6 / np.sqrt(1 + kk)
    q = np.stack([np.asarray(px, float).ravel(), np.asarray(pz, float).ravel()], -1)
    out = np.ones(len(q))
    for c in range(0, len(q), 20000):
        d = np.linalg.norm(q[c:c + 20000, None, :] - p[None], axis=-1)
        out[c:c + 20000] = 1.0 + gain * np.max(K[None] * np.exp(-d / lam[None]), axis=1)
    inside = np.abs(q[:, 0] / MAP_A) ** n + np.abs(q[:, 1] / MAP_B) ** n < 1
    out[inside] = 0.0
    return out.reshape(np.shape(px))


def _corner():
    p, k = se_boundary(MAP_A, MAP_B, N_SQUARE, 400)
    sel = (p[:, 0] > 0) & (p[:, 1] > 0)
    i = np.argmax(np.where(sel, k, -1))
    return float(p[i, 0]), float(p[i, 1])


MAP_CORNER = _corner()


def crack_path(seed=7, n=40, length=2.4):
    """Jagged crack from the upper-right map corner, heading up and out (x, z), cumulative length."""
    g = np.random.default_rng(seed)
    x0, z0 = MAP_CORNER
    ang = math.radians(48)
    pts = [(x0 + 0.02, z0 + 0.02)]
    for i in range(n):
        ang += g.normal(0, 0.28)
        ang = min(max(ang, math.radians(25)), math.radians(70))
        st = length / n
        pts.append((pts[-1][0] + st * math.cos(ang), pts[-1][1] + st * math.sin(ang)))
    pts = np.array(pts)
    cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    return pts, cum


# ---------------------------------------------------------------- the jetliner (nose +Y; used in comet and tank)
JET_L, JET_R, JET_NOSE = 93.0, 5.0, 14.0
JET_WIN_S = [22.0 + 3.4 * k for k in range(16)]   # window stations from the nose
JET_SPLIT = (31.0, 64.0)                         # break stations (nose | centre | tail)


def jet_r(s):
    s = np.asarray(s, float)
    u = np.clip(s / JET_NOSE, 0, 1)
    r = JET_R * np.sqrt(np.clip(1 - (1 - u) ** 2, 0, 1)) ** 0.8
    t = np.clip((s - 66.0) / (JET_L - 66.0), 0, 1)
    return r * (1 - 0.82 * t ** 1.35)


def jet_zc(s):
    s = np.asarray(s, float)
    u = np.clip(s / JET_NOSE, 0, 1)
    t = np.clip((s - 66.0) / (JET_L - 66.0), 0, 1)
    return -1.4 * (1 - u) ** 2 + 2.6 * t ** 1.5


def jet_surf(s, phi, origin=(0, 0, 0)):
    """s = distance back from the nose tip; the nose points to +Y, so y = -s."""
    s, phi = np.broadcast_arrays(np.asarray(s, float), np.asarray(phi, float))
    r = jet_r(s)
    return np.stack([r * np.sin(phi), -s, jet_zc(s) + r * np.cos(phi)], -1) + np.asarray(origin, float)
