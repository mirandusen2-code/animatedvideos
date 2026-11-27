"""Blender scene for "Grapes in a microwave make plasma" (Cycles, posed per frame). 1 unit = 1 inch.

Sets (only the active one is rendered):
  mw    inside a microwave oven: glass turntable, two grapes touching that burst into a plasma fireball (frame 0 / loop),
        and two water beads that do the same
  lab   a dark navy studio: light squeezed into a tiny spot, a 5-inch microwave, the wave shrinking in water,
        cut-away grapes with the wave bouncing inside, the hotspot next to a pinhead
  zoom  the hotspot magnified: salt ions with electrons that get ripped off, then the plasma flash

Usage: python3 scene.py <out_dir> [--frames a,b,c | --range a b] [--res 1080x1920] [--quality 1.0]
"""
import bpy  # noqa: I001  (bpy must be imported before bmesh)
import bmesh
import math
import os
import sys

import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timeline as T  # noqa: E402
import geo as G  # noqa: E402

args = sys.argv[1:]
OUT = args[0]
FRAMES = list(range(T.NFRAMES))
if "--frames" in args:
    FRAMES = [int(v) for v in args[args.index("--frames") + 1].split(",")]
if "--range" in args:
    i = args.index("--range")
    FRAMES = list(range(int(args[i + 1]), min(T.NFRAMES, int(args[i + 2]) + 1)))
RES = tuple(int(v) for v in args[args.index("--res") + 1].split("x")) if "--res" in args else (1080, 1920)
QUALITY = float(args[args.index("--quality") + 1]) if "--quality" in args else 1.0
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = T.FPS
col = scene.collection
V = Vector
SETS = {k: [] for k in ("mw", "lab", "zoom")}


# ================================================================= helpers
def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    return m, nt, nt.nodes["Material Output"]


def node(nt, kind, **inputs):
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def principled(name, base, rough=0.5, coat=0.0, bump=0.0, bump_scale=12.0):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=rough)
    p.inputs["Base Color"].default_value = (*base, 1)
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Coat Roughness"].default_value = 0.1
    p.inputs["Specular IOR Level"].default_value = 0.3
    if bump:
        tc = node(nt, "ShaderNodeTexCoord")
        nz = node(nt, "ShaderNodeTexNoise", Scale=bump_scale, Detail=3.0)
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        bp = node(nt, "ShaderNodeBump", Strength=bump, Distance=0.05)
        nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m, p


def emit_mat(name, color, strength):
    m, nt, out = new_mat(name)
    em = node(nt, "ShaderNodeEmission", Color=(*color, 1), Strength=strength)
    nt.links.new(em.outputs[0], out.inputs[0])
    return m, em.inputs["Strength"]


NOISE_W = []                                   # animated 4D-noise 'time' sockets (turbulent glow)


