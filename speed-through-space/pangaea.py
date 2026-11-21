"""Stylised Pangaea (~230 million years ago) texture from NASA's Blue Marble: each present-day continent is
cut out of the map and rotated about its own Euler pole (Africa held fixed), closing the Atlantic and
re-assembling Gondwana. Ice caps are replaced by land (the Triassic had no polar ice).

Usage: python3 pangaea.py <bmng.jpg> <shadedrelief.jpg> <out.png> [--preview out_small.png]
"""
import sys

import numpy as np
from PIL import Image, ImageFilter

W, H = 4096, 2048


def lonlat_grid(w, h):
    lon = np.radians((np.arange(w) + 0.5) / w * 360 - 180)
    lat = np.radians(90 - (np.arange(h) + 0.5) / h * 180)
    return np.meshgrid(lon, lat)


def to_xyz(lon, lat):
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)


def to_lonlat(v):
    return np.arctan2(v[..., 1], v[..., 0]), np.arcsin(np.clip(v[..., 2], -1, 1))


def rot(pole_lat, pole_lon, ang):
    """Rotation matrix about the Euler pole (degrees)."""
    k = to_xyz(np.radians(pole_lon), np.radians(pole_lat))
    a = np.radians(ang)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


# (name, region test on present lon/lat in degrees, list of rotations applied in order)
def regions(lo, la):
    sa = (lo > -82) & (lo < -34) & (la < 12) & (la > -57)
    na = ((lo < -52) & (lo > -170) & (la >= 12)) | ((lo > -75) & (lo < -10) & (la > 58)) | \
         ((lo < -77) & (lo > -100) & (la >= 7) & (la < 12))
    af = (lo > -20) & (lo < 60) & (la > -37) & (la < 37) & ~((lo > 26) & (la > 31))
    india = (lo > 66) & (lo < 92) & (la > 5) & (la < 27)
    aus = (lo > 110) & (lo < 156) & (la < -9) & (la > -46)
    ant = la < -60
    eur = ~(sa | na | af | india | aus | ant)
    return {"sa": sa, "na": na, "af": af, "india": india, "aus": aus, "ant": ant, "eur": eur}


def move(src, tgt, spin=0.0):
    """Rotation taking continent centre `src` (lon, lat) to `tgt`, then turning it by `spin` degrees about
    its new centre (positive = anticlockwise seen from above)."""
    p = to_xyz(np.radians(src[0]), np.radians(src[1]))
    q = to_xyz(np.radians(tgt[0]), np.radians(tgt[1]))
    ax = np.cross(p, q)
    s_ = np.linalg.norm(ax)
    ang = np.degrees(np.arctan2(s_, p @ q))
    R = np.eye(3)
    if s_ > 1e-9:
        ax /= s_
        R = rot(np.degrees(np.arcsin(ax[2])), np.degrees(np.arctan2(ax[1], ax[0])), ang)
    S = rot(tgt[1], tgt[0], spin)
    return [S @ R]


MOVES = {
    "af": [],
    "sa": move((-60, -15), (-16.5, -16), -14),     # Brazil's bulge tucked into the Gulf of Guinea
    "na": move((-100, 45), (-46, 39), 20),      # east coast against north-west Africa
    "eur": [],
    "india": move((78, 18), (54, -26), 70),      # against Madagascar / East Africa
    "ant": move((0, -90), (30, -60), 20),         # against southern Africa
    "aus": move((134, -25), (92, -47), 55),      # with East Antarctica
}


def build(bm_path, sr_path, out_path, preview=None, extra=None):
    bm = Image.open(bm_path).convert("RGB").resize((W, H), Image.LANCZOS)
    sr = np.asarray(Image.open(sr_path).convert("RGB").resize((W, H), Image.LANCZOS)).astype(float)
    ocean = np.array([127, 170, 208.0])
    dist = np.linalg.norm(sr - ocean, axis=-1)
    shelf = (sr[..., 2] > sr[..., 0] + 40) & (sr[..., 2] > 180) & (sr[..., 0] < 190)
    land = (dist > 38) & ~shelf
    land = np.asarray(Image.fromarray((land * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5))) > 127
    col = np.asarray(bm).astype(float)
    ice = (col.min(axis=-1) > 150)
    arid = sr * np.array([0.62, 0.52, 0.38])           # relief shading, recoloured to dry Triassic land
    col = np.where(ice[..., None], arid, col)

    LON, LAT = lonlat_grid(W, H)
    lo, la = np.degrees(LON), np.degrees(LAT)
    reg = regions(lo, la)
    xyz = to_xyz(LON, LAT)
    out = np.zeros((H, W, 3))
    cov = np.zeros((H, W))
    moves = dict(MOVES)
    if extra:
        moves.update(extra)
    for name, m in reg.items():
        sel = m & land
        v = xyz[sel]
        for R in moves[name]:
            v = v @ R.T
        lon2, lat2 = to_lonlat(v)
        x = ((np.degrees(lon2) + 180) / 360 * W).astype(int) % W
        y = np.clip(((90 - np.degrees(lat2)) / 180 * H).astype(int), 0, H - 1)
        np.add.at(out, (y, x), col[sel])
        np.add.at(cov, (y, x), 1)
    filled = cov > 0
    out[filled] /= cov[filled][:, None]
    # close the small holes left by splatting
    m8 = Image.fromarray((filled * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
    mask = np.asarray(m8) > 127
    blur = np.asarray(Image.fromarray(out.astype(np.uint8)).filter(ImageFilter.MaxFilter(5))).astype(float)
    landcol = np.where(filled[..., None], out, blur)
    # ocean: deep Blue-Marble navy with a lighter shelf around the coasts
    rng = np.random.default_rng(3)
    deep = np.array([8, 22, 60.0]) * (0.9 + 0.2 * rng.random((H, W, 1)))
    near = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14))).astype(float) / 255
    shelfc = np.array([30, 80, 120.0])
    oc = deep + (shelfc - deep) * np.clip(near * 1.6, 0, 1)[..., None]
    img = np.where(mask[..., None], landcol, oc)
    soft = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    soft.save(out_path)
    if preview:
        soft.resize((1000, 500)).save(preview)


if __name__ == "__main__":
    pv = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
    build(sys.argv[1], sys.argv[2], sys.argv[3], pv)
