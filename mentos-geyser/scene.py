"""Blender scene for "Mentos + Diet Coke" (Cycles, posed per frame). 1 unit = 1 inch.

Sets (only the active one is rendered):
  yard   a sunny lawn: a 2-liter bottle erupting past a basketball hoop (frame 0 / loop), regular vs diet
  lab    a teal studio: a see-through bottle with the dissolved gas, three ghost bottles of gas, a Mentos close-up,
         Mentos sinking with bubble trails, the foam shooting out
  micro  the candy surface magnified in the soda: a bubble that can't start, craters that spit out bubbles

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
SETS = {k: [] for k in ("yard", "lab", "micro")}


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
    def __init__(self, name, verts, faces, mat, sets=("yard",), smooth=True):
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


def no_glossy(o):
    o.visible_glossy = False
    return o


def no_shadow(o):
    o.visible_shadow = False
    return o


# ================================================================= world (sky gradient for the yard, flat elsewhere)
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
_wbg = wnt.nodes["Background"]
_wtc = wnt.nodes.new("ShaderNodeTexCoord")
_wsep = wnt.nodes.new("ShaderNodeSeparateXYZ")
wnt.links.new(_wtc.outputs["Generated"], _wsep.inputs[0])
_wmr = wnt.nodes.new("ShaderNodeMapRange")
_wmr.inputs["From Min"].default_value, _wmr.inputs["From Max"].default_value = -0.05, 0.75
wnt.links.new(_wsep.outputs["Z"], _wmr.inputs["Value"])
_wramp = wnt.nodes.new("ShaderNodeValToRGB")
_cr = _wramp.color_ramp
_cr.elements[0].position, _cr.elements[0].color = 0.0, (0.78, 0.86, 0.95, 1)
_cr.elements[1].position, _cr.elements[1].color = 1.0, (0.20, 0.45, 0.92, 1)
wnt.links.new(_wmr.outputs["Result"], _wramp.inputs[0])
_wmix = wnt.nodes.new("ShaderNodeMix")
_wmix.data_type = "RGBA"
wnt.links.new(_wramp.outputs[0], _wmix.inputs[7])
wnt.links.new(_wmix.outputs[2], _wbg.inputs["Color"])
WSKY = _wmix.inputs[0]
WCOL = _wmix.inputs[6]
WSTR = _wbg.inputs["Strength"]
WORLD = {"yard": ((0.5, 0.6, 0.8), 1.0, 1.0), "lab": ((0.010, 0.035, 0.045), 1.0, 0.0),
         "micro": ((0.075, 0.028, 0.010), 1.0, 0.0)}


# ================================================================= materials
def pet_mat(name, ior=1.3, tint=(0.95, 0.98, 0.97), rough=0.03):
    m, p = principled(name, tint, rough=rough)
    p.inputs["Transmission Weight"].default_value = 1.0
    p.inputs["IOR"].default_value = ior
    p.inputs["Specular IOR Level"].default_value = 0.6
    return m, p


bottle_m, _ = pet_mat("PET")
labpet_m, _lp = pet_mat("LabPET", ior=1.02, rough=0.06)
_lp.inputs["Coat Weight"].default_value = 0.6
_lp.inputs["Coat Roughness"].default_value = 0.05
cola_m, _cola = pet_mat("Cola", ior=1.33, tint=(0.30, 0.08, 0.02), rough=0.04)
def labcola_mat(name):
    m, nt, out = new_mat(name)
    tr = node(nt, "ShaderNodeBsdfTransparent", Color=(1.0, 0.70, 0.38, 1))
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.15)
    p.inputs["Base Color"].default_value = (0.70, 0.30, 0.08, 1)
    p.inputs["Coat Weight"].default_value = 0.8
    p.inputs["Emission Color"].default_value = (0.9, 0.38, 0.08, 1)
    p.inputs["Emission Strength"].default_value = 0.25
    mix = node(nt, "ShaderNodeMixShader", Fac=0.2)
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(p.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m


labcola_m = labcola_mat("LabCola")
silver_m, _sv = principled("LabelSilver", (0.80, 0.81, 0.83), rough=0.35)
_sv.inputs["Metallic"].default_value = 0.7
red_m, _ = principled("LabelRed", (0.62, 0.03, 0.03), rough=0.3, coat=0.4)
cap_m, _ = principled("Cap", (0.85, 0.85, 0.86), rough=0.35)


def foam_mat(name, glow=0.0):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.55)
    p.inputs["Subsurface Weight"].default_value = 0.6
    p.inputs["Subsurface Radius"].default_value = (1.0, 0.6, 0.4)
    p.inputs["Subsurface Scale"].default_value = 0.4
    p.inputs["Emission Color"].default_value = (1.0, 0.86, 0.72, 1)
    p.inputs["Emission Strength"].default_value = glow
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=1.6, Detail=6.0)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    rp = nt.nodes.new("ShaderNodeValToRGB")
    cr = rp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.30, (0.78, 0.55, 0.36, 1)
    cr.elements[1].position, cr.elements[1].color = 0.50, (1.0, 0.95, 0.90, 1)
    nt.links.new(nz.outputs["Fac"], rp.inputs[0])
    nt.links.new(rp.outputs[0], p.inputs["Base Color"])
    vz = node(nt, "ShaderNodeTexVoronoi", Scale=9.0)
    nt.links.new(tc.outputs["Object"], vz.inputs["Vector"])
    bp = node(nt, "ShaderNodeBump", Strength=0.5, Distance=0.05)
    nt.links.new(vz.outputs["Distance"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


foam_m = foam_mat("Foam", glow=0.12)
labfoam_m = foam_mat("LabFoamMat", glow=0.6)
dropcola_m, _dc = pet_mat("ColaDrop", ior=1.33, tint=(0.45, 0.16, 0.05), rough=0.05)


def candy_mat(name, crater_scale=0.0):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.38)
    p.inputs["Base Color"].default_value = (0.93, 0.92, 0.88, 1)
    p.inputs["Subsurface Weight"].default_value = 0.35
    p.inputs["Subsurface Radius"].default_value = (1.0, 0.9, 0.8)
    p.inputs["Subsurface Scale"].default_value = 0.05 if crater_scale else 0.6
    p.inputs["Coat Weight"].default_value = 0.3
    if crater_scale:
        tc = node(nt, "ShaderNodeTexCoord")
        vz = node(nt, "ShaderNodeTexVoronoi", Scale=crater_scale)
        nt.links.new(tc.outputs["Object"], vz.inputs["Vector"])
        bp = node(nt, "ShaderNodeBump", Strength=0.55, Distance=0.02)
        nt.links.new(vz.outputs["Distance"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


mentos_m = candy_mat("Mentos")
labmentos_m = candy_mat("LabMentos")
_lmp = [n for n in labmentos_m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"][0]
_lmp.inputs["Emission Color"].default_value = (1.0, 0.98, 0.94, 1)
_lmp.inputs["Emission Strength"].default_value = 0.9
mentos_close_m = candy_mat("MentosClose", crater_scale=38.0)


def bubble_mat(name, rim=0.5, blend=0.25, gcol=(1, 1, 1), ecol=(0.92, 0.97, 1.0)):
    """An air bubble: see-through centre, bright glossy edge (no refraction: cheap and readable)."""
    m, nt, out = new_mat(name)
    tr = node(nt, "ShaderNodeBsdfTransparent")
    gl = node(nt, "ShaderNodeBsdfGlossy", Roughness=0.04, Color=(*gcol, 1))
    lw = node(nt, "ShaderNodeLayerWeight", Blend=blend)
    geo_ = nt.nodes.new("ShaderNodeNewGeometry")
    front = nt.nodes.new("ShaderNodeMath")
    front.operation = "SUBTRACT"
    front.inputs[0].default_value = 1.0
    nt.links.new(geo_.outputs["Backfacing"], front.inputs[1])
    fr = nt.nodes.new("ShaderNodeMath")
    fr.operation = "MULTIPLY"
    nt.links.new(lw.outputs["Fresnel"], fr.inputs[0])
    nt.links.new(front.outputs[0], fr.inputs[1])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fr.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(gl.outputs[0], mix.inputs[2])
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], inv.inputs[1])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 3.0
    nt.links.new(inv.outputs[0], pw.inputs[0])
    em = node(nt, "ShaderNodeEmission", Color=(*ecol, 1))
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = rim
    nt.links.new(pw.outputs[0], mul.inputs[0])
    mul2 = nt.nodes.new("ShaderNodeMath")
    mul2.operation = "MULTIPLY"
    nt.links.new(mul.outputs[0], mul2.inputs[0])
    nt.links.new(front.outputs[0], mul2.inputs[1])
    nt.links.new(mul2.outputs[0], em.inputs["Strength"])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(mix.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs[0])
    return m


bubble_m = bubble_mat("Bubble", 0.4)
microbub_m = bubble_mat("MicroBubble", 0.5, blend=0.1, gcol=(0.55, 0.55, 0.55))
gas_m, GAS_S = emit_mat("GasDot", (0.80, 0.95, 1.0), 2.2)
ghost_m, _gh = principled("GhostBottle", (0.55, 0.88, 1.0), rough=0.1)
_gh.inputs["Transmission Weight"].default_value = 1.0
_gh.inputs["IOR"].default_value = 1.0
_gh.inputs["Alpha"].default_value = 0.55
_gh.inputs["Emission Color"].default_value = (0.4, 0.85, 1.0, 1)
_gh.inputs["Emission Strength"].default_value = 0.35
grass_m, _gr = principled("Grass", (0.1, 0.3, 0.05), rough=0.8)
grass_nt = grass_m.node_tree
_gtc = node(grass_nt, "ShaderNodeTexCoord")
_gn = node(grass_nt, "ShaderNodeTexNoise", Scale=0.02, Detail=6.0)
grass_nt.links.new(_gtc.outputs["Object"], _gn.inputs["Vector"])
_grp = grass_nt.nodes.new("ShaderNodeValToRGB")
_grp.color_ramp.elements[0].color = (0.045, 0.16, 0.025, 1)
_grp.color_ramp.elements[1].color = (0.20, 0.42, 0.07, 1)
grass_nt.links.new(_gn.outputs["Fac"], _grp.inputs[0])
grass_nt.links.new(_grp.outputs[0], _gr.inputs["Base Color"])
_gv = node(grass_nt, "ShaderNodeTexNoise", Scale=2.5, Detail=2.0)
grass_nt.links.new(_gtc.outputs["Object"], _gv.inputs["Vector"])
_gb = node(grass_nt, "ShaderNodeBump", Strength=0.8, Distance=0.3)
grass_nt.links.new(_gv.outputs["Fac"], _gb.inputs["Height"])
grass_nt.links.new(_gb.outputs["Normal"], _gr.inputs["Normal"])
wood_m, _ = principled("Fence", (0.50, 0.33, 0.19), rough=0.7, bump=0.3, bump_scale=0.4)
bush_m, _ = principled("Bush", (0.06, 0.20, 0.04), rough=0.8, bump=0.6, bump_scale=0.3)
house_m, _ = principled("House", (0.62, 0.70, 0.78), rough=0.7)
roof_m, _ = principled("Roof", (0.22, 0.20, 0.22), rough=0.8)
pole_m, _pm = principled("Pole", (0.12, 0.12, 0.13), rough=0.35)
_pm.inputs["Metallic"].default_value = 0.8
board_m, _ = principled("Backboard", (0.95, 0.95, 0.95), rough=0.25, coat=0.5)
stripe_m, _ = principled("BoardStripe", (0.75, 0.05, 0.04), rough=0.3)
rim_m, _rm = principled("Rim", (0.95, 0.30, 0.04), rough=0.3)
_rm.inputs["Metallic"].default_value = 0.6
net_m, _ = principled("Net", (0.95, 0.95, 0.95), rough=0.6)
cyc_m, _ = principled("Cyc", (0.06, 0.32, 0.36), rough=0.6)
terrain_m, _tp = principled("CandySurface", (0.90, 0.88, 0.82), rough=0.35)
_tp.inputs["Subsurface Weight"].default_value = 0.4
_tp.inputs["Subsurface Radius"].default_value = (1.0, 0.85, 0.7)
_tp.inputs["Subsurface Scale"].default_value = 0.6
_tnt = terrain_m.node_tree
_ttc = node(_tnt, "ShaderNodeTexCoord")
_tnz = node(_tnt, "ShaderNodeTexNoise", Scale=0.9, Detail=8.0)
_tnt.links.new(_ttc.outputs["Object"], _tnz.inputs["Vector"])
_tb = node(_tnt, "ShaderNodeBump", Strength=0.35, Distance=0.2)
_tnt.links.new(_tnz.outputs["Fac"], _tb.inputs["Height"])
_tnt.links.new(_tb.outputs["Normal"], _tp.inputs["Normal"])


# ================================================================= geometry helpers
def lathe_vf(prof, seg=48):
    prof = [(max(r, 1e-3), z) for r, z in prof]
    ang = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    v = np.array([(r * math.cos(a), r * math.sin(a), z) for r, z in prof for a in ang])
    f = [[i * seg + k, i * seg + (k + 1) % seg, (i + 1) * seg + (k + 1) % seg, (i + 1) * seg + k]
         for i in range(len(prof) - 1) for k in range(seg)]
    return v, f


def solid_faces(nr, seg):
    f = [[i * seg + k, i * seg + (k + 1) % seg, (i + 1) * seg + (k + 1) % seg, (i + 1) * seg + k]
         for i in range(nr - 1) for k in range(seg)]
    b, tp = nr * seg, nr * seg + 1
    f += [[(k + 1) % seg, k, b] for k in range(seg)]
    f += [[(nr - 1) * seg + k, (nr - 1) * seg + (k + 1) % seg, tp] for k in range(seg)]
    return f


def solid_verts(z0, z1, rk, nr, seg, wobble=0.0, t=0.0):
    zz = np.linspace(z0, z1, nr)
    rr = G.bottle_r(zz) * rk
    ang = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    if wobble:
        top = np.zeros(nr)
        top[-1] = 1
    v = np.stack([rr[:, None] * np.cos(ang)[None], rr[:, None] * np.sin(ang)[None],
                  np.repeat(zz[:, None], seg, 1)], -1).reshape(-1, 3)
    if wobble:
        v[-seg:, 2] += wobble * np.sin(3 * ang + t * 9) * 0.5 + wobble * np.sin(5 * ang - t * 13) * 0.3
    return np.concatenate([v, [[0, 0, z0], [0, 0, z1 + wobble * 0.6]]])


class Solid(Dyn):
    """The soda or the foam inside a bottle between two heights (fixed topology)."""
    def __init__(self, name, mat, sets, rk=0.955, nr=36, seg=40):
        self.rk, self.nr, self.seg = rk, nr, seg
        super().__init__(name, solid_verts(1, 2, rk, nr, seg), solid_faces(nr, seg), mat, sets=sets)

    def pose(self, origin, z0, z1, wobble=0.0, t=0.0, scale_xy=1.0):
        if z1 - z0 < 0.03:
            self.o.hide_render = True
            return
        self.o.hide_render = False
        v = solid_verts(z0, z1, self.rk, self.nr, self.seg, wobble, t)
        v[:, :2] *= scale_xy
        self.set(v + origin)


_DV, _DF = ico_vf(1)


class Spray:
    """Ballistic drops: p = p0 + v0 a - g a^2/2 (a = te - t0), stretched along their velocity, gone below 'ground'."""
    def __init__(self, name, n, seed, mat, sets, size=(0.12, 0.35), sub=1):
        self.g = np.random.default_rng(seed)
        self.n = n
        self.size = self.g.uniform(*size, n)
        self.V, F = ico_vf(sub)
        f = [[k * len(self.V) + a for a in tri] for k in range(n) for tri in F]
        self.dyn = Dyn(name, np.zeros((n * len(self.V), 3)), f, mat, sets=sets, smooth=True)

    def emit(self, p0, v0, t0, life=9.0):
        self.p0, self.v0, self.t0 = np.asarray(p0, float), np.asarray(v0, float), np.asarray(t0, float)
        self.life = np.broadcast_to(np.asarray(life, float), (self.n,))

    def state(self, te):
        a = te - self.t0
        p = self.p0 + self.v0 * a[:, None]
        p[:, 2] -= 0.5 * G.G_IN * a * a
        vel = self.v0.copy()
        vel[:, 2] -= G.G_IN * a
        return a, p, vel

    def pose(self, te, origin, ground=0.15, scale=1.0, grow=0.0):
        if te is None:
            self.dyn.o.hide_render = True
            return
        a, p, vel = self.state(te)
        vis = (a > 0) & (p[:, 2] > ground) & (a < self.life)
        if not vis.any():
            self.dyn.o.hide_render = True
            return
        self.dyn.o.hide_render = False
        fade = np.clip((self.life - a) / 0.3, 0, 1)
        sc = np.where(vis, self.size * np.clip(a * 14, 0.35, 1.0) * scale * (1 + grow * np.clip(a, 0, 0.8)) * fade, 0.0)
        sp = np.linalg.norm(vel, axis=1) + 1e-6
        d = vel / sp[:, None]
        st = 1.0 + np.clip(sp / 500.0, 0, 1.2)
        L = self.V[None] * sc[:, None, None]
        along = np.einsum("kvj,kj->kv", L, d)
        L = L + along[..., None] * d[:, None, :] * (st[:, None, None] - 1)
        self.dyn.set(L + (p + origin)[:, None, :])


class BubbleSet(Dyn):
    def __init__(self, name, n, mat, sets, sub=1):
        self.bv, bf = ico_vf(sub)
        self.nb = n
        super().__init__(name, np.zeros((n * len(self.bv), 3)),
                         [[k * len(self.bv) + a for a in tri] for k in range(n) for tri in bf], mat, sets=sets)

    def pose(self, pos, rad):
        pos = np.asarray(pos, float)
        rad = np.asarray(rad, float)
        if not (rad > 1e-4).any():
            self.o.hide_render = True
            return
        self.o.hide_render = False
        self.set(self.bv[None] * rad[:, None, None] + pos[:, None, :])


def mentos_vf():
    v, f = uv_vf(32, 16)
    v = v * np.array([G.MENTOS_R, G.MENTOS_R, G.MENTOS_H * 0.5])
    flat = np.abs(v[:, 2]) > G.MENTOS_H * 0.32
    v[flat, 2] = np.sign(v[flat, 2]) * (G.MENTOS_H * 0.32 + (np.abs(v[flat, 2]) - G.MENTOS_H * 0.32) * 0.5)
    return v, f


_MV, _MF = mentos_vf()


def place(o, loc, rot=(0, 0, 0), scale=1.0):
    o.location = tuple(float(c) for c in loc)
    o.rotation_euler = rot
    o.scale = (scale, scale, scale) if np.isscalar(scale) else tuple(scale)
    o.hide_render = False


# ================================================================= YARD
YO = G.YARD_O
puts(obj_from("Lawn", [(-4000, -4000, 0), (4000, -4000, 0), (4000, 4000, 0), (-4000, 4000, 0)], [[0, 1, 2, 3]],
              grass_m, smooth=False), "yard")
for k in range(-20, 21):                                       # wooden fence boards
    box(f"Fence{k}", (k * 6.0 - 2.8, 260, 0), (k * 6.0 + 2.8, 261.5, 72 + 3 * (k % 2)), wood_m, "yard")
box("FenceRail", (-123, 258.5, 50), (123, 260, 54), wood_m, "yard")
box("House", (-600, 520, 0), (600, 600, 230), house_m, "yard")
box("Roof", (-640, 500, 230), (640, 620, 250), roof_m, "yard")
_gb_ = np.random.default_rng(5)
_iv2, _if2 = ico_vf(3)
for k in range(9):
    c = np.array([_gb_.uniform(-260, 260), _gb_.uniform(280, 360), 0])
    s = _gb_.uniform(30, 60)
    vv = _iv2 * np.array([s * 1.3, s, s * 0.9]) + c
    puts(obj_from(f"Bush{k}", vv, _if2, bush_m), "yard")

# basketball hoop (rim at 10 ft)
HX, HY = G.HOOP_X, G.HOOP_Y
_cyl_v, _cyl_f = lathe_vf([(2.2, 0), (2.2, 150)], 24)
puts(obj_from("Pole", _cyl_v + np.array([HX, HY + 16, 0]), _cyl_f, pole_m), "yard")
box("Arm", (HX - 1.5, HY + 1, 133), (HX + 1.5, HY + 16, 137), pole_m, "yard")
box("Backboard", (HX - 36, HY - 1, 114), (HX + 36, HY, 156), board_m, "yard")
for lo, hi in [((HX - 12, HY - 1.15, 120.5), (HX + 12, HY - 1.0, 121.8)),
               ((HX - 12, HY - 1.15, 136.2), (HX + 12, HY - 1.0, 137.5)),
               ((HX - 12, HY - 1.15, 120.5), (HX - 10.7, HY - 1.0, 137.5)),
               ((HX + 10.7, HY - 1.15, 120.5), (HX + 12, HY - 1.0, 137.5))]:
    box("Stripe", lo, hi, stripe_m, "yard")
RIM_C = np.array([HX, HY - 1 - G.RIM_R - 0.6, G.RIM_Z])
_tv, _tf = [], []
for i in range(48):
    a = 2 * math.pi * i / 48
    for j in range(8):
        b = 2 * math.pi * j / 8
        rr = G.RIM_R + 0.32 * math.cos(b)
        _tv.append((RIM_C[0] + rr * math.cos(a), RIM_C[1] + rr * math.sin(a), RIM_C[2] + 0.32 * math.sin(b)))
_tf = [[i * 8 + j, i * 8 + (j + 1) % 8, ((i + 1) % 48) * 8 + (j + 1) % 8, ((i + 1) % 48) * 8 + j]
       for i in range(48) for j in range(8)]
puts(obj_from("Rim", _tv, _tf, rim_m), "yard")
for k in range(12):
    a0 = 2 * math.pi * k / 12
    for dirn in (1, -1):
        pts = []
        for s in np.linspace(0, 1, 6):
            a = a0 + dirn * s * 0.5
            rr = G.RIM_R * (1 - 0.35 * s)
            pts.append((RIM_C[0] + rr * math.cos(a), RIM_C[1] + rr * math.sin(a), RIM_C[2] - 15 * s))
        pts = resample(pts, 8)
        puts(obj_from("Net", tube_verts(pts, 0.15, 5), tube_faces(8, 5), net_m), "yard")

SUN = bpy.data.lights.new("Sun", "SUN")
SUN.energy, SUN.angle, SUN.color = 4.2, math.radians(1.5), (1.0, 0.95, 0.86)
_sun = bpy.data.objects.new("Sun", SUN)
_sun.rotation_euler = (V((-0.8, -1.3, 1.7)).normalized()).to_track_quat("Z", "Y").to_euler()
col.objects.link(_sun)
SETS["yard"].append(_sun)
no_glossy(light("YardBounce", "AREA", (-30, -80, 30), (0, 0, 20), 3000.0, 80.0, (0.9, 0.95, 1.0), ("yard",)))


class Geyser:
    """A 2-liter bottle that erupts: shell, label, soda, foam inside, the jet column, and two sprays."""
    def __init__(self, name, pos, H, seed, label_m, n_cola=520, n_foam=900, toward=None):
        self.pos, self.H = np.asarray(pos, float), H
        v, f = lathe_vf(G.BOT_PROFILE, 48)
        self.shell = puts(obj_from(name + "Shell", v + self.pos, f, bottle_m), "yard")
        lv, lf = lathe_vf([(2.13, G.LABEL_Z[0]), (2.13, G.LABEL_Z[1])], 48)
        self.label = puts(obj_from(name + "Label", lv + self.pos, lf, label_m), "yard")
        self.soda = Solid(name + "Soda", cola_m, ("yard",))
        self.foam = Solid(name + "FoamIn", foam_m, ("yard",), rk=0.95)
        self.jet = Line(name + "Jet", 56, foam_m, ("yard",), seg=20)
        self.cola = Spray(name + "ColaSpray", n_cola, seed, dropcola_m, ("yard",), (0.10, 0.30))
        self.fspray = Spray(name + "FoamSpray", n_foam, seed + 1, foam_m, ("yard",), (0.35, 0.8), sub=2)
        self.parts = [self.shell, self.label, self.soda.o, self.foam.o, self.jet.dyn.o, self.cola.dyn.o,
                      self.fspray.dyn.o]
        for sp in (self.cola, self.fspray):
            g = sp.g
            n = sp.n
            t0 = 5.0 * g.uniform(0, 1, n) ** 1.7
            s = np.array([T.geyser_strength(x) for x in t0])
            vz = np.sqrt(2 * G.G_IN * (H - G.BOT_TOP) * np.maximum(s, 0.05)) * g.uniform(0.62, 1.0, n)
            ang = g.uniform(0, 2 * np.pi, n)
            vr = (g.uniform(4, 34, n) * (1 + 0.6 * g.uniform(0, 1, n) ** 3)) if sp is self.cola else g.uniform(1, 10, n)
            v0 = np.stack([vr * np.cos(ang), vr * np.sin(ang), vz], -1)
            if toward is not None:                           # a few drops fly toward the camera (and miss it)
                k = g.choice(n, n // 12, replace=False)
                d = np.asarray(toward, float)
                d = d / np.linalg.norm(d)
                v0[k, 0] = d[0] * g.uniform(40, 75, len(k)) + g.normal(0, 6, len(k))
                v0[k, 1] = d[1] * g.uniform(40, 75, len(k)) + g.normal(0, 6, len(k))
                v0[k, 2] = g.uniform(150, 230, len(k))
                t0[k] = g.uniform(0.0, 1.2, len(k))
            p0 = np.stack([0.3 * np.cos(ang), 0.3 * np.sin(ang), np.full(n, G.BOT_TOP + 0.2)], -1)
            life = 9.0 if sp is self.cola else v0[:, 2] / G.G_IN + g.uniform(0.25, 0.7, n)
            sp.emit(p0, v0, t0, life)

    def hide(self):
        for o in self.parts:
            o.hide_render = True

    def pose(self, te, t):
        for o in (self.shell, self.label):
            o.hide_render = False
        lvl = G.FILL_Z if te < -0.25 else 2.6 + (G.FILL_Z - 2.6) * math.exp(-(te + 0.25) / 2.0)
        self.soda.pose(self.pos, 0.12, lvl, wobble=0.0)
        if te > -0.32:
            ft = lvl + (G.BOT_TOP + 0.15 - lvl) * T.smoother((te + 0.32) / 0.3)
            self.foam.pose(self.pos, lvl - 0.02, ft, wobble=0.08, t=t)
        else:
            self.foam.o.hide_render = True
        if te > 0.0:
            top = T.jet_top(te, self.H)
            s = T.geyser_strength(te)
            zz = np.linspace(G.BOT_TOP - 1.2, top, self.jet.npt)
            f = (zz - G.BOT_TOP) / max(1.0, top - G.BOT_TOP)
            hs = self.H / G.GEYSER_H
            r = (0.65 + 1.4 * hs * f ** 0.6 + 2.6 * hs * f ** 2) * (0.6 + 0.4 * s)
            r = r * (1 + 0.12 * np.sin(zz * 0.35 + t * 23) + 0.08 * np.sin(zz * 0.9 - t * 31))
            front = np.clip((top - zz) / 4.0, 0, 1) ** 0.5
            r = np.maximum(0.05, r * (0.35 + 0.65 * front))
            r = np.where(zz < G.BOT_TOP + 0.2, np.minimum(r, 0.52), r)
            wob = f * hs * 3.0
            pts = np.stack([wob * np.sin(zz * 0.045 + t * 3.1), wob * np.sin(zz * 0.038 - t * 2.3) * 0.6, zz], -1)
            self.jet.set(pts + self.pos, r)
        else:
            self.jet.hide()
        self.cola.pose(te, self.pos)
        self.fspray.pose(te, self.pos, grow=1.6)


HERO = Geyser("Hero", YO, G.GEYSER_H, 21, silver_m, n_cola=800, n_foam=1500, toward=(0.45, -0.9))
REG = Geyser("Reg", YO + np.array([G.DIET_X[0], 0, 0]), G.REG_H, 31, red_m, n_cola=260, n_foam=700)
DIET = Geyser("Diet", YO + np.array([G.DIET_X[1], 0, 0]), G.GEYSER_H, 41, silver_m, n_cola=400, n_foam=1100)
HERO_MENTOS = [puts(obj_from(f"DropMentos{k}", _MV, _MF, mentos_m), "yard") for k in range(G.N_MENTOS)]


def pose_yard(t):
    te, td = T.yard_clock(t)
    if te is not None:
        REG.hide()
        DIET.hide()
        HERO.pose(te, t)
        for k, o in enumerate(HERO_MENTOS):
            z = T.mentos_drop(te, k)
            if z < G.BOT_TOP - 1.2:
                o.hide_render = True
            else:
                place(o, YO + np.array([0.04 * math.sin(k * 2.1), 0.04 * math.cos(k * 1.3), z]),
                      (0.05 * math.sin(k), 0.05 * math.cos(k * 1.7), k * 0.7))
    else:
        HERO.hide()
        for o in HERO_MENTOS:
            o.hide_render = True
        REG.pose(td, t)
        DIET.pose(td, t)


# ================================================================= LAB
LO = G.LAB_O
_cp = [(-300, 0.0)] + [(80 + 60 * math.sin(a), 60 - 60 * math.cos(a)) for a in np.linspace(0, math.pi / 2, 12)] + \
      [(140, 400.0)]
_cv = np.array([(x, y, z) for y, z in _cp for x in (-400.0, 400.0)]) + LO
_cf = [[2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2] for i in range(len(_cp) - 1)]
puts(obj_from("Cyc", _cv, _cf, cyc_m), "lab")
light("LabKey", "AREA", tuple(LO + np.array([-28, -36, 36])), tuple(LO + np.array([0, 0, 7])), 2600.0, 24.0,
      (1.0, 0.95, 0.88), ("lab",))
light("LabRim", "AREA", tuple(LO + np.array([26, 30, 24])), tuple(LO + np.array([0, 0, 8])), 1600.0, 16.0,
      (0.65, 0.85, 1.0), ("lab",))
no_glossy(light("LabFill", "AREA", tuple(LO + np.array([34, -30, 10])), tuple(LO + np.array([0, 0, 7])), 700.0, 30.0,
      (0.9, 0.95, 1.0), ("lab",)))
no_glossy(light("LabBack", "AREA", tuple(LO + np.array([0, 20, 26])), tuple(LO + np.array([0, 70, 6])), 9000.0, 50.0,
      (0.5, 0.95, 1.0), ("lab",)))

_bv, _bf = lathe_vf(G.BOT_PROFILE, 56)
LAB_SHELL = puts(obj_from("LabShell", _bv, _bf, labpet_m), "lab")
LAB_SODA = Solid("LabSoda", labcola_m, ("lab",), rk=0.96)
LAB_FOAM = Solid("LabFoam", labfoam_m, ("lab",), rk=0.955)
_capv, _capf = lathe_vf([(0.01, 0.62), (0.70, 0.62), (0.72, 0.55), (0.72, 0.05), (0.66, 0.0)], 40)
LAB_CAP = puts(obj_from("LabCap", _capv, _capf, cap_m), "lab")

_gl = np.random.default_rng(12)
NG = 320


def rand_in_bottle(n, g, z0=0.5, z1=G.FILL_Z - 0.35, rk=0.82):
    z = g.uniform(z0, z1, n)
    a = g.uniform(0, 2 * np.pi, n)
    r = np.sqrt(g.uniform(0, 1, n)) * G.bottle_r(z) * rk
    return np.stack([r * np.cos(a), r * np.sin(a), z], -1)


GAS_P = rand_in_bottle(NG, _gl)
GAS_PH = _gl.uniform(0, 6.28, (NG, 3))
GAS_ORDER = _gl.permutation(NG)
_sv_, _sf_ = ico_vf(1)
GAS = Dyn("Gas", np.zeros((NG * len(_sv_), 3)), [[k * len(_sv_) + a for a in tri] for k in range(NG) for tri in _sf_],
          gas_m, sets=("lab",))
no_shadow(GAS.o)
GHOST_POS = [np.array([-4.9, 3.5, 0.0]), np.array([4.9, 3.5, 0.0]), np.array([0.0, 5.0, 13.6])]
GHOSTS = []
for k in range(3):
    gs = puts(obj_from(f"Ghost{k}", _bv, _bf, ghost_m), "lab")
    no_shadow(gs)
    gp = rand_in_bottle(70, _gl, 0.4, 11.0, 0.7)
    gd = obj_from(f"GhostGas{k}", np.concatenate([_sv_ * 0.075 + p for p in gp]),
                  [[i * len(_sv_) + a for a in tri] for i in range(70) for tri in _sf_], gas_m)
    gd.parent = gs
    no_shadow(gd)
    SETS["lab"].append(gd)
    GHOSTS.append((gs, gd))
light("CandyKey", "AREA", tuple(LO + np.array([55, -8, 12])), tuple(LO + np.array([60, 0, 6])), 1500.0, 6.0,
      (1.0, 0.96, 0.9), ("lab",))
light("CandyRim", "AREA", tuple(LO + np.array([64, 6, 9])), tuple(LO + np.array([60, 0, 6])), 900.0, 5.0,
      (0.6, 0.9, 1.0), ("lab",))
LAB_MENTOS = [puts(obj_from(f"LabMentos{k}", _MV * 1.15, _MF, labmentos_m), "lab") for k in range(G.N_MENTOS)]
CLOSE_MENTOS = puts(obj_from("CloseMentos", uv_vf(96, 48)[0] * np.array([G.MENTOS_R, G.MENTOS_R, G.MENTOS_H * 0.5]),
                             uv_vf(96, 48)[1], mentos_close_m), "lab")
NBT = 520
_gb2 = np.random.default_rng(14)
BT_M = np.arange(NBT) % G.N_MENTOS
BT_DT = 3.4 * _gb2.uniform(0, 1, NBT) ** 1.25
BT_OFF = rand_dirs(NBT, _gb2) * 0.42
BT_V = _gb2.uniform(5.0, 10.0, NBT)
BT_R = _gb2.uniform(0.05, 0.13, NBT)
BT_PH = _gb2.uniform(0, 6.28, NBT)
LAB_BUB = BubbleSet("LabBubbles", NBT, bubble_m, ("lab",))
LAB_JET = Line("LabJet", 40, labfoam_m, ("lab",), seg=18)
LAB_SPRAY = Spray("LabSpray", 160, 61, labfoam_m, ("lab",), (0.10, 0.28))
_g3 = np.random.default_rng(62)
_n = 160
_a = _g3.uniform(0, 2 * np.pi, _n)
_vr = _g3.uniform(2, 14, _n)
LAB_SPRAY.emit(np.stack([0.25 * np.cos(_a), 0.25 * np.sin(_a), np.full(_n, G.BOT_TOP)], -1),
               np.stack([_vr * np.cos(_a), _vr * np.sin(_a), _g3.uniform(110, 190, _n)], -1),
               _g3.uniform(0, 1.6, _n) ** 1.3)


def mentos_lab_z(t, k):
    """Height of the k-th Mentos in the lab bottle (falls into the neck, then sinks through the soda)."""
    a = t - (T.T_SINK0 + k * T.MENTOS_DT)
    z0 = G.BOT_TOP + 3.5
    if a <= 0:
        return z0, 0.0
    zl = G.FILL_Z
    al = math.sqrt(2 * (z0 - zl) / G.G_IN)
    if a < al:
        return z0 - 0.5 * G.G_IN * a * a, a
    vin, vs, tau = G.G_IN * al, 7.5, 0.07
    b = a - al
    z = zl - vs * b - (vin - vs) * tau * (1 - math.exp(-b / tau))
    return max(0.33 + 0.31 * k, z), a


def mentos_lab_xy(k, z):
    depth = T.clamp((G.FILL_Z - z) / 7.0)
    return np.array([0.75 * math.sin(k * 1.9 + 0.4) * depth, 0.5 * math.cos(k * 2.3) * depth])


def lab_foam(t):
    zt = G.FILL_Z + (G.BOT_TOP + 0.2 - G.FILL_Z) * T.smoother((t - (T.T_SINK0 + 0.6)) /
                                                              (T.T_ONEWAY[0] - T.T_SINK0 - 0.6))
    zb = G.FILL_Z - 6.2 * T.smoother((t - (T.T_SINK0 + 0.35)) / (T.T_JET_LAB + 1.2 - T.T_SINK0))
    return zb, zt


def pose_lab(t):
    i = T.shot_index(t)
    bottle = i in (T.S_WHY, T.S_SQZ, T.S_SINK, T.S_PUSH)
    for o in [LAB_SHELL, LAB_SODA.o, LAB_FOAM.o, LAB_CAP, GAS.o, LAB_BUB.o, LAB_JET.dyn.o, LAB_SPRAY.dyn.o,
              CLOSE_MENTOS] + LAB_MENTOS + [g for pair in GHOSTS for g in pair]:
        o.hide_render = True
    if i == T.S_PITSA:
        x = T.clamp((t - T.C5) / (T.C5B - T.C5))
        place(CLOSE_MENTOS, LO + np.array([60, 0, 6.0]), (math.radians(90) + 0.15, 0.25 + 0.3 * x, 0.4 + 0.5 * x))
        return
    if not bottle:
        return
    jit = T.smoother((t - T.T_JITTER) / 0.3) if i == T.S_SQZ else 0.0
    sxy = 1.0 + 0.03 * jit * (0.6 + 0.4 * math.sin(t * 37))
    place(LAB_SHELL, LO, scale=(sxy, sxy, 1.0))
    # soda and foam
    if i in (T.S_SINK, T.S_PUSH):
        zb, zt = lab_foam(t)
    else:
        zb, zt = G.FILL_Z, G.FILL_Z
    LAB_SODA.pose(LO, 0.1, zb, scale_xy=sxy)
    if zt - zb > 0.05:
        LAB_FOAM.pose(LO, zb - 0.02, zt, wobble=0.12, t=t)
    # dissolved gas dots
    if i == T.S_WHY:
        nvis = 120
    elif i == T.S_SQZ:
        q = sum(T.smoother((t - ts) / 0.22) for ts in T.T_SQZ)
        nvis = int(120 + 66 * q)
    else:
        nvis = int(150 * (1 - T.smoother((t - T.C7) / 0.7)))
    amp = 0.04 + 0.22 * jit
    p = GAS_P + amp * np.sin(GAS_PH + t * np.array([7.0, 8.3, 9.1]) * (1 + 3 * jit))
    p[:, 2] += 0.12 * np.sin(GAS_PH[:, 0] + t * 1.3)
    vis = np.zeros(NG, bool)
    vis[GAS_ORDER[:nvis]] = True
    vis &= p[:, 2] < zb - 0.15
    p[:, :2] *= sxy
    GAS.set(_sv_[None] * (0.065 * vis)[:, None, None] + (p + LO)[:, None, :])
    GAS.o.hide_render = False
    # ghost bottles of gas
    if i in (T.S_WHY, T.S_SQZ):
        for k, (gs, gd) in enumerate(GHOSTS):
            out_ = T.smoother((t - (T.T_GHOST + 0.14 * k)) / 0.45)
            back = T.smoother((t - T.T_SQZ[k]) / 0.22) if i == T.S_SQZ else 0.0
            f = out_ * (1 - back)
            if f < 0.02:
                continue
            gs.hide_render = gd.hide_render = False
            sc = 0.15 + 0.85 * f
            place(gs, LO + GHOST_POS[k] * f + np.array([0, 0, 0.4 * (1 - f)]), (0, 0, 0.15 * (k - 1) * f), sc)
    # cap: screwed on after the squeeze, rattling when the gas strains
    if i == T.S_SQZ:
        c = T.smoother((t - (T.T_CAP - 0.3)) / 0.35)
        if c > 0.01:
            rat = 0.06 * jit * math.sin(t * 61)
            place(LAB_CAP, LO + np.array([0, 0, G.BOT_TOP - 0.55 + 3.0 * (1 - c) + abs(rat)]),
                  (rat * 0.5, rat * 0.4, -4 * math.pi * c))
    # Mentos sinking, bubble trails, the jet
    if i in (T.S_SINK, T.S_PUSH):
        mz = []
        for k, o in enumerate(LAB_MENTOS):
            z, a = mentos_lab_z(t, k)
            xy = mentos_lab_xy(k, z)
            mz.append((xy, z, a))
            place(o, LO + np.array([xy[0], xy[1], z]), (1.2 * math.sin(k + a * 2), 0.8 * math.cos(k * 1.3 + a * 1.5),
                                                         k * 0.9))
        ts = np.array([T.T_SINK0 + m * T.MENTOS_DT + math.sqrt(2 * (3.5 + G.BOT_TOP - G.FILL_Z) / G.G_IN)
                       for m in range(G.N_MENTOS)])[BT_M] + BT_DT
        age = t - ts
        pos = np.zeros((NBT, 3))
        for m in range(G.N_MENTOS):
            sel = BT_M == m
            zs = np.array([mentos_lab_z(x, m)[0] for x in ts[sel]])
            xys = np.array([mentos_lab_xy(m, z) for z in zs])
            pos[sel, 0], pos[sel, 1], pos[sel, 2] = xys[:, 0], xys[:, 1], zs
        pos += BT_OFF
        pos[:, 2] += BT_V * np.maximum(age, 0) + 4.0 * np.maximum(age, 0) ** 2
        pos[:, 0] += 0.12 * np.sin(BT_PH + age * 9)
        r = BT_R * (0.5 + np.clip(age * 1.5, 0, 1.0))
        rb = G.bottle_r(pos[:, 2]) * 0.9
        rr = np.linalg.norm(pos[:, :2], axis=1)
        pos[:, :2] *= np.minimum(1.0, rb / (rr + 1e-6))[:, None]
        alive = (age > 0) & (pos[:, 2] < zb - 0.1)
        LAB_BUB.pose(pos + LO, np.where(alive, r, 0.0))
    if i == T.S_PUSH and t > T.T_JET_LAB:
        a = t - T.T_JET_LAB
        top = G.BOT_TOP + min(70.0, 190 * a)
        zz = np.linspace(G.BOT_TOP - 0.4, top, LAB_JET.npt)
        f = (zz - G.BOT_TOP) / max(1.0, top - G.BOT_TOP)
        r = (0.42 + 0.9 * f) * (1 + 0.15 * np.sin(zz * 1.3 + t * 25))
        r *= np.clip((top - zz) / 2.0, 0.2, 1) ** 0.5
        pts = np.stack([0.4 * f * np.sin(zz * 0.3 + t * 5), 0.3 * f * np.sin(zz * 0.25 - t * 4), zz], -1)
        LAB_JET.set(pts + LO, r)
        LAB_SPRAY.pose(a, LO, ground=0.3)


# ================================================================= MICRO: the candy surface in the soda
MO = G.MICRO_O
_gm = np.random.default_rng(91)
CR = [(2.0, 0.0, 3.4, 1.3)]                            # the hero crater (x, y, R, depth)
while len(CR) < 46:
    x, y = _gm.uniform(-30, 30), _gm.uniform(-16, 30)
    R = _gm.uniform(1.4, 3.6)
    if all(math.hypot(x - a, y - b) > R + c + 0.6 for a, b, c, _ in CR):
        CR.append((x, y, R, R * _gm.uniform(0.3, 0.45)))
CR = np.array(CR)


def terrain_h(x, y):
    h = 0.25 * np.sin(x * 0.21) * np.cos(y * 0.17) + 0.15 * np.sin(x * 0.53 + y * 0.31)
    for cx, cy, R, D in CR:
        d = np.hypot(x - cx, y - cy) / R
        h = h - D * np.clip(1 - d * d, 0, None) + 0.28 * D * np.exp(-((d - 1.0) / 0.22) ** 2)
    return h


NTR = 230
_xs = np.linspace(-38, 38, NTR)
_X, _Y = np.meshgrid(_xs, _xs)
_Z = terrain_h(_X, _Y)
_tv = np.stack([_X, _Y, _Z], -1).reshape(-1, 3) + MO
_tf = [[i * NTR + j, i * NTR + j + 1, (i + 1) * NTR + j + 1, (i + 1) * NTR + j] for i in range(NTR - 1)
       for j in range(NTR - 1)]
puts(obj_from("CandySurface", _tv, _tf, terrain_m), "micro")
CR_FLOOR = np.array([terrain_h(cx, cy) for cx, cy, _r, _d in CR])
light("MicroKey", "AREA", tuple(MO + np.array([-22, -26, 40])), tuple(MO), 26000.0, 30.0, (1.0, 0.92, 0.8),
      ("micro",))
no_glossy(light("MicroRim", "AREA", tuple(MO + np.array([20, 40, 18])), tuple(MO), 14000.0, 30.0, (1.0, 0.75, 0.45),
      ("micro",)))
no_glossy(light("MicroFill", "AREA", tuple(MO + np.array([10, -40, 10])), tuple(MO + np.array([0, 0, 6])), 6000.0, 40.0,
      (0.8, 0.9, 1.0), ("micro",)))
NSLOT = 4
NMB = len(CR) * NSLOT
MB = BubbleSet("MicroBubbles", NMB + 1, microbub_m, ("micro",), sub=3)
_gm2 = np.random.default_rng(92)
CR_ON = T.T_ALLON + _gm2.uniform(0, 0.12, len(CR))
CR_P = _gm2.uniform(0.42, 0.68, len(CR))
NDOT = 90
DOT_P = np.stack([_gm2.uniform(-26, 26, NDOT), _gm2.uniform(-14, 30, NDOT), _gm2.uniform(3, 34, NDOT)], -1)
DOT_PH = _gm2.uniform(0, 6.28, NDOT)
DOTS = Dyn("MicroGas", np.zeros((NDOT * len(_sv_), 3)),
           [[k * len(_sv_) + a for a in tri] for k in range(NDOT) for tri in _sf_], gas_m, sets=("micro",))
no_shadow(DOTS.o)
FAIL_P = [np.array([-4.5, 2.0, 15.0]), np.array([3.0, 4.0, 11.0])]


def crater_bubbles(t):
    pos = np.zeros((len(CR), NSLOT, 3))
    rad = np.zeros((len(CR), NSLOT))
    for k, (cx, cy, R, D) in enumerate(CR):
        P = CR_P[k]
        n = math.floor((t - CR_ON[k]) / P)
        for j in range(NSLOT):
            idx = n - j
            if idx < 0:
                continue
            age = t - (CR_ON[k] + idx * P)
            g = 0.55 * P
            Rb = 0.42 * R
            if age < g:
                r = Rb * math.sqrt(T.smoother(age / g))
                z = CR_FLOOR[k] + r * 0.9
            else:
                u = age - g
                r = Rb * (1 + 0.35 * u)
                z = CR_FLOOR[k] + Rb * 0.9 + 12 * u + 16 * u * u
            pos[k, j] = (cx + 0.3 * math.sin(age * 7 + k), cy, z)
            rad[k, j] = r if z < 42 else 0.0
    return pos.reshape(-1, 3), rad.reshape(-1)


def pose_micro(t):
    i = T.shot_index(t)
    pos = np.zeros((NMB + 1, 3))
    rad = np.zeros(NMB + 1)
    if i == T.S_BUB:
        p, r = crater_bubbles(t)
        pos[:NMB], rad[:NMB] = p, r
    if i == T.S_SEED:
        for k, ft in enumerate(T.T_FAIL):           # a bubble tries to start in the open soda, then collapses
            a = t - ft
            if 0 < a < 0.45:
                r = 0.9 * math.sin(math.pi * min(1.0, a / 0.45)) ** 0.7 * (1 - 0.25 * math.sin(a * 60))
                pos[NMB] = FAIL_P[k]
                rad[NMB] = max(0.0, r)
        a = t - T.T_HERO                            # the bubble that grows in the rough spot
        if a > 0:
            r = 1.55 * math.sqrt(T.smoother(a / 0.9))
            pos[0] = (CR[0, 0], CR[0, 1], CR_FLOOR[0] + r * 0.9)
            rad[0] = r
    MB.pose(pos + MO, rad)
    dp = DOT_P + np.stack([0.4 * np.sin(DOT_PH + t * 1.1), 0.3 * np.cos(DOT_PH + t * 0.9),
                           0.5 * np.sin(DOT_PH * 2 + t * 0.7)], -1)
    DOTS.set(_sv_[None] * 0.13 + (dp + MO)[:, None, :])


# ================================================================= per-frame pose
def pose(t):
    i = T.shot_index(t)
    s = T.SET_OF[i]
    for k, objs in SETS.items():
        for o in objs:
            o.hide_render = True
    for o in SETS[s]:
        o.hide_render = False
    c, st, sky = WORLD[s]
    WCOL.default_value = (*c, 1)
    WSTR.default_value = st
    WSKY.default_value = sky
    for w_ in NOISE_W:
        w_.default_value = t * 2.5
    if s == "yard":
        pose_yard(t)
    elif s == "lab":
        pose_lab(t)
    elif s == "micro":
        pose_micro(t)


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
if os.environ.get("MG_EXP"):
    exec(os.environ["MG_EXP"])

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