def glow_mat(name, color, strength, alpha=1.0, edge=6.0, turb=0.0):
    """Emission that fades towards the silhouette (a soft glow, not a hard disc). Returns (mat, alpha, strength)."""
    m, nt, out = new_mat(name)
    em = node(nt, "ShaderNodeEmission", Color=(*color, 1), Strength=strength)
    if turb:
        tc = node(nt, "ShaderNodeTexCoord")
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        nz.inputs["Scale"].default_value = 2.2
        nz.inputs["Detail"].default_value = 4.0
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        NOISE_W.append(nz.inputs["W"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.3, 0.7
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1 - turb, 1 + turb
        nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
        st = nt.nodes.new("ShaderNodeValue")
        st.outputs[0].default_value = strength
        mul_s = nt.nodes.new("ShaderNodeMath")
        mul_s.operation = "MULTIPLY"
        nt.links.new(st.outputs[0], mul_s.inputs[0])
        nt.links.new(mr.outputs[0], mul_s.inputs[1])
        nt.links.new(mul_s.outputs[0], em.inputs["Strength"])
        em_strength = st.outputs[0]
    else:
        em_strength = em.inputs["Strength"]
    tr = node(nt, "ShaderNodeBsdfTransparent")
    lw = node(nt, "ShaderNodeLayerWeight", Blend=0.5)
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], inv.inputs[1])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = edge
    nt.links.new(inv.outputs[0], pw.inputs[0])
    a = nt.nodes.new("ShaderNodeValue")
    a.outputs[0].default_value = alpha
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(a.outputs[0], mul.inputs[0])
    nt.links.new(pw.outputs[0], mul.inputs[1])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(mul.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m, a.outputs[0], em_strength


def obj_from(name, verts, faces, mat, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(np.asarray(verts).tolist(), [], faces)
    if smooth:
        me.shade_smooth()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(mat)
    col.objects.link(o)
    return o


def puts(o, s):
    SETS[s].append(o)
    return o


def ico_vf(sub):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    bm.verts.index_update()
    vv = np.array([x.co[:] for x in bm.verts])
    ff = [[x.index for x in f.verts] for f in bm.faces]
    bm.free()
    return vv, ff


def uv_vf(u, v):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    bm.verts.index_update()
    vv = np.array([x.co[:] for x in bm.verts])
    ff = [[x.index for x in f.verts] for f in bm.faces]
    bm.free()
    return vv, ff


class Dyn:
    """A mesh object whose vertex positions are rewritten every frame."""
    def __init__(self, name, verts, faces, mat, sets=("mw",), smooth=True):
        self.o = obj_from(name, verts, faces, mat, smooth)
        self.n = len(verts)
        for s in sets:
            SETS[s].append(self.o)

    def set(self, verts):
        v = np.asarray(verts, np.float32).reshape(-1)
        self.o.data.vertices.foreach_set("co", v)
        self.o.data.update()


def rand_dirs(n, g):
    d = g.normal(0, 1, (n, 3))
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def rodrigues(ax, ang):
    ax = np.asarray(ax, float)
    ang = np.asarray(ang, float)
    K = np.zeros((len(ax), 3, 3))
    K[:, 0, 1], K[:, 0, 2], K[:, 1, 2] = -ax[:, 2], ax[:, 1], -ax[:, 0]
    K[:, 1, 0], K[:, 2, 0], K[:, 2, 1] = ax[:, 2], -ax[:, 1], ax[:, 0]
    s, c = np.sin(ang)[:, None, None], np.cos(ang)[:, None, None]
    return np.eye(3)[None] + s * K + (1 - c) * (K @ K)


def rotz(p, ang, centre=(0, 0, 0)):
    c, s = math.cos(ang), math.sin(ang)
    q = np.asarray(p, float) - centre
    return np.stack([c * q[..., 0] - s * q[..., 1], s * q[..., 0] + c * q[..., 1], q[..., 2]], -1) + centre


TET = np.array([(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)], float) / math.sqrt(3)
TETF = [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]]


class Burst:
    """Pieces flying out of the burst: p(a) = p0 + v0 (1 - e^-ka)/k - g a^2/2."""
    def __init__(self, name, n, sets, seed, mat, size=(0.02, 0.06), shape="tet", stretch=1.0):
        g = np.random.default_rng(seed)
        self.g, self.n = g, n
        if shape == "tet":
            L = np.repeat(TET[None] * 1.0, n, 0) * g.uniform(*size, (n, 1, 1))
            L[:, :, 2] *= stretch
            f = [[k * 4 + a for a in tri] for k in range(n) for tri in TETF]
        elif shape == "drop":
            sv, sf = ico_vf(1)
            L = np.repeat(sv[None], n, 0) * g.uniform(*size, (n, 1, 1)) * np.array([1.0, 1.0, 1.25])
            f = [[k * len(sv) + a for a in tri] for k in range(n) for tri in sf]
        else:                                                   # flat irregular flakes
            L = np.zeros((n, 4, 3))
            for k in range(n):
                s = g.uniform(*size)
                a = np.sort(g.uniform(0, 2 * math.pi, 4))
                rr = s * g.uniform(0.5, 1.0, 4)
                L[k, :, 0], L[k, :, 1] = rr * np.cos(a), rr * np.sin(a)
                L[k, :, 2] = g.uniform(-0.15, 0.15, 4) * s
            f = [[k * 4 + 0, k * 4 + 1, k * 4 + 2], [k * 4 + 0, k * 4 + 2, k * 4 + 3]]
            f = [[k * 4 + 0, k * 4 + 1, k * 4 + 2] for k in range(n)] + [[k * 4 + 0, k * 4 + 2, k * 4 + 3]
                                                                          for k in range(n)]
        self.L = L
        self.dyn = Dyn(name, np.zeros((n * L.shape[1], 3)), f, mat, sets=sets, smooth=(shape == "drop"))
        self.ax = rand_dirs(n, g)
        self.w = g.uniform(3.0, 12.0, n) * g.choice([-1, 1], n)
        self.ph = g.uniform(0, 6.28, n)
        self.R0 = rodrigues(rand_dirs(n, g), g.uniform(0, 6.28, n))

    def emit(self, p0, v0, t0, k, grav):
        self.p0, self.v0, self.t0 = np.asarray(p0, float), np.asarray(v0, float), np.asarray(t0, float)
        self.k = np.asarray(k, float) * np.ones(self.n)
        self.grav = grav

    def positions(self, te):
        a = np.maximum(0.0, te - self.t0)
        k = self.k
        p = self.p0 + self.v0 * ((1 - np.exp(-k * a)) / k)[:, None]
        p[:, 2] -= 0.5 * self.grav * a * a
        return p

    def pose(self, te, life=None):
        a = np.maximum(0.0, te - self.t0)
        on = (te >= self.t0).astype(float)
        if life is not None:
            on = on * np.clip((life - a) / 0.15, 0, 1)
        p = self.positions(te)
        R = rodrigues(self.ax, self.w * a + self.ph) @ self.R0
        sc = on * np.minimum(1.0, 0.3 + a * 20.0)
        v = np.einsum("kij,kvj->kvi", R, self.L * sc[:, None, None]) + p[:, None, :]
        self.dyn.set(v)


def tube_verts(pts, r, seg=8):
    pts = np.asarray(pts, float)
    d = np.gradient(pts, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    ref = np.array([0.0, 1.0, 0.0])
    a = np.cross(d, ref)
    bad = np.linalg.norm(a, axis=1) < 1e-3
    a[bad] = np.cross(d[bad], [1.0, 0.0, 0.0])
    a /= np.linalg.norm(a, axis=1, keepdims=True) + 1e-9
    b = np.cross(d, a)
    ang = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    rr = np.broadcast_to(np.asarray(r, float), (len(pts),))
    ring = np.cos(ang)[None, :, None] * a[:, None, :] + np.sin(ang)[None, :, None] * b[:, None, :]
    v = (pts[:, None, :] + rr[:, None, None] * ring).reshape(-1, 3)
    caps = np.array([pts[0] - d[0] * rr[0] * 0.8, pts[-1] + d[-1] * rr[-1] * 0.8])
    return np.concatenate([v, caps])


def tube_faces(n, seg=8):
    f = []
    for i in range(n - 1):
        for k in range(seg):
            f.append([i * seg + k, i * seg + (k + 1) % seg, (i + 1) * seg + (k + 1) % seg, (i + 1) * seg + k])
    c0, c1 = n * seg, n * seg + 1
    for k in range(seg):
        f.append([(k + 1) % seg, k, c0])
        f.append([(n - 1) * seg + k, (n - 1) * seg + (k + 1) % seg, c1])
    return f


class Line:
    """A glowing tube along a polyline that can be redrawn every frame (fixed point count)."""
    def __init__(self, name, n, mat, sets, seg=8):
        self.npt, self.seg = n, seg
        self.dyn = Dyn(name, np.zeros((n * seg + 2, 3)), tube_faces(n, seg), mat, sets=sets, smooth=True)

    def set(self, pts, r):
        self.dyn.set(tube_verts(pts, r, self.seg))
        self.dyn.o.hide_render = False

    def hide(self):
        self.dyn.o.hide_render = True


def resample(pts, n, upto=1.0):
    """n points along a polyline, from its start to fraction 'upto' of its length."""
    pts = np.asarray(pts, float)
    cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    s = np.linspace(0, cum[-1] * max(upto, 1e-4), n)
    return np.stack([np.interp(s, cum, pts[:, k]) for k in range(3)], -1)


def box_vf(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1),
         (x0, y1, z1)]
    f = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return np.array(v, float), f


def box(name, lo, hi, mat, s):
    v, f = box_vf(lo, hi)
    return puts(obj_from(name, v, f, mat, smooth=False), s)


def light(name, kind, loc, target, energy, size, color, sets):
    ld = bpy.data.lights.new(name, kind)
    ld.energy, ld.color = energy, color
    if kind == "AREA":
        ld.size, ld.shape = size, "DISK"
    else:
        ld.shadow_soft_size = size
    o = bpy.data.objects.new(name, ld)
    o.location = loc
    if target is not None:
        o.rotation_euler = (V(loc) - V(target)).to_track_quat("Z", "Y").to_euler()
    col.objects.link(o)
    for s in sets:
        SETS[s].append(o)
    return o


def no_shadow(o):
    o.visible_shadow = False
    return o


# ================================================================= world
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
_wbg = wnt.nodes["Background"]
WCOL = _wbg.inputs["Color"]
WSTR = _wbg.inputs["Strength"]
WORLD = {"mw": ((0.02, 0.018, 0.016), 1.0), "lab": ((0.010, 0.016, 0.040), 1.0), "zoom": ((0.006, 0.006, 0.02), 1.0)}

# ================================================================= materials
paint_m, _ = principled("OvenPaint", (0.36, 0.37, 0.37), rough=0.35, bump=0.02, bump_scale=60)
floor_m, _ = principled("OvenFloor", (0.30, 0.31, 0.31), rough=0.45)
mica_m, _ = principled("Mica", (0.62, 0.52, 0.36), rough=0.6)
front_m, _ = principled("OvenFront", (0.03, 0.03, 0.035), rough=0.25, coat=0.6)
chrome_m, _chr = principled("Chrome", (0.8, 0.8, 0.82), rough=0.15)
_chr.inputs["Metallic"].default_value = 1.0
counter_m, _ = principled("Counter", (0.42, 0.40, 0.37), rough=0.5, bump=0.05, bump_scale=30)
grill_m, GRILL_S = emit_mat("LampGrill", (1.0, 0.78, 0.48), 3.0)
ttglass_m, _ttg = principled("TurntableGlass", (0.86, 0.93, 0.9), rough=0.14)
_ttg.inputs["Transmission Weight"].default_value = 1.0
_ttg.inputs["IOR"].default_value = 1.5
_ttg.inputs["Specular IOR Level"].default_value = 0.5
hub_m, _ = principled("Hub", (0.08, 0.08, 0.08), rough=0.6)


def grape_mat(name):
    """Deep red-purple grape with a dusty bloom; 'burn' (vertex attribute) scorches it and glows when hot."""
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.32)
    p.inputs["Subsurface Weight"].default_value = 0.35
    p.inputs["Subsurface Radius"].default_value = (0.9, 0.12, 0.3)
    p.inputs["Subsurface Scale"].default_value = 0.12
    p.inputs["Coat Weight"].default_value = 0.35
    p.inputs["Coat Roughness"].default_value = 0.25
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=7.0, Detail=4.0)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    rp = nt.nodes.new("ShaderNodeValToRGB")
    cr = rp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.35, (0.20, 0.02, 0.09, 1)
    cr.elements[1].position, cr.elements[1].color = 0.75, (0.42, 0.10, 0.26, 1)
    nt.links.new(nz.outputs["Fac"], rp.inputs[0])
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "burn"
    mixc = nt.nodes.new("ShaderNodeMix")
    mixc.data_type = "RGBA"
    nt.links.new(at.outputs["Fac"], mixc.inputs[0])
    nt.links.new(rp.outputs[0], mixc.inputs[6])
    mixc.inputs[7].default_value = (0.03, 0.015, 0.01, 1)
    nt.links.new(mixc.outputs[2], p.inputs["Base Color"])
    p.inputs["Emission Color"].default_value = (1.0, 0.42, 0.08, 1)
    hot = nt.nodes.new("ShaderNodeValue")
    hot.outputs[0].default_value = 0.0
    em = nt.nodes.new("ShaderNodeMath")
    em.operation = "MULTIPLY"
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 3.0
    nt.links.new(at.outputs["Fac"], pw.inputs[0])
    nt.links.new(pw.outputs[0], em.inputs[0])
    nt.links.new(hot.outputs[0], em.inputs[1])
    nt.links.new(em.outputs[0], p.inputs["Emission Strength"])
    bp = node(nt, "ShaderNodeBump", Strength=0.04, Distance=0.02)
    nz2 = node(nt, "ShaderNodeTexNoise", Scale=40.0, Detail=2.0)
    nt.links.new(tc.outputs["Object"], nz2.inputs["Vector"])
    nt.links.new(nz2.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m, hot.outputs[0]


grape_m, GRAPE_HOT = grape_mat("Grape")
flesh_m, _fl = principled("GrapeFlesh", (0.26, 0.40, 0.14), rough=0.25)
_fl.inputs["Subsurface Weight"].default_value = 0.5
_fl.inputs["Subsurface Radius"].default_value = (0.5, 0.6, 0.3)
_fl.inputs["Subsurface Scale"].default_value = 0.1
_fl.inputs["Emission Color"].default_value = (1.0, 0.55, 0.2, 1)
FLESH_GLOW = _fl.inputs["Emission Strength"]
bead_m, _bd = principled("WaterBead", (0.25, 0.75, 0.95), rough=0.08)
_bd.inputs["Transmission Weight"].default_value = 0.85
_bd.inputs["Subsurface Weight"].default_value = 0.3
_bd.inputs["Subsurface Radius"].default_value = (0.2, 0.6, 0.9)
_bd.inputs["Subsurface Scale"].default_value = 0.2
_bd.inputs["IOR"].default_value = 1.34
_bd.inputs["Specular IOR Level"].default_value = 0.6
drop_m, _dr = principled("Juice", (0.38, 0.03, 0.10), rough=0.08, coat=0.6)
skin_m, _ = principled("SkinFlake", (0.16, 0.02, 0.07), rough=0.4, coat=0.3)
spark_m, SPARK_S = emit_mat("Spark", (1.0, 0.5, 0.12), 8.0)
arc_m, ARC_S = emit_mat("Arc", (0.78, 0.72, 1.0), 30.0)
hot_m, HOT_A, HOT_S = glow_mat("Hotspot", (1.0, 0.92, 0.8), 40.0, 1.0, 2.0)
core_m, _ca, CORE_S = glow_mat("PlasmaCore", (1.0, 0.78, 0.40), 5.0, 1.0, 1.4, turb=0.4)
mid_m, MID_A, MID_S = glow_mat("PlasmaMid", (1.0, 0.18, 0.0), 1.4, 1.0, 0.9, turb=0.6)
out_m, OUT_A, OUT_S = glow_mat("PlasmaOuter", (1.0, 0.10, 0.55), 1.2, 0.22, 2.0, turb=0.5)

# lab
cyc_m, _cyc = principled("Cyc", (0.028, 0.045, 0.10), rough=0.55)
wave_m, WAVE_S = emit_mat("Wave", (0.25, 0.85, 1.0), 8.0)
ray_m, RAY_S = emit_mat("Ray", (0.35, 0.9, 1.0), 9.0)
ruler_m, _ = emit_mat("Ruler", (0.95, 0.95, 0.95), 3.0)
water_m, _wm = principled("WaterBlock", (0.2, 0.55, 0.95), rough=0.15)
_wm.inputs["Alpha"].default_value = 0.28
edge_m, _ = emit_mat("WaterEdge", (0.45, 0.8, 1.0), 4.0)
pin_m, _pn = principled("PinSteel", (0.85, 0.85, 0.88), rough=0.18)
_pn.inputs["Metallic"].default_value = 1.0
pinhead_m, _ = principled("PinHead", (0.85, 0.06, 0.05), rough=0.2, coat=0.8)
# zoom
ion_m, _ion = principled("Ion", (1.0, 0.55, 0.12), rough=0.3, coat=0.5)
_ion.inputs["Emission Color"].default_value = (1.0, 0.45, 0.1, 1)
ION_GLOW = _ion.inputs["Emission Strength"]
elec_m, ELEC_S = emit_mat("Electron", (0.25, 0.65, 1.0), 5.0)
orbit_m, ORBIT_A, ORBIT_S = glow_mat("Orbit", (0.35, 0.7, 1.0), 2.0, 0.5, 1.0)


# ================================================================= fireball (three layered, noise-displaced shells)
class Fireball:
    def __init__(self, name, sets, seed):
        g = np.random.default_rng(seed)
        self.u, f = ico_vf(3)
        self.layers = [Dyn(f"{name}{k}", self.u * 0.1, f, m, sets=sets, smooth=True)
                       for k, m in enumerate((core_m, mid_m, out_m))]
        for d in self.layers:
            no_shadow(d.o)
        self.dirs = rand_dirs(7, g)
        self.freq = g.uniform(2.0, 4.5, 7)
        self.w = g.uniform(6.0, 14.0, 7) * g.choice([-1, 1], 7)
        self.ph = g.uniform(0, 6.28, 7)
        self.amp = g.uniform(0.025, 0.06, 7)

    def pose(self, centre, radius, te, rise=0.35):
        if radius <= 1e-3:
            for d in self.layers:
                d.o.hide_render = True
            return
        for k, (d, sc) in enumerate(zip(self.layers, (0.36, 0.80, 1.0))):
            dd = self.u @ self.dirs.T
            n = (self.amp[None] * (1.0 + 0.6 * k) * np.sin(self.freq[None] * dd * (1 + 0.4 * k)
                                                            + self.w[None] * te + self.ph[None] + k)).sum(1)
            r = radius * sc * (1 + n)
            v = self.u * r[:, None]
            v[:, 2] = v[:, 2] * 1.18 + rise * radius * sc * np.clip(self.u[:, 2], 0, 1) ** 2   # flame-like top
            d.set(v + centre)
            d.o.hide_render = False


# ================================================================= MW set: the microwave oven
X, Y, Z = G.MW_X, G.MW_Y, G.MW_Z
O = G.MW_O
_walls = [
    ("OvenFloor", [(-X, -Y, 0), (X, -Y, 0), (X, Y, 0), (-X, Y, 0)], floor_m),
    ("OvenCeil", [(-X, -Y, Z), (-X, Y, Z), (X, Y, Z), (X, -Y, Z)], paint_m),
    ("OvenBack", [(-X, Y, 0), (X, Y, 0), (X, Y, Z), (-X, Y, Z)], paint_m),
    ("OvenLeft", [(-X, -Y, 0), (-X, Y, 0), (-X, Y, Z), (-X, -Y, Z)], paint_m),
    ("OvenRight", [(X, -Y, 0), (X, -Y, Z), (X, Y, Z), (X, Y, 0)], paint_m),
]
for nm, vv, mm in _walls:
    puts(obj_from(nm, np.array(vv) + O, [[0, 1, 2, 3]], mm, smooth=False), "mw")
# front panel with the opening (the door is open), the counter below it and a wall behind the camera side
_fx0, _fx1, _fz0, _fz1 = -X - 4.5, X + 9.5, -3.0, Z + 3.5
for lo, hi in [((_fx0, -Y - 1.2, _fz0), (_fx1, -Y, 0.0)), ((_fx0, -Y - 1.2, Z), (_fx1, -Y, _fz1)),
               ((_fx0, -Y - 1.2, 0.0), (-X, -Y, Z)), ((X, -Y - 1.2, 0.0), (_fx1, -Y, Z))]:
    box("OvenFront", np.array(lo) + O, np.array(hi) + O, front_m, "mw")
box("FrontTrim", np.array((-X - 0.25, -Y - 1.3, -0.25)) + O, np.array((X + 0.25, -Y - 1.2, 0.0)) + O, chrome_m, "mw")
box("Counter", np.array((-60, -40, _fz0 - 0.6)) + O, np.array((60, Y + 8, _fz0)) + O, counter_m, "mw")
box("Mica", np.array((X - 0.02, -1.6, 4.6)) + O, np.array((X, 1.6, 7.6)) + O, mica_m, "mw")
box("Grill", np.array((-X, 2.6, 6.4)) + O, np.array((-X + 0.02, 5.0, 8.2)) + O, grill_m, "mw")
# glass turntable on a dark roller ring
_seg = 96
_a = np.linspace(0, 2 * math.pi, _seg, endpoint=False)
_prof = [(0.0, G.TT_Z - 0.18), (G.TT_R - 0.2, G.TT_Z - 0.18), (G.TT_R, G.TT_Z - 0.05), (G.TT_R, G.TT_Z + 0.12),
         (G.TT_R - 0.18, G.TT_Z + 0.12), (G.TT_R - 0.35, G.TT_Z), (0.0, G.TT_Z)]
_tv, _tf = [], []
for j, (rr, zz) in enumerate(_prof):
    for k in range(_seg):
        _tv.append((rr * math.cos(_a[k]), rr * math.sin(_a[k]), zz))
for j in range(len(_prof) - 1):
    for k in range(_seg):
        k1 = (k + 1) % _seg
        _tf.append([j * _seg + k, j * _seg + k1, (j + 1) * _seg + k1, (j + 1) * _seg + k])
TT = puts(obj_from("Turntable", np.array(_tv) + O, _tf, ttglass_m, smooth=True), "mw")
_rv, _rf = [], []
for k in range(_seg):
    for j, (rr, zz) in enumerate([(3.0, 0.0), (3.0, 0.5), (3.4, 0.5), (3.4, 0.0)]):
        _rv.append((rr * math.cos(_a[k]), rr * math.sin(_a[k]), zz))
for k in range(_seg):
    k1 = (k + 1) % _seg
    for j in range(3):
        _rf.append([k * 4 + j, k1 * 4 + j, k1 * 4 + j + 1, k * 4 + j + 1])
puts(obj_from("Roller", np.array(_rv) + O, _rf, hub_m, smooth=False), "mw")

# the two grapes (deformable: a scorched crater opens at the touching point when they burst)
_gv, _gf = uv_vf(64, 40)
_gv = _gv[:, [0, 2, 1]] * np.array([1, 1, 1])               # poles along Y (the grape lies on its side)
GRAPE_L = _gv * np.array(G.GR_A)
GRAPES = []
for k in range(2):
    d = Dyn(f"Grape{k}", GRAPE_L, _gf, grape_m, sets=("mw",), smooth=True)
    d.o.data.attributes.new("burn", "FLOAT", "POINT")
    GRAPES.append(d)
_gdir = _gv / np.linalg.norm(_gv, axis=1, keepdims=True)
# water beads (same place, clear hydrogel spheres)
_bv, _bf = uv_vf(48, 32)
BEADS = []
for k, c in enumerate(G.grape_centres(O, G.TT_Z + 0.42)):
    BEADS.append(Dyn(f"Bead{k}", _bv * 0.42 + c, _bf, bead_m, sets=("mw",), smooth=True))
BEAD_C = [c.copy() for c in G.grape_centres(O, G.TT_Z + 0.42)]

FB = Fireball("Plasma", ("mw",), 5)
HOT = puts(obj_from("HotSpot", ico_vf(3)[0] * 0.05, ico_vf(3)[1], hot_m), "mw")
no_shadow(HOT)
PL = light("PlasmaLight", "POINT", (0, 0, 2), None, 0.0, 0.3, (1.0, 0.55, 0.28), ("mw",))
LAMP = light("OvenLamp", "AREA", tuple(O + np.array([-X + 1.2, 3.8, Z - 0.4])), tuple(O + np.array([0, 0, 0.8])),
             420.0, 3.0, (1.0, 0.8, 0.58), ("mw",))
FILL = light("OvenFill", "AREA", tuple(O + np.array([-3.0, -16.0, 6.0])), tuple(O + np.array([0, 0, 1.0])),
             900.0, 8.0, (0.75, 0.85, 1.0), ("mw",))
NARC = 5
ARCS = [Line(f"Arc{k}", 12, arc_m, ("mw",), seg=5) for k in range(NARC)]
for a_ in ARCS:
    no_shadow(a_.dyn.o)

# flying pieces (all from the touching point)
_gs = np.random.default_rng(41)
SPARKS = Burst("Sparks", 200, ("mw",), 42, spark_m, size=(0.005, 0.011), stretch=3.0)
DROPS = Burst("Juice", 90, ("mw",), 43, drop_m, size=(0.03, 0.08), shape="drop")
FLAKES = Burst("Flakes", 80, ("mw",), 44, skin_m, size=(0.05, 0.14), shape="flake")
for b in (SPARKS,):
    no_shadow(b.dyn.o)
_cam_dir = T.CAM0_LOC - np.array(T.CT)
_cam_dir = _cam_dir / np.linalg.norm(_cam_dir)


def _emit(b, n_cam, speed, spread, seed, t_span=0.05, up=1.2, grav=12.0, k=(0.6, 1.6)):
    g = np.random.default_rng(seed)
    n = b.n
    d = rand_dirs(n, g)
    towards = g.uniform(0, 1, n) < n_cam
    d[towards] = _cam_dir + g.normal(0, spread, (towards.sum(), 3))
    d[:, 2] = np.abs(d[:, 2]) * 0.6 + 0.15
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    v = d * g.uniform(*speed, n)[:, None] + np.array([0, 0, up])
    p0 = np.array(T.CT) + g.normal(0, 0.03, (n, 3))
    b.emit(p0, v, g.uniform(0, t_span, n), g.uniform(*k, n), grav)


_emit(SPARKS, 0.35, (2.0, 9.0), 0.35, 51, t_span=0.9, up=1.5, grav=6.0)
_emit(DROPS, 0.55, (1.2, 4.2), 0.45, 52, t_span=0.08, up=0.8, grav=14.0)
_emit(FLAKES, 0.6, (1.0, 3.6), 0.5, 53, t_span=0.08, up=0.6, grav=5.0)


def pose_grapes(te, ang, hot):
    """te: time since the burst (None = no burst in this shot); ang: turntable angle."""
    crat = 0.0 if te is None or te < 0 else 0.17 * (1 - math.exp(-te / 0.07))
    scorch = 0.0 if te is None else T.smoother((te + 1.3) / 1.3)
    for k, (d, c) in enumerate(zip(GRAPES, G.grape_centres(O))):
        side = 1.0 if k == 0 else -1.0                         # the touching side faces +x for grape 0
        dd = _gdir[:, 0] * side
        wgt = np.clip((dd - math.cos(math.radians(48))) / (1 - math.cos(math.radians(48))), 0, 1)
        v = GRAPE_L.copy()
        v -= _gdir * (crat * wgt ** 1.5)[:, None] * np.array([1.0, 0.6, 0.6])
        v = rotz(v + c, ang, centre=np.array(T.CT))
        d.set(v)
        burn = np.clip(wgt ** 0.7 * scorch * 1.2, 0, 1)
        d.o.data.attributes["burn"].data.foreach_set("value", burn.astype(np.float32))
        d.o.data.update()
    GRAPE_HOT.default_value = hot


def pose_mw(te, beads, ang):
    for d in GRAPES:
        d.o.hide_render = beads
    for d in BEADS:
        d.o.hide_render = not beads
    TT.rotation_euler = (0, 0, ang)
    if not beads:
        pose_grapes(te, ang, 6.0 * (0.0 if te is None else T.smoother((te + 0.6) / 0.6)))
    else:
        for d, c in zip(BEADS, BEAD_C):
            d.set(rotz(_bv * 0.42 + c, ang, centre=np.array(T.CT)))
    ct = np.array(T.CT) + (np.array([0, 0, -0.0]) if not beads else np.array([0, 0, 0.02]))
    # pre-burst: hotspot glow + arcs flicker at the touching point
    pre = 0.0 if te is None else T.smoother((te + 1.5) / 1.5) * (1.0 if te < 0.05 else math.exp(-(te - 0.05) / 0.1))
    HOT.hide_render = pre < 0.02
    if pre >= 0.02:
        s = 0.35 + 1.2 * pre + 0.25 * math.sin(te * 47) * pre
        HOT.scale = (s, s, s)
        HOT.location = ct
        HOT_S.default_value = 25.0 + 40.0 * pre
    g = np.random.default_rng(int((te if te is not None else 0) * 30 * 7) % 100000 + 3)
    for k, a_ in enumerate(ARCS):
        if te is None or pre < 0.25 or g.uniform() > 0.35 + 0.6 * pre:
            a_.hide()
            continue
        d = rand_dirs(1, g)[0]
        d[2] = abs(d[2]) * 0.8 + 0.2
        ln = g.uniform(0.15, 0.45) * (0.5 + pre)
        pts = ct + np.outer(np.linspace(0, 1, 12), d * ln) + np.concatenate([[np.zeros(3)], g.normal(0, 0.03, (10, 3)),
                                                                            [np.zeros(3)]])
        a_.set(pts, 0.006)
    # the fireball
    if te is None or te < 0:
        FB.pose(ct, 0.0, 0.0)
        PL.data.energy = 0.0 if te is None else 4.0 * pre
        PL.location = tuple(ct + np.array([0, 0, 0.2]))
        for b in (SPARKS, DROPS, FLAKES):
            b.dyn.o.hide_render = True
        return
    grow = 1 - math.exp(-te / 0.06)
    rad = (0.42 + 0.7 * min(te, 3.0) / 3.0) * grow * (1 + 0.06 * math.sin(te * 31) + 0.04 * math.sin(te * 53))
    rise = 0.45 * grow + 0.5 * min(te, 0.6) + 1.05 * max(0.0, min(te, 4.0) - 0.6)                  # the hot ball floats upward (buoyant plasma)
    cen = ct + np.array([0, 0, rise])
    FB.pose(cen, rad, te)
    PL.location = tuple(cen)
    PL.data.energy = 120.0 * grow * (1 + 0.15 * math.sin(te * 41))
    CORE_S.default_value = 5.0 * (1 + 0.2 * math.sin(te * 37))
    SPARKS.dyn.o.hide_render = False
    SPARKS.pose(te, life=0.9)
    for b in (DROPS, FLAKES):
        b.dyn.o.hide_render = beads
        if not beads:
            b.pose(te)


# ================================================================= LAB set: dark navy studio
LO = G.LAB_O
_cw = []
_cf = []
_ny = 30
for j in range(_ny + 1):                       # floor that sweeps up into the back wall (a seamless cyc)
    u = j / _ny
    if u < 0.6:
        y, z = -40 + (u / 0.6) * 52, 0.0
    else:
        a = (u - 0.6) / 0.4 * (math.pi / 2)
        y, z = 12 + 8 * math.sin(a), 8 - 8 * math.cos(a)
    for x in (-60.0, 60.0):
        _cw.append((x, y, z))
for j in range(_ny):
    _cf.append([j * 2, j * 2 + 1, j * 2 + 3, j * 2 + 2])
_cv = np.array(_cw)
_cv[-2:, 2] += 30
puts(obj_from("Cyc", _cv + LO, _cf, cyc_m, smooth=True), "lab")
light("LabKey", "AREA", tuple(LO + np.array([-8, -14, 14])), tuple(LO + np.array([0, 0, 1.5])), 2600.0, 10.0,
      (1.0, 0.95, 0.9), ("lab",))
light("LabRim", "AREA", tuple(LO + np.array([9, 9, 7])), tuple(LO + np.array([0, 2, 1.0])), 1400.0, 6.0,
      (0.55, 0.7, 1.0), ("lab",))

LG = LO + G.LAB_GRAPES                         # lab grape pair (floor level)
LGC = G.grape_centres(LG, G.LAB_GZ)
LGP = np.array(T.GP)                           # their touching point
LAB_GRAPES = [puts(obj_from(f"LabGrape{k}", GRAPE_L + c, _gf, grape_m), "lab") for k, c in enumerate(LGC)]
for o in LAB_GRAPES:
    o.data.attributes.new("burn", "FLOAT", "POINT")
# cut-away halves (the back half of each grape + a flat cut face, so the wave inside can be seen)
_back = _gf
_hv = GRAPE_L.copy()
_hv[:, 1] = np.maximum(_hv[:, 1], 0.012)          # squash the front half onto the cut plane
CUT_GRAPES = [puts(obj_from(f"CutGrape{k}", _hv + c, _gf, grape_m), "lab") for k, c in enumerate(LGC)]
for o in CUT_GRAPES:
    o.data.attributes.new("burn", "FLOAT", "POINT")
_fa = np.linspace(0, 2 * math.pi, 96, endpoint=False)
_ff = [[k, (k + 1) % 96, 96] for k in range(96)]
CUT_FACES = []
for k, c in enumerate(LGC):
    vv = np.concatenate([np.stack([G.GR_A[0] * 0.92 * np.cos(_fa), np.full(96, -0.004), G.GR_A[2] * 0.92 * np.sin(_fa)],
                                  -1), [[0, -0.004, 0]]]) + c
    CUT_FACES.append(puts(obj_from(f"CutFace{k}", vv, _ff, flesh_m, smooth=False), "lab"))
RAYS = [Line(f"Ray{k}", 160, ray_m, ("lab",), seg=6) for k in range(2)]
HEADS = [puts(obj_from(f"RayHead{k}", ico_vf(2)[0] * 0.03, ico_vf(2)[1], hot_m), "lab") for k in range(2)]
for o in HEADS:
    no_shadow(o)
LHOT = puts(obj_from("LabHot", ico_vf(3)[0] * 0.02, ico_vf(3)[1], hot_m), "lab")
no_shadow(LHOT)
LPL = light("LabHotLight", "POINT", tuple(LGP), None, 0.0, 0.05, (1.0, 0.7, 0.45), ("lab",))

# waves
NWHY = 5
WHY_W = [Line(f"WhyWave{k}", 120, wave_m, ("lab",), seg=6) for k in range(NWHY)]
MAINW = Line("MainWave", 400, wave_m, ("lab",), seg=8)
RULER = Dyn("Ruler", np.zeros((24, 3)), [[q * 8 + a for a in f] for q in range(3) for f in box_vf((0, 0, 0), (1, 1, 1))[1]],
            ruler_m, sets=("lab",), smooth=False)
WATER = box("WaterBlock", LO + np.array([G.WATER_X0, -1.6, 0.0]), LO + np.array([G.WATER_X0 + 7.0, 1.6, 6.4]), water_m,
            "lab")
WATER.visible_shadow = False
_e = []
for (a, b) in [((0, 0, 0), (1, 0, 0)), ((0, 0, 1), (1, 0, 1)), ((0, 0, 0), (0, 0, 1)), ((1, 0, 0), (1, 0, 1)),
               ((0, 1, 1), (1, 1, 1)), ((0, 0, 1), (0, 1, 1)), ((1, 0, 1), (1, 1, 1))]:
    p0 = LO + np.array([G.WATER_X0, -1.6, 0.0]) + np.array(a) * np.array([7.0, 3.2, 6.4])
    p1 = LO + np.array([G.WATER_X0, -1.6, 0.0]) + np.array(b) * np.array([7.0, 3.2, 6.4])
    lo, hi = np.minimum(p0, p1) - 0.03, np.maximum(p0, p1) + 0.03
    _e.append(box("WaterEdge", lo, hi, edge_m, "lab"))
SIZE_GRAPE = puts(obj_from("SizeGrape", GRAPE_L, _gf, grape_m), "lab")
SIZE_GRAPE.data.attributes.new("burn", "FLOAT", "POINT")
SIZE_POS = LO + np.array([G.WATER_X0 + 2.5, -1.9, G.WAVE_Z + 1.12])
# the pin (for scale next to the hotspot)
PIN_E = bpy.data.objects.new("Pin", None)
col.objects.link(PIN_E)
_ph = puts(obj_from("PinHead", ico_vf(3)[0] * 0.04, ico_vf(3)[1], pinhead_m), "lab")
_ps = puts(obj_from("PinShaft", tube_verts(np.array([[0, 0, 0], [0.9, 0, 0]]), 0.009, 12), tube_faces(2, 12), pin_m),
           "lab")
_ph.parent = PIN_E
_ps.parent = PIN_E
PIN_PARTS = (_ph, _ps)


def wave_points(x0, x1, lam, amp, phase, z, y=0.0, n=400):
    return G.sine_path(x0, x1, lam, amp, phase, n, z, y)


def set_ruler(xa, xb, z, y=0.0, th=0.05, tick=0.35):
    parts = [((xa, y - th, z - th), (xb, y + th, z + th)), ((xa - th, y - th, z - tick), (xa + th, y + th, z + tick)),
             ((xb - th, y - th, z - tick), (xb + th, y + th, z + tick))]
    RULER.set(np.concatenate([box_vf(lo, hi)[0] for lo, hi in parts]))
    RULER.o.hide_render = False


def bounce_path(c, energy, pull):
    """The wave bouncing inside a cut grape (in the cut plane), pulled toward the touching point."""
    hp = G.ellipse_bounce(G.GR_A[0] * 0.84, G.GR_A[2] * 0.84, 14)
    pts = np.stack([hp[:, 0], np.full(len(hp), -0.03), hp[:, 1]], -1) + c
    tgt = LGP + np.array([0, -0.03, 0])
    w = pull * np.linspace(0.2, 1.0, len(pts))[:, None]
    return pts * (1 - w) + tgt * w


def pose_lab(t):
    i = T.shot_index(t)
    for o in LAB_GRAPES:
        o.hide_render = i not in (*T.S_WHY, T.S_WAVE, T.S_WATER)
    for o in CUT_GRAPES + CUT_FACES:
        o.hide_render = i not in (T.S_TRAP, T.S_TOUCH)
    for w in WHY_W:
        w.hide()
    MAINW.hide()
    RULER.o.hide_render = True
    WATER.hide_render = i != T.S_WATER
    for e in _e:
        e.hide_render = i != T.S_WATER
    SIZE_GRAPE.hide_render = True
    for r in RAYS:
        r.hide()
    for o in HEADS:
        o.hide_render = True
    for p in PIN_PARTS:
        p.hide_render = True
    LHOT.hide_render = True
    LPL.data.energy = 0.0
    FLESH_GLOW.default_value = 0.0
    WAVE_S.default_value = 8.0
    if i in T.S_WHY:                               # WHY: light squeezed into the touching point
        head = 0.25 + 0.75 * T.smoother((t - T.C2 + 0.1) / 1.2)
        for k, w in enumerate(WHY_W):
            sp = (k - (NWHY - 1) / 2) * 1.0
            x = np.linspace(-6.5, 0.0, 240)
            s = (x + 6.5) / 6.5
            z = sp * (1 - s) ** 1.4 + (0.16 * (1 - s) + 0.015) * np.sin(2 * math.pi * x / 1.1 - 9.0 * t + k)
            y = -0.25 * (1 - s) * k * 0.2
            pts = np.stack([x, y, z], -1) + LGP
            w.set(resample(pts, 120, head), 0.028)
        e = T.smoother((t - (T.C2 + 0.9)) / 0.6)
        if e > 0.01:
            LHOT.hide_render = False
            LHOT.location = tuple(LGP)
            sc = 0.6 + 1.6 * e + 0.15 * math.sin(t * 40) * e
            LHOT.scale = (sc, sc, sc)
            HOT_S.default_value = 30.0 + 30.0 * e
            LPL.data.energy = 3.0 * e
            LPL.location = tuple(LGP + np.array([0, -0.15, 0.05]))
    if i == T.S_WAVE:                              # one microwave, 5 inches long
        head = T.smoother((t - T.C3 + 0.15) / 0.8)
        x0 = LO[0] - 6.0
        ph = 1.6 * (t - T.C3)
        pts = wave_points(x0, x0 + 10.5, G.LAM_AIR, 1.1, ph, LO[2] + G.WAVE_Z, LO[1])
        MAINW.set(resample(pts, 400, head), 0.06)
        r = T.smoother((t - (T.T_5[0] - 0.2)) / 0.3)
        if r > 0.01:
            xa = x0 + G.LAM_AIR * (0.25 + ph / (2 * math.pi))          # one crest (it travels with the wave) ...
            set_ruler(xa, xa + G.LAM_AIR * r, LO[2] + G.WAVE_Z + 1.65, LO[1])     # ... to the next crest
    if i == T.S_WATER:                             # into water: it shrinks
        x0 = LO[0] - 6.0
        xw = LO[0] + G.WATER_X0
        head = T.smoother((t - T.C4) / 1.6)
        ph = 1.6 * (t - T.C3)
        p_air = wave_points(x0, xw, G.LAM_AIR, 1.1, ph, LO[2] + G.WAVE_Z, LO[1], 300)
        k_air = 2 * math.pi * (xw - x0) / G.LAM_AIR - ph            # phase at the boundary
        xx = np.linspace(xw, xw + 6.6, 700)
        zz = LO[2] + G.WAVE_Z + 0.32 * np.sin(k_air + 2 * math.pi * (xx - xw) / G.LAM_WATER) + \
            (1.1 - 0.32) * math.sin(k_air) * np.exp(-(xx - xw) / 0.25)
        p_w = np.stack([xx, np.full(len(xx), LO[1]), zz], -1)
        reach = 0.25 + 0.75 * head
        MAINW.set(resample(np.concatenate([p_air, p_w]), 400, 0.55 + 0.45 * head * reach), 0.06)
        g = T.smoother((t - (T.T_GSIZE[0] - 0.25)) / 0.3)
        r = T.smoother((t - (T.T_HALF[0] - 0.15)) / 0.3)
        if r > 0.01:
            xa = xw + G.LAM_WATER * (4.25 - (k_air / (2 * math.pi)) % 1.0)
            set_ruler(xa, xa + G.LAM_WATER * r, LO[2] + G.WAVE_Z + 0.62, LO[1] - 1.7, th=0.02, tick=0.12)
        if g > 0.01:
            SIZE_GRAPE.hide_render = False
            s = 0.6 * g * (1 + 0.15 * math.sin(min(1.0, g) * math.pi))
            SIZE_GRAPE.location = tuple(SIZE_POS)
            SIZE_GRAPE.scale = (s, s, s)
            SIZE_GRAPE.rotation_euler = (0, 0, math.radians(90))
    if i in (T.S_TRAP, T.S_TOUCH):                 # bouncing inside; then piling into the touching point
        if i == T.S_TRAP:
            prog = T.smoother((t - T.C5 - 0.05) / 2.2)
            pull = 0.0
            energy = T.smoother((t - T.T_BOUNCE[0]) / 1.0)
        else:
            prog = 1.0
            pull = T.smoother((t - (T.T_PILES[0] - 0.3)) / 0.8) * 0.85
            energy = 1.0
        for k, (r_, c) in enumerate(zip(RAYS, LGC)):
            pts = bounce_path(c, energy, pull)
            r_.set(resample(pts, 160, prog), 0.011)
            hp_ = resample(pts, 400, 1.0)
            u_ = prog if prog < 0.999 else (0.45 * (t - T.C5 - 2.25)) % 1.0
            HEADS[k].location = tuple(hp_[min(399, int(u_ * 399))])
            HEADS[k].hide_render = False
        RAY_S.default_value = 9.0 + 10.0 * energy
        FLESH_GLOW.default_value = 0.12 * energy * (1 - 0.6 * pull)
        hot = 0.0 if i == T.S_TRAP else T.smoother((t - (T.T_PILES[0] - 0.1)) / 0.7)
        if hot > 0.01:
            LHOT.hide_render = False
            LHOT.location = tuple(LGP + np.array([0, -0.05, 0]))
            sc = 0.6 + 1.4 * hot + 0.15 * math.sin(t * 45) * hot
            LHOT.scale = (sc, sc, sc)
            HOT_S.default_value = 60.0 + 80.0 * hot
            LPL.data.energy = 4.0 * hot
            LPL.location = tuple(LGP + np.array([0, -0.1, 0]))
        if i == T.S_TOUCH:
            pin = T.smoother((t - (T.T_PIN[0] - 0.25)) / 0.3)
            if pin > 0.01:
                for p in PIN_PARTS:
                    p.hide_render = False
                PIN_E.location = tuple(LGP + np.array([0.07, -0.16, -0.10]) + np.array([0, 0, -0.6]) * (1 - pin))
                PIN_E.rotation_euler = (0, math.radians(38), math.radians(-12))


# ================================================================= ZOOM set: salt ions and electrons in the hotspot
ZO = G.ZOOM_O
_gz = np.random.default_rng(77)
NI = 9
ION_P = np.stack([_gz.uniform(-1.6, 1.6, NI), _gz.uniform(-0.4, 0.6, NI), _gz.uniform(-0.6, 1.3, NI)], -1)
for _ in range(60):                             # push apart so the ions don't overlap
    d = ION_P[:, None] - ION_P[None]
    dist = np.linalg.norm(d, axis=-1) + np.eye(NI) * 9
    push = (d / dist[..., None] * np.clip(0.95 - dist, 0, None)[..., None]).sum(1)
    ION_P += push * 0.5
ION_P += ZO
_iv, _if = ico_vf(3)
IONS = puts(obj_from("Ions", np.concatenate([_iv * 0.26 + p for p in ION_P]),
                     [[k * len(_iv) + a for a in f] for k in range(NI) for f in _if], ion_m), "zoom")
NE = NI * 2
E_AX = rand_dirs(NE, _gz)
E_PH = _gz.uniform(0, 6.28, NE)
E_W = _gz.uniform(3.0, 5.0, NE) * _gz.choice([-1, 1], NE)
E_OUT = rand_dirs(NE, _gz)
E_OUT[:, 1] = -np.abs(E_OUT[:, 1]) * 0.6 - 0.2          # many fly toward the camera side
E_OUT /= np.linalg.norm(E_OUT, axis=1, keepdims=True)
E_T0 = T.E_T0
_ev, _ef = ico_vf(2)
ELECS = Dyn("Electrons", np.zeros((NE * len(_ev), 3)), [[k * len(_ev) + a for a in f] for k in range(NE) for f in _ef],
            elec_m, sets=("zoom",), smooth=True)
no_shadow(ELECS.o)
ZHOT = puts(obj_from("ZoomGlow", ico_vf(3)[0], ico_vf(3)[1], hot_m), "zoom")
no_shadow(ZHOT)
FBZ = Fireball("ZoomPlasma", ("zoom",), 9)
ZPL = light("ZoomLight", "POINT", tuple(ZO + np.array([0, -1.0, 0.4])), None, 0.0, 0.5, (1.0, 0.6, 0.3), ("zoom",))
light("ZoomKey", "AREA", tuple(ZO + np.array([-5, -8, 6])), tuple(ZO + np.array([0, 0, 0.3])), 900.0, 6.0,
      (0.85, 0.9, 1.0), ("zoom",))
light("ZoomRim", "AREA", tuple(ZO + np.array([5, 6, 3])), tuple(ZO + np.array([0, 0, 0.3])), 500.0, 5.0,
      (0.5, 0.6, 1.0), ("zoom",))


def e_basis(ax):
    a = np.cross(ax, [0.0, 0.0, 1.0])
    bad = np.linalg.norm(a, axis=1) < 1e-3
    a[bad] = np.cross(ax[bad], [1.0, 0.0, 0.0])
    a /= np.linalg.norm(a, axis=1, keepdims=True)
    return a, np.cross(ax, a)


E_A, E_B = e_basis(E_AX)


def pose_zoom(t):
    home = np.repeat(ION_P, 2, axis=0)
    ang = E_PH + E_W * t
    orb = home + 0.5 * (np.cos(ang)[:, None] * E_A + np.sin(ang)[:, None] * E_B)
    a = np.maximum(0.0, t - (T.T_RIP + E_T0))
    fly = orb + E_OUT * (2.5 * a + 6.0 * a * a)[:, None]
    p = np.where((a > 0)[:, None], fly, orb)
    sc = np.where(a > 0, np.maximum(0.0, 1 - a / 1.4), 1.0)
    ELECS.set((_ev[None] * 0.1 * sc[:, None, None] + p[:, None, :]))
    field = T.smoother((t - (T.C7 + 0.1)) / 0.6)
    boom = t - T.T_BOOM7
    ZHOT.location = tuple(ZO + np.array([0, 0.3, 0.35]))
    s = 0.25 + 0.25 * field + 0.03 * math.sin(t * 35)
    ZHOT.scale = (s, s, s)
    ZHOT.hide_render = True
    HOT_S.default_value = 3.0 + 4.0 * field
    HOT_A.default_value = 0.25
    ION_GLOW.default_value = 0.0 if boom < 0 else 3.0 * min(1.0, boom / 0.2)
    if boom > 0:
        grow = 1 - math.exp(-boom / 0.08)
        FBZ.pose(ZO + np.array([0, 0.2, 0.3 + 0.25 * boom]), 1.9 * grow * (1 + 0.05 * math.sin(boom * 29)), boom,
                 rise=0.2)
        ZPL.data.energy = 900.0 * grow
    else:
        FBZ.pose(ZO, 0.0, 0.0)
        ZPL.data.energy = 25.0 * field


# ================================================================= per-frame pose
def pose(t):
    i = T.shot_index(t)
    s = T.SET_OF[i]
    for k, objs in SETS.items():
        for o in objs:
            o.hide_render = True
    for o in SETS[s]:
        o.hide_render = False
    c, st = WORLD[s]
    WCOL.default_value = (*c, 1)
    WSTR.default_value = st
    HOT_A.default_value = 1.0
    for w_ in NOISE_W:
        w_.default_value = t * 2.5
    if s == "mw":
        pose_mw(*T.mw_state(t))
    elif s == "lab":
        pose_lab(t)
    elif s == "zoom":
        pose_zoom(t)


# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.clip_start = 0.01
cam_d.clip_end = 5000
cam = bpy.data.objects.new("Cam", cam_d)
cam.rotation_mode = "QUATERNION"
col.objects.link(cam)
scene.camera = cam

# ================================================================= render
r = scene.render
r.engine = "CYCLES"
r.resolution_x, r.resolution_y = RES
r.resolution_percentage = 100
r.image_settings.file_format = "PNG"
r.use_motion_blur = False
c = scene.cycles
c.device = "CPU"
c.use_adaptive_sampling = True
c.adaptive_threshold = 0.05
c.use_denoising = True
c.denoising_quality = "BALANCED"
c.denoising_prefilter = "ACCURATE"
c.max_bounces = 8
c.diffuse_bounces = 2
c.glossy_bounces = 3
c.transparent_max_bounces = 24
c.transmission_bounces = 6
c.caustics_reflective = False
c.caustics_refractive = False
c.blur_glossy = 1.0
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0
except Exception:
    pass

SPP = 12
if os.environ.get("GP_EXP"):
    exec(os.environ["GP_EXP"])

for f in FRAMES:
    t = f / T.FPS
    path = os.path.join(OUT, f"f_{f:04d}.png")
    if os.path.exists(path):
        continue
    pose(t)
    loc, tgt, lens = T.camera(t)
    k = T.shake(t)
    if k:
        loc = tuple(a + k * b for a, b in zip(loc, (math.sin(t * 61), math.sin(t * 53) * 0.5, math.sin(t * 47))))
    cam.location = loc
    cam.rotation_quaternion = (V(tgt) - V(loc)).to_track_quat("-Z", "Y")
    cam_d.lens = lens
    scene.frame_set(f)
    c.samples = max(4, int(SPP * QUALITY))
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"rendered {f}", flush=True)
print("done")
