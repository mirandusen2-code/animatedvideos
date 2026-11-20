"""Wombat body + leg meshes from a signed-distance sculpt (smooth unions of ellipsoids), via marching cubes.

Units: metres, x forward, z up, ground at z = 0. The body is one smooth closed mesh; the four legs are
separate stubby meshes with their pivot (hip) at the origin so they can swing while walking.
"""
import numpy as np
from skimage import measure


def ell(p, c, r):
    """Approximate signed distance to an ellipsoid (good enough near the surface)."""
    q = (p - np.asarray(c)) / np.asarray(r)
    k0 = np.linalg.norm(q, axis=-1)
    k1 = np.linalg.norm(q / np.asarray(r), axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def body_sdf(p):
    d = ell(p, (-0.04, 0.0, 0.265), (0.42, 0.245, 0.205))          # barrel
    d = smin(d, ell(p, (-0.27, 0.0, 0.255), (0.22, 0.235, 0.215)), 0.10)   # big round rump
    d = smin(d, ell(p, (0.17, 0.0, 0.255), (0.21, 0.225, 0.195)), 0.10)    # shoulders
    d = smin(d, ell(p, (0.40, 0.0, 0.275), (0.155, 0.165, 0.14)), 0.09)    # broad head, no neck
    for s in (-1, 1):
        d = smin(d, ell(p, (0.43, s * 0.075, 0.235), (0.11, 0.09, 0.09)), 0.05)   # cheeks
    d = smin(d, ell(p, (0.535, 0.0, 0.245), (0.075, 0.105, 0.075)), 0.05)    # wide muzzle
    for s in (-1, 1):
        d = smin(d, ell(p, (0.385, s * 0.105, 0.41), (0.028, 0.048, 0.06)), 0.035)   # small round ears
    d = np.maximum(d, 0.075 - p[..., 2])                                 # flat-ish belly line
    return d


def leg_sdf(p):
    d = ell(p, (0.0, 0.0, -0.06), (0.075, 0.07, 0.10))                  # thigh/shoulder bulge (hidden in body)
    d = smin(d, ell(p, (0.01, 0.0, -0.15), (0.06, 0.058, 0.07)), 0.05)  # short stubby leg
    d = smin(d, ell(p, (0.045, 0.0, -0.19), (0.075, 0.062, 0.03)), 0.04)   # broad paw
    return d


def mesh(sdf, lo, hi, step):
    xs = [np.arange(a, b + step, step) for a, b in zip(lo, hi)]
    g = np.stack(np.meshgrid(*xs, indexing="ij"), axis=-1)
    vol = sdf(g)
    v, f, _n, _ = measure.marching_cubes(vol, 0.0, spacing=(step, step, step))
    v = v + np.asarray(lo)
    return v, f


def surface_along(sdf, origin, direction, max_d=0.4):
    """First surface point from `origin` (inside) along `direction`."""
    o = np.asarray(origin, float)
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    ts = np.linspace(0, max_d, 800)
    vals = sdf(o[None, :] + ts[:, None] * d[None, :])
    i = int(np.argmax(vals > 0))
    return o + ts[i] * d


def build(step=0.007):
    body = mesh(body_sdf, (-0.55, -0.30, 0.03), (0.66, 0.30, 0.52), step)
    leg = mesh(leg_sdf, (-0.10, -0.09, -0.24), (0.14, 0.09, 0.06), step * 0.7)
    eyes = [surface_along(body_sdf, (0.42, s * 0.05, 0.315), (0.55, s * 0.62, 0.33)) for s in (-1, 1)]
    nose = surface_along(body_sdf, (0.50, 0.0, 0.25), (1.0, 0.0, -0.05))
    return body, leg, eyes, nose


if __name__ == "__main__":
    (bv, bf), (lv, lf), eyes, nose = build()
    print(len(bv), len(bf), len(lv), eyes, nose)
