"""Blender scene for "This Corn Kernel Explodes Inside Out" (Cycles, posed per frame).

Usage: python3 scene.py <out_dir> [--frames a,b,c | --range a b] [--res 1080x1920] [--quality 1.0]
"""
import bpy  # noqa: I001  (bpy must be imported before bmesh)
import bmesh
import math
import os
import random
import sys

import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timeline as T  # noqa: E402

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


def ramp(nt, stops, interp="LINEAR"):
    r = nt.nodes.new("ShaderNodeValToRGB")
    cr = r.color_ramp
    cr.interpolation = interp
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position, cr.elements[0].color = stops[0][0], (*stops[0][1], 1)
    for pos, c in stops[1:]:
        e = cr.elements.new(pos)
        e.color = (*c, 1)
    return r


def shell_bsdf(nt, base, rough=0.35, coat=0.8):
    p = node(nt, "ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (*base, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Coat Roughness"].default_value = 0.08
    return p


def pmat(name, base, rough=0.35, coat=0.8, bump=0.15, bump_scale=14.0):
    """Wet exoskeleton: glossy coat over a coloured base with a fine bump."""
    m, nt, out = new_mat(name)
    p = shell_bsdf(nt, base, rough, coat)
    if bump:
        tc = node(nt, "ShaderNodeTexCoord")
        nz = node(nt, "ShaderNodeTexNoise", Scale=bump_scale, Detail=5.0)
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        bp = node(nt, "ShaderNodeBump", Strength=bump, Distance=0.02)
        nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


def spotted_mat(name, base, spot, scale=9.0, thr=0.08, bump=0.12):
    """Base colour with voronoi spots (the peacock mantis shrimp's leopard dots)."""
    m, nt, out = new_mat(name)
    p = shell_bsdf(nt, base)
    tc = node(nt, "ShaderNodeTexCoord")
    vo = node(nt, "ShaderNodeTexVoronoi", Scale=scale)
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    rp = ramp(nt, [(0.0, spot), (thr, spot), (thr + 0.04, base)])
    nt.links.new(vo.outputs["Distance"], rp.inputs[0])
    nt.links.new(rp.outputs[0], p.inputs["Base Color"])
    nz = node(nt, "ShaderNodeTexNoise", Scale=16.0, Detail=5.0)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = node(nt, "ShaderNodeBump", Strength=bump, Distance=0.02)
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


def emit_mat(name, color, strength):
    m, nt, out = new_mat(name)
    em = node(nt, "ShaderNodeEmission", Color=(*color, 1), Strength=strength)
    nt.links.new(em.outputs[0], out.inputs[0])
    return m, em.inputs["Strength"]


def fade_emit_mat(name, color, strength):
    """Emission mixed with transparency; returns (material, alpha socket, strength socket)."""
    m, nt, out = new_mat(name)
    em = node(nt, "ShaderNodeEmission", Color=(*color, 1), Strength=strength)
    tr = node(nt, "ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    a = node(nt, "ShaderNodeValue")
    a.outputs[0].default_value = 1.0
    nt.links.new(a.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m, a.outputs[0], em.inputs["Strength"]


def soften(mat):
    """Emission fades towards the silhouette: a soft glow instead of a hard disc."""
    _nt = mat.node_tree
    _lw = node(_nt, "ShaderNodeLayerWeight", Blend=0.5)
    _inv = _nt.nodes.new("ShaderNodeMath")
    _inv.operation = "SUBTRACT"
    _inv.inputs[0].default_value = 1.0
    _nt.links.new(_lw.outputs["Facing"], _inv.inputs[1])
    _pw = _nt.nodes.new("ShaderNodeMath")
    _pw.operation = "POWER"
    _pw.inputs[1].default_value = 6.0
    _nt.links.new(_inv.outputs[0], _pw.inputs[0])
    _mul = _nt.nodes.new("ShaderNodeMath")
    _mul.operation = "MULTIPLY"
    _mix = next(n for n in _nt.nodes if n.type == "MIX_SHADER")
    _val = next(n for n in _nt.nodes if n.type == "VALUE")
    _nt.links.new(_val.outputs[0], _mul.inputs[0])
    _nt.links.new(_pw.outputs[0], _mul.inputs[1])
    _nt.links.new(_mul.outputs[0], _mix.inputs[0])


def obj_from(name, verts, faces, mat, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(np.asarray(verts).tolist(), [], faces)
    if smooth:
        me.shade_smooth()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(mat)
    col.objects.link(o)
    return o


def sphere_vf(u=16, v=10):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    bm.verts.index_update()
    vv = np.array([x.co[:] for x in bm.verts])
    ff = [[x.index for x in f.verts] for f in bm.faces]
    bm.free()
    return vv, ff


SPH_V, SPH_F = sphere_vf()


class Builder:
    """Accumulates many transformed primitives into one mesh (fast)."""
    def __init__(self):
        self.v, self.f, self.off = [], [], 0

    def add(self, vv, ff, m):
        M = np.array(m)
        self.v.append(vv @ M[:3, :3].T + M[:3, 3])
        self.f += [[i + self.off for i in fc] for fc in ff]
        self.off += len(vv)

    def sphere(self, loc, scale, rot=(0, 0, 0), vf=None):
        vv, ff = vf or (SPH_V, SPH_F)
        self.add(vv, ff, Matrix.Translation(loc) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*scale, 1)))

    def build(self, name, mat, smooth=True):
        return obj_from(name, np.concatenate(self.v), self.f, mat, smooth)


def tube(name, pts, radii, mat, seg=12):
    """Smooth tube along a polyline with per-point radius."""
    pts = [V(p) for p in pts]
    verts, faces = [], []
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = d.orthogonal().normalized()
        b = d.cross(a)
        for k in range(seg):
            ang = 2 * math.pi * k / seg
            verts.append(p + radii[i] * (math.cos(ang) * a + math.sin(ang) * b))
    for i in range(len(pts) - 1):
        for k in range(seg):
            faces.append([i * seg + k, i * seg + (k + 1) % seg, (i + 1) * seg + (k + 1) % seg, (i + 1) * seg + k])
    n = len(pts)
    for cap, ring in ((pts[0], 0), (pts[-1], n - 1)):          # closed, rounded ends
        d = (pts[1] - pts[0]) if ring == 0 else (pts[-1] - pts[-2])
        verts.append(cap + d.normalized() * radii[ring] * (-0.8 if ring == 0 else 0.8))
        c = len(verts) - 1
        for k in range(seg):
            faces.append([ring * seg + k, ring * seg + (k + 1) % seg, c])
    return obj_from(name, [v[:] for v in verts], faces, mat)


def sph(name, loc, r, mat, u=40, v=20, scale=(1, 1, 1), rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    o = bpy.data.objects.new(name, me)
    o.location, o.scale, o.rotation_euler = loc, scale, rot
    o.data.materials.append(mat)
    col.objects.link(o)
    return o


def empty(name, loc, parent=None):
    o = bpy.data.objects.new(name, None)
    o.location = loc
    o.parent = parent
    col.objects.link(o)
    return o


def area(name, loc, target, energy, size, color, sets):
    l = bpy.data.lights.new(name, "AREA")
    l.energy, l.size, l.color, l.shape = energy, size, color, "DISK"
    o = bpy.data.objects.new(name, l)
    o.location = loc
    o.rotation_euler = (V(loc) - V(target)).to_track_quat("Z", "Y").to_euler()
    col.objects.link(o)
    SETS[sets].append(o)
    return o


def no_bounce(objs):
    for o in objs:
        o.visible_diffuse = False
        o.visible_glossy = False



def xray_mat(name, color, strength, power=2.0, base=0.0):
    """X-ray look: emission strongest at the silhouette, transparent where the surface faces the camera."""
    m, nt, out = new_mat(name)
    em = node(nt, "ShaderNodeEmission", Color=(*color, 1), Strength=strength)
    tr = node(nt, "ShaderNodeBsdfTransparent")
    lw = node(nt, "ShaderNodeLayerWeight", Blend=0.5)
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = power
    nt.links.new(lw.outputs["Facing"], pw.inputs[0])
    ad = nt.nodes.new("ShaderNodeMath")
    ad.operation = "ADD"
    ad.use_clamp = True
    ad.inputs[1].default_value = base
    nt.links.new(pw.outputs[0], ad.inputs[0])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(ad.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m, em.inputs["Strength"]


def principled(name, base, rough=0.5, coat=0.0, emit=None, emit_s=0.0, bump=0.0, bump_scale=12.0):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=rough)
    p.inputs["Base Color"].default_value = (*base, 1)
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Coat Roughness"].default_value = 0.1
    p.inputs["Specular IOR Level"].default_value = 0.3
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = emit_s
    if bump:
        tc = node(nt, "ShaderNodeTexCoord")
        nz = node(nt, "ShaderNodeTexNoise", Scale=bump_scale, Detail=3.0)
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        bp = node(nt, "ShaderNodeBump", Strength=bump, Distance=0.05)
        nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m, p


# ---------------------------------------------------------------- dynamic meshes (constant topology)
def tube_faces(n, seg, off=0):
    f = []
    for i in range(n - 1):
        for k in range(seg):
            f.append([off + i * seg + k, off + i * seg + (k + 1) % seg, off + (i + 1) * seg + (k + 1) % seg,
                      off + (i + 1) * seg + k])
    c0, c1 = off + n * seg, off + n * seg + 1
    for k in range(seg):
        f.append([off + (k + 1) % seg, off + k, c0])
        f.append([off + (n - 1) * seg + k, off + (n - 1) * seg + (k + 1) % seg, c1])
    return f


def tube_verts(pts, radii, seg, ref=(1.0, 0.0, 0.0)):
    pts = np.asarray(pts, float)
    radii = np.asarray(radii, float)
    d = np.gradient(pts, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    a = np.cross(d, np.asarray(ref))
    bad = np.linalg.norm(a, axis=1) < 1e-3
    a[bad] = np.cross(d[bad], [0.0, 1.0, 0.0])
    a /= np.linalg.norm(a, axis=1, keepdims=True) + 1e-9
    b = np.cross(d, a)
    ang = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    ring = (np.cos(ang)[None, :, None] * a[:, None, :] + np.sin(ang)[None, :, None] * b[:, None, :])
    v = pts[:, None, :] + radii[:, None, None] * ring
    v = v.reshape(-1, 3)
    caps = np.array([pts[0] - d[0] * radii[0] * 0.8, pts[-1] + d[-1] * radii[-1] * 0.8])
    return np.concatenate([v, caps])


class Dyn:
    """A mesh object whose vertex positions are rewritten every frame."""
    def __init__(self, name, verts, faces, mat, sets=("earth",), smooth=True):
        self.o = obj_from(name, verts, faces, mat, smooth)
        self.n = len(verts)
        for s in sets:
            SETS[s].append(self.o)

    def set(self, verts):
        v = np.asarray(verts, np.float32).reshape(-1)
        self.o.data.vertices.foreach_set("co", v)
        self.o.data.update()




# ================================================================= sets
SETS = {"pan": [], "section": []}
rng = np.random.default_rng(7)


def to_set(name, *objs):
    for o in objs:
        SETS[name].append(o)
    return objs[0] if len(objs) == 1 else objs


def math_node(nt, op, a=None, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for k, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[k].default_value = v
        else:
            nt.links.new(v, n.inputs[k])
    return n.outputs[0]


def value(nt, v):
    n = nt.nodes.new("ShaderNodeValue")
    n.outputs[0].default_value = v
    return n.outputs[0]


def lathe(name, prof, mat, seg=64, smooth=True):
    """Surface of revolution around Z from a (r, z) profile."""
    verts, faces = [], []
    for r, z in prof:
        for k in range(seg):
            a = 2 * math.pi * k / seg
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(len(prof) - 1):
        for k in range(seg):
            faces.append([i * seg + k, i * seg + (k + 1) % seg, (i + 1) * seg + (k + 1) % seg, (i + 1) * seg + k])
    return obj_from(name, verts, faces, mat, smooth)


def box_vf(x0, x1, y0, y1, z0, z1):
    v = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    f = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]]
    return v, f


def box(name, lo, hi, mat):
    v, f = box_vf(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
    return obj_from(name, v, f, mat, smooth=False)


def link(nt, a, b):
    nt.links.new(a, b)



# ================================================================= world
world = bpy.data.worlds.new("Studio")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
for n_ in list(wnt.nodes):
    if n_.type != "OUTPUT_WORLD":
        wnt.nodes.remove(n_)
wbg = wnt.nodes.new("ShaderNodeBackground")
wbg.inputs["Color"].default_value = (0.006, 0.003, 0.002, 1)
wbg.inputs["Strength"].default_value = 1.0
wnt.links.new(wbg.outputs[0], wnt.nodes["World Output"].inputs[0])


def glow_backdrop(name, loc, size, colors, strength, sets, scale=(0.09, 1.0, 0.09)):
    """A big vertical plane (facing -Y) with a soft spherical-gradient glow in the middle."""
    m, nt, out = new_mat(name)
    tc = node(nt, "ShaderNodeTexCoord")
    mp = node(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    gr = node(nt, "ShaderNodeTexGradient")
    gr.gradient_type = "SPHERICAL"
    link(nt, tc.outputs["Object"], mp.inputs["Vector"])
    link(nt, mp.outputs[0], gr.inputs["Vector"])
    rp = ramp(nt, colors, "EASE")
    link(nt, gr.outputs["Fac"], rp.inputs[0])
    em = node(nt, "ShaderNodeEmission", Strength=strength)
    link(nt, rp.outputs[0], em.inputs["Color"])
    link(nt, em.outputs[0], out.inputs[0])
    h = size
    o = obj_from(name, [(-h, 0, -h), (h, 0, -h), (h, 0, h), (-h, 0, h)], [[0, 1, 2, 3]], m)
    o.location = loc
    for s in sets:
        SETS[s].append(o)
    return o


WARM = [(0.0, (0.0, 0.0, 0.0)), (0.35, (0.05, 0.008, 0.002)), (0.75, (0.32, 0.07, 0.01)), (1.0, (0.75, 0.24, 0.03))]

# ================================================================= kernel geometry
def icosphere(sub):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    bm.verts.index_update()
    vv = np.array([x.co[:] for x in bm.verts])
    ff = [[x.index for x in f.verts] for f in bm.faces]
    bm.free()
    return vv / np.linalg.norm(vv, axis=1, keepdims=True), ff


def kernel_shape(d):
    """Unpopped kernel (local frame: height along z, tip cap at -z, wide along x, thin along y)."""
    x, y, z = d[:, 0], d[:, 1], d[:, 2]
    taper = 1.0 - 0.55 * ((1.0 - z) / 2.0) ** 2
    return np.stack([0.85 * x * taper * (1 + 0.06 * z), 0.55 * y * taper, 1.05 * z], 1)


LOBES = [((0.0, 0.0, 0.35), 1.25), ((1.35, 0.1, 0.9), 1.12), ((-1.3, -0.1, 0.95), 1.1), ((0.1, 1.05, 1.05), 1.0),
         ((-0.1, -1.05, 0.9), 1.0), ((0.95, -0.85, 0.2), 0.9), ((-0.9, 0.9, 0.15), 0.92), ((0.0, 0.1, 2.0), 1.05),
         ((0.75, -0.35, 2.25), 0.8), ((-0.8, 0.4, 2.05), 0.78), ((0.35, -0.25, -1.25), 0.72)]
_lr = np.random.default_rng(11)
for (c_, r_) in list(LOBES[1:10]):
    for _ in range(5):
        u_ = _lr.normal(0, 1, 3)
        u_ /= np.linalg.norm(u_)
        if u_[2] < -0.5:
            u_[2] = -u_[2]
        LOBES.append((tuple(np.array(c_) + u_ * r_ * 0.85), r_ * _lr.uniform(0.32, 0.48)))
LEG_DIR = np.array([0.35, -0.25, -1.25]) / np.linalg.norm([0.35, -0.25, -1.25])
_nrng = np.random.default_rng(3)
NZ_F = _nrng.normal(0, 1, (10, 3))
NZ_F = NZ_F / np.linalg.norm(NZ_F, axis=1, keepdims=True) * _nrng.uniform(5.0, 9.5, (10, 1))
NZ_P = _nrng.uniform(0, 2 * np.pi, 10)


def foam_radius(d):
    """Radius of the popped flake along each direction: smooth union of lobes, plus foam bumps."""
    C = np.array([c for c, _ in LOBES])
    R = np.array([r for _, r in LOBES])

    def sdf(p):
        dist = np.linalg.norm(p[:, None, :] - C[None], axis=2) - R[None]
        k = 0.2
        res = dist[:, 0]
        for j in range(1, len(R)):
            h = np.clip(0.5 + 0.5 * (dist[:, j] - res) / k, 0, 1)
            res = dist[:, j] * (1 - h) + res * h - k * h * (1 - h)
        return res

    rs = np.linspace(4.5, 0.05, 220)
    out = np.full(len(d), 0.5)
    found = np.zeros(len(d), bool)
    for r in rs:
        inside = sdf(d * r) < 0
        new = inside & ~found
        out[new] = r
        found |= inside
    lo, hi = out - 0.025, out + 0.0
    for _ in range(8):
        mid = (lo + hi) / 2
        ins = sdf(d * mid[:, None]) < 0
        lo = np.where(ins, mid, lo)
        hi = np.where(ins, hi, mid)
    bumps = sum(0.03 * np.sin(d @ NZ_F[k] + NZ_P[k]) for k in range(10))
    return lo * (1 + bumps)


class Kernel:
    """A popping kernel as one deforming mesh with a per-vertex 'foam' attribute (shell <-> foam)."""

    def __init__(self, name, sub, mat, sets, scale=1.0):
        d, f = icosphere(sub)
        self.d = d
        self.K = kernel_shape(d) * scale
        rf = foam_radius(d)
        P = d * rf[:, None]
        # keep the bottom (tip cap + some hull) close to the kernel
        bottom = np.clip((-d[:, 2] - 0.55) / 0.35, 0, 1)
        legw = np.exp(-np.sum((d - LEG_DIR) ** 2, 1) / 0.12)
        P = P * (1 - bottom * (1 - legw))[:, None] + self.K / scale * (bottom * (1 - legw))[:, None]
        # volume check, then scale the flake to ~40x the kernel volume
        vk = np.mean(np.linalg.norm(kernel_shape(d), axis=1) ** 3) * 4 * np.pi / 3
        vp = np.mean(np.linalg.norm(P, axis=1) ** 3) * 4 * np.pi / 3
        self.vol_ratio = vp / vk
        P = P * (40.0 / self.vol_ratio) ** (1 / 3)          # puffed to 40x the kernel's volume
        self.P = P * scale
        top = (d[:, 2] + 1) / 2
        self.delay = 0.42 * (1 - top) ** 1.3 * (1 - 0.85 * legw) + 0.02 * _nrng.random(len(d))
        hull = np.clip(0.35 * _nrng.random(len(d)) + 1.2 * np.clip(-d[:, 2] - 0.15, 0, 1) - 0.05, 0, 1.4)
        nz = sum(np.sin(d @ (NZ_F[k] * 0.6) + NZ_P[k]) for k in range(4)) / 4
        self.th = np.clip(0.06 + 0.55 * hull + 0.15 * nz, 0.02, 1.6)
        self.o = obj_from(name, self.K, f, mat)
        me = self.o.data
        me.attributes.new("foam", "FLOAT", "POINT")
        a = me.attributes.new("dir", "FLOAT_VECTOR", "POINT")
        a.data.foreach_set("vector", d.astype(np.float32).reshape(-1))
        for s in sets:
            SETS[s].append(self.o)
        self.M = np.eye(3)
        self.rest_lift = None

    def shape(self, b):
        """Local vertex positions and foam fraction at burst progress b (0..1)."""
        s = np.clip((b - self.delay) / (1 - 0.42), 0, 1)
        e = 1 - (1 - s) ** 3 + 0.07 * np.sin(np.pi * s)
        v = self.K + (self.P - self.K) * e[:, None]
        foam = np.clip((e - self.th) / 0.07, 0, 1)
        return v, foam

    def pose(self, b, M, loc, lift=True, extra_z=0.0, shake=(0, 0, 0), fixed_lift=None):
        v, foam = self.shape(b)
        w = v @ M.T
        lz = -w[:, 2].min() if fixed_lift is None else fixed_lift
        self.o.location = (loc[0] + shake[0], loc[1] + shake[1], (lz if lift else 0.0) + extra_z + shake[2])
        me = self.o.data
        me.vertices.foreach_set("co", w.astype(np.float32).reshape(-1))
        me.attributes["foam"].data.foreach_set("value", foam.astype(np.float32))
        me.update()
        return lz


def frame_from(hz, up=(0.0, 0.0, 1.0)):
    hz = np.asarray(hz, float)
    hz /= np.linalg.norm(hz)
    hx = np.cross(np.asarray(up, float), hz)
    hx /= np.linalg.norm(hx)
    hy = np.cross(hz, hx)
    return np.stack([hx, hy, hz], 1)          # columns: where local x, y, z go


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


# ---------------------------------------------------------------- kernel material: glossy amber hull <-> cream foam
def kernel_mat(name, crack_glow=True):
    m, nt, out = new_mat(name)
    at = node(nt, "ShaderNodeAttribute")
    at.attribute_name = "foam"
    ad = node(nt, "ShaderNodeAttribute")
    ad.attribute_name = "dir"
    sep = node(nt, "ShaderNodeSeparateXYZ")
    link(nt, ad.outputs["Vector"], sep.inputs[0])
    # hull: deep amber-gold, glossy coat, darker toward the tip cap, pale tip
    hz = math_node(nt, "MULTIPLY_ADD", sep.outputs["Z"], 0.5)
    hz.node.inputs[2].default_value = 0.5
    hr = ramp(nt, [(0.0, (0.95, 0.86, 0.62)), (0.1, (0.62, 0.22, 0.02)), (0.35, (0.85, 0.36, 0.02)),
                   (1.0, (1.0, 0.62, 0.06))])
    link(nt, hz, hr.inputs[0])
    hull = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.28)
    hull.inputs["Coat Weight"].default_value = 1.0
    hull.inputs["Coat Roughness"].default_value = 0.06
    hull.inputs["Subsurface Weight"].default_value = 0.0
    hull.inputs["Subsurface Radius"].default_value = (0.4, 0.2, 0.05)
    hull.inputs["Subsurface Scale"].default_value = 0.15
    link(nt, hr.outputs[0], hull.inputs["Base Color"])
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=22.0, Detail=4.0)
    link(nt, ad.outputs["Vector"], nz.inputs["Vector"])
    bp = node(nt, "ShaderNodeBump", Strength=0.08, Distance=0.02)
    link(nt, nz.outputs["Fac"], bp.inputs["Height"])
    link(nt, bp.outputs["Normal"], hull.inputs["Normal"])
    # crack glow on the hull (voronoi edges on the original directions)
    crack_v = value(nt, 0.0)
    if crack_glow:
        vo = node(nt, "ShaderNodeTexVoronoi", Scale=1.8)
        vo.feature = "DISTANCE_TO_EDGE"
        cn = node(nt, "ShaderNodeTexNoise", Scale=3.0, Detail=3.0)
        link(nt, ad.outputs["Vector"], cn.inputs["Vector"])
        cvec = node(nt, "ShaderNodeVectorMath")
        cvec.operation = "MULTIPLY_ADD"
        cvec.inputs[1].default_value = (0.45, 0.45, 0.45)
        link(nt, cn.outputs["Color"], cvec.inputs[0])
        link(nt, ad.outputs["Vector"], cvec.inputs[2])
        link(nt, cvec.outputs[0], vo.inputs["Vector"])
        edge = math_node(nt, "LESS_THAN", vo.outputs["Distance"], 0.016)
        upper = math_node(nt, "GREATER_THAN", sep.outputs["Z"], 0.45)
        ce = math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", edge, upper), crack_v)
        hull.inputs["Emission Color"].default_value = (1.0, 0.85, 0.55, 1)
        ce2 = math_node(nt, "MULTIPLY", ce, 4.0)
        link(nt, ce2, hull.inputs["Emission Strength"])
    # foam: creamy white with a warm yellow tint deep in the folds, porous bump
    foam = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.62)
    foam.inputs["Base Color"].default_value = (1.0, 0.93, 0.78, 1)
    foam.inputs["Subsurface Weight"].default_value = 0.0
    foam.inputs["Subsurface Radius"].default_value = (1.0, 0.75, 0.45)
    foam.inputs["Subsurface Scale"].default_value = 0.25
    foam.inputs["Specular IOR Level"].default_value = 0.25
    vf = node(nt, "ShaderNodeTexVoronoi", Scale=14.0)
    link(nt, tc.outputs["Object"], vf.inputs["Vector"])
    nf = node(nt, "ShaderNodeTexNoise", Scale=6.0, Detail=6.0)
    link(nt, tc.outputs["Object"], nf.inputs["Vector"])
    hsum = math_node(nt, "ADD", math_node(nt, "MULTIPLY", vf.outputs["Distance"], 0.6), nf.outputs["Fac"])
    bf = node(nt, "ShaderNodeBump", Strength=0.6, Distance=0.06)
    link(nt, hsum, bf.inputs["Height"])
    link(nt, bf.outputs["Normal"], foam.inputs["Normal"])
    ao = node(nt, "ShaderNodeAmbientOcclusion", Distance=0.6)
    fr = ramp(nt, [(0.0, (0.82, 0.5, 0.16)), (0.55, (1.0, 0.86, 0.62)), (0.85, (1.0, 0.95, 0.86)), (1.0, (1.0, 0.98, 0.93))])
    link(nt, ao.outputs["AO"], fr.inputs[0])
    link(nt, fr.outputs[0], foam.inputs["Base Color"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    link(nt, at.outputs["Fac"], mix.inputs[0])
    link(nt, hull.outputs[0], mix.inputs[1])
    link(nt, foam.outputs[0], mix.inputs[2])
    link(nt, mix.outputs[0], out.inputs[0])
    return m, crack_v


k_m, CRACK_V = kernel_mat("Kernel")
ko_m, _ = kernel_mat("KernelOther", crack_glow=False)

# ================================================================= pan set
pan_m, _pp = principled("Pan", (0.03, 0.027, 0.025), rough=0.42, bump=0.03, bump_scale=40)
_pp.inputs["Metallic"].default_value = 1.0
_pnt = pan_m.node_tree
PAN_HEAT = value(_pnt, 1.0)
_ptc = node(_pnt, "ShaderNodeTexCoord")
_pgr = node(_pnt, "ShaderNodeTexGradient")
_pgr.gradient_type = "SPHERICAL"
_pmp = node(_pnt, "ShaderNodeMapping")
_pmp.inputs["Scale"].default_value = (0.075, 0.075, 1.0)
link(_pnt, _ptc.outputs["Object"], _pmp.inputs["Vector"])
link(_pnt, _pmp.outputs[0], _pgr.inputs["Vector"])
_pem = math_node(_pnt, "MULTIPLY", math_node(_pnt, "POWER", _pgr.outputs["Fac"], 2.5), PAN_HEAT)
link(_pnt, math_node(_pnt, "MULTIPLY", _pem, 0.1), _pp.inputs["Emission Strength"])
_pp.inputs["Emission Color"].default_value = (1.0, 0.22, 0.03, 1)
PAN = lathe("Pan", [(0.0, -0.05), (11.0, -0.05), (11.6, 0.6), (12.0, 1.6), (12.25, 1.6), (11.8, 0.5),
                    (11.0, -0.35), (0.0, -0.35)], pan_m, seg=128)
to_set("pan", PAN)
glow_backdrop("PanBack", (0.0, 26.0, 6.0), 40.0, WARM, 0.75, ("pan",), scale=(0.06, 1.0, 0.08))

HERO = Kernel("Hero", 6, k_m, ("pan",))
print("flake / kernel volume:", round(HERO.vol_ratio, 1), flush=True)
HERO_M = frame_from((0.5, -0.35, 0.8), up=(0.0, -1.0, 0.2))
REST_LIFT = -((HERO.K @ HERO_M.T)[:, 2].min())
FULL_LIFT = -((HERO.P @ HERO_M.T)[:, 2].min())
CROWN0 = np.array([0.4, -0.3, 1.5])                    # debris origin: the middle of the bursting kernel

OTHER_K = []
for k, (x, y, yaw, tp) in enumerate(T.OTHERS):
    kk = Kernel(f"Other{k}", 4, ko_m, ("pan",), scale=0.6)
    kk.M = rot_z(yaw) @ frame_from((0.8, 0.1, 0.25), up=(0.0, 0.0, 1.0))
    OTHER_K.append(kk)
COMP = Kernel("Compare", 5, ko_m, ("pan",))            # the unpopped kernel for the 40x comparison (S4)
COMP_M = rot_z(0.5) @ HERO_M

# lights (pan)
area("PKey", (-6.0, -8.0, 9.0), (0.0, 0.0, 1.0), 900, 6.0, (1.0, 0.93, 0.85), "pan")
area("PRim", (5.0, 7.0, 5.0), (0.0, 0.0, 1.2), 1100, 4.0, (0.85, 0.9, 1.0), "pan")
area("PFill", (6.0, -6.0, 2.0), (0.0, 0.0, 1.0), 160, 5.0, (1.0, 0.75, 0.5), "pan")
_hl = bpy.data.lights.new("HeatL", "POINT")
_hl.color = (1.0, 0.35, 0.08)
_hl.shadow_soft_size = 2.0
HEAT_L = bpy.data.objects.new("HeatL", _hl)
HEAT_L.location = (0.0, -1.5, 0.25)
col.objects.link(HEAT_L)
SETS["pan"].append(HEAT_L)

# steam puffs on the burst, steam jets and sound rings (S6)
st_m, ST_A, ST_S = fade_emit_mat("Steam", (1.0, 0.97, 0.93), 0.5)
soften(st_m)
NST = 70
_sv, _sf = sphere_vf(10, 6)
STEAM = Dyn("SteamPuffs", np.zeros((NST * len(_sv), 3)), [[i + k * len(_sv) for i in f] for k in range(NST) for f in _sf],
            st_m, sets=("pan",))
ST_DIR = rng.normal(0, 1, (NST, 3))
ST_DIR[:, 2] = np.abs(ST_DIR[:, 2]) + 0.6
ST_DIR /= np.linalg.norm(ST_DIR, axis=1, keepdims=True)
ST_SP = rng.uniform(1.5, 3.5, NST)
ST_R = rng.uniform(0.2, 0.45, NST)
ST_T = rng.uniform(0.0, 0.5, NST)

jt_m, JT_A, JT_S = fade_emit_mat("Jet", (0.92, 0.97, 1.0), 1.6)
soften(jt_m)
NJ = 90
JETS = Dyn("Jets", np.zeros((NJ * len(_sv), 3)), [[i + k * len(_sv) for i in f] for k in range(NJ) for f in _sf],
           jt_m, sets=("pan",))
J_DIR = rng.normal(0, 1, (NJ, 3)) * 0.28 + np.array([0.0, 0.0, 1.0])
J_DIR /= np.linalg.norm(J_DIR, axis=1, keepdims=True)
J_PH = rng.uniform(0, 1, NJ)
J_SP = rng.uniform(4.0, 7.0, NJ)

# flying debris on every burst: glossy hull chips and white starch crumbs, thrown toward the camera
chip_m, _cp = principled("Chip", (1.0, 0.5, 0.04), rough=0.25, coat=1.0, emit=(1.0, 0.55, 0.1), emit_s=0.6)
crumb_m, _cr = principled("Crumb", (1.0, 0.95, 0.85), rough=0.6, emit=(1.0, 0.92, 0.8), emit_s=0.5)
TET = np.array([(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)], float) / math.sqrt(3)
TETF = [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]]
NCH, NCR = 320, 340


def debris(n, name, mat, flat):
    base = TET[None, :, :] * rng.uniform(0.5, 1.5, (n, 4, 1))
    if flat:
        base[:, :, 2] *= 0.25                                   # thin curved hull flakes
    dyn = Dyn(name, np.zeros((n * 4, 3)), [[i + 4 * k for i in f] for k in range(n) for f in TETF], mat,
              sets=("pan",), smooth=False)
    d = rng.normal(0, 1, (n, 3))
    d[:, 1] = -np.abs(d[:, 1]) * 1.1 - 0.2                     # toward the camera
    d[:, 2] = np.abs(d[:, 2]) + 0.2
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    return dict(dyn=dyn, base=base, dir=d, sp=rng.uniform(6.0, 15.0, n), size=rng.uniform(0.04, 0.12, n) * (1.6 if flat else 1.0),
                ax=rng.normal(0, 1, (n, 3)), spin=rng.uniform(6, 20, n), t0=rng.uniform(0.0, 0.12, n))


CHIPS = debris(NCH, "HullChips", chip_m, True)
CRUMBS = debris(NCR, "Crumbs", crumb_m, False)


def pose_debris(D, age, origin):
    n = len(D["sp"])
    a = age - D["t0"]
    live = (a > 0) & (a < 2.5)
    a = np.clip(a, 0, None)
    pos = origin[None] + D["dir"] * (1.3 + D["sp"][:, None] * (1 - np.exp(-a / 0.55))[:, None] * 0.55) \
        + np.array([0, 0, -1.0])[None] * (a ** 2)[:, None] * 0.6
    ang = D["spin"] * a
    ax = D["ax"] / np.linalg.norm(D["ax"], axis=1, keepdims=True)
    c, s_ = np.cos(ang)[:, None, None], np.sin(ang)[:, None, None]
    b = D["base"]
    k = ax[:, None, :]
    rotd = b * c + np.cross(k, b) * s_ + k * np.sum(k * b, 2, keepdims=True) * (1 - c)
    shrink = np.clip(1 - (a - 1.6) / 0.9, 0, 1)
    v = rotd * (D["size"] * shrink * live * np.clip(a / 0.04, 0, 1))[:, None, None] + pos[:, None, :]
    v[~live] = np.array([0, 0, -50.0])
    D["dyn"].set(v.reshape(-1, 3))


RINGS = []
for k in range(4):
    rm, ra, rs_ = fade_emit_mat(f"Ring{k}", (1.0, 0.85, 0.55), 5.0)
    ro = lathe(f"Ring{k}", [(0.97, -0.006), (1.0, 0.0), (1.03, -0.006), (1.0, -0.012)], rm, seg=96, smooth=False)
    to_set("pan", ro)
    RINGS.append((ro, ra, rs_))

# ================================================================= section set
SX, SY, SZ = T.SECTION
# back half of the kernel (y >= 0), upright
NTH, NPH = 72, 48
th = np.linspace(0, np.pi, NTH)
ph = np.linspace(0, np.pi, NPH)
TH, PH = np.meshgrid(th, ph, indexing="ij")
D_half = np.stack([np.sin(TH) * np.cos(PH), np.sin(TH) * np.sin(PH), np.cos(TH)], -1).reshape(-1, 3)
HV = kernel_shape(D_half)
HF = [[i * NPH + j, i * NPH + j + 1, (i + 1) * NPH + j + 1, (i + 1) * NPH + j] for i in range(NTH - 1) for j in range(NPH - 1)]
sec_hull_m, _sh = principled("SecHull", (1.0, 0.55, 0.05), rough=0.3, coat=1.0, bump=0.05, bump_scale=20)
SEC_HULL = obj_from("SecHull", HV, HF, sec_hull_m)
SEC_HULL.location = (SX, SY, SZ)
to_set("section", SEC_HULL)
# the cut face at y = 0: rings from the outline to the centre, attribute rel = radius fraction
NA, NR = 160, 26
ang = np.linspace(0, 2 * np.pi, NA, endpoint=False)
OUTL = kernel_shape(np.stack([np.sin(ang), np.zeros(NA), np.cos(ang)], 1))
CEN = np.array([0.0, 0.0, 0.05])
fv, rel = [], []
for j in range(NR):
    s = 1 - j / NR
    for a in range(NA):
        fv.append(CEN + (OUTL[a] - CEN) * s)
        rel.append(s)
fv.append(CEN)
rel.append(0.0)
ff = []
for j in range(NR - 1):
    for a in range(NA):
        ff.append([j * NA + a, j * NA + (a + 1) % NA, (j + 1) * NA + (a + 1) % NA, (j + 1) * NA + a])
c_ = len(fv) - 1
for a in range(NA):
    ff.append([(NR - 1) * NA + a, (NR - 1) * NA + (a + 1) % NA, c_])
sec_m, nt_s, out_s = new_mat("SecFace")
_ra = node(nt_s, "ShaderNodeAttribute")
_ra.attribute_name = "rel"
_sr = ramp(nt_s, [(0.0, (0.98, 0.95, 0.88)), (0.66, (0.98, 0.94, 0.84)), (0.74, (1.0, 0.78, 0.3)),
                  (0.9, (1.0, 0.7, 0.18)), (0.915, (0.75, 0.25, 0.02)), (1.0, (0.85, 0.35, 0.03))])
link(nt_s, _ra.outputs["Fac"], _sr.inputs[0])
_sp = node(nt_s, "ShaderNodeBsdfPrincipled", Roughness=0.45)
_sp.inputs["Subsurface Weight"].default_value = 0.3
_sp.inputs["Subsurface Scale"].default_value = 0.1
link(nt_s, _sr.outputs[0], _sp.inputs["Base Color"])
_stc = node(nt_s, "ShaderNodeTexCoord")
_svo = node(nt_s, "ShaderNodeTexVoronoi", Scale=30.0)
link(nt_s, _stc.outputs["Object"], _svo.inputs["Vector"])
_sb = node(nt_s, "ShaderNodeBump", Strength=0.25, Distance=0.02)
link(nt_s, _svo.outputs["Distance"], _sb.inputs["Height"])
link(nt_s, _sb.outputs["Normal"], _sp.inputs["Normal"])
# heat: the shell ring glows orange-red from the bottom up
SEC_HEAT = value(nt_s, 0.0)
_sz = node(nt_s, "ShaderNodeSeparateXYZ")
link(nt_s, _stc.outputs["Object"], _sz.inputs[0])
_hz = math_node(nt_s, "SUBTRACT", 0.6, _sz.outputs["Z"])
_ring = math_node(nt_s, "GREATER_THAN", _ra.outputs["Fac"], 0.9)
_he = math_node(nt_s, "MULTIPLY", math_node(nt_s, "MULTIPLY", _ring, math_node(nt_s, "MAXIMUM", _hz, 0.0)), SEC_HEAT)
link(nt_s, math_node(nt_s, "MULTIPLY", _he, 2.2), _sp.inputs["Emission Strength"])
_sp.inputs["Emission Color"].default_value = (1.0, 0.3, 0.04, 1)
link(nt_s, _sp.outputs[0], out_s.inputs[0])
SEC_FACE = obj_from("SecFace", fv, ff, sec_m)
_ar = SEC_FACE.data.attributes.new("rel", "FLOAT", "POINT")
_ar.data.foreach_set("value", np.array(rel, np.float32))
SEC_FACE.location = (SX, SY, SZ)
to_set("section", SEC_FACE)
# the drop of water
wd_m, _wp = principled("WaterDrop", (0.15, 0.5, 1.0), rough=0.05, coat=1.0, emit=(0.1, 0.45, 1.0), emit_s=0.9)
_wp.inputs["Transmission Weight"].default_value = 0.35
WDROP = sph("WaterDrop", (SX, SY - 0.02, SZ + 0.05), 0.3, wd_m, u=48, v=24, scale=(1, 0.55, 1))
to_set("section", WDROP)
# steam particles bouncing inside the starch, in front of the face
sp_m, SP_A, SP_S = fade_emit_mat("SteamDot", (0.85, 0.95, 1.0), 4.0)
NP = 150
_pv, _pf = sphere_vf(10, 6)
SDOTS = Dyn("SteamDots", np.zeros((NP * len(_pv), 3)), [[i + k * len(_pv) for i in f] for k in range(NP) for f in _pf],
            sp_m, sets=("section",))
P_POS = rng.uniform(-0.6, 0.6, (NP, 2))
P_VEL = rng.normal(0, 1, (NP, 2))
P_VEL /= np.linalg.norm(P_VEL, axis=1, keepdims=True)
P_R = rng.uniform(0.025, 0.045, NP)
# pre-simulate the bounce at unit speed (parameter = travelled path length)
SIM_STEP, SIM_N = 0.01, 3200
SIM = np.zeros((SIM_N, NP, 2))
pp, vv_ = P_POS.copy() * 0.3, P_VEL.copy()
for i in range(SIM_N):
    pp = pp + vv_ * SIM_STEP
    # inside an ellipse a little smaller than the starch (x 0.62, z 0.82)
    q = (pp[:, 0] / 0.6) ** 2 + ((pp[:, 1] - 0.05) / 0.8) ** 2
    out_ = q > 1
    if out_.any():
        nrm = np.stack([pp[:, 0] / 0.36, (pp[:, 1] - 0.05) / 0.64], 1)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        dv = np.sum(vv_ * nrm, 1, keepdims=True)
        vv_ = np.where(out_[:, None] & (dv > 0), vv_ - 2 * dv * nrm, vv_)
        pp = np.where(out_[:, None], pp / np.sqrt(q)[:, None] * 0.999, pp)
    SIM[i] = pp
# pressure arrows around the shell (pointing outward)
ar_m, ARR_A, ARR_S = fade_emit_mat("PArrow", (1.0, 0.55, 0.1), 3.0)
ARROWS = []
for k in range(12):
    a = 2 * math.pi * (k + 0.5) / 12
    o = OUTL[int(a / (2 * math.pi) * NA) % NA]
    nrm = V((o[0] / 0.72, 0.0, o[2] / 1.1)).normalized()
    shaft = tube(f"ArrShaft{k}", [(0, 0, 0), (0, 0, 0.32)], [0.035, 0.035], ar_m, seg=10)
    head = lathe(f"ArrHead{k}", [(0.0, 0.5), (0.09, 0.3), (0.0, 0.3)], ar_m, seg=16, smooth=False)
    piv = empty(f"Arr{k}", (0, 0, 0))
    shaft.parent = piv
    head.parent = piv
    piv.rotation_euler = V((0, 0, 1)).rotation_difference(nrm).to_euler()
    to_set("section", piv, shaft, head)
    ARROWS.append((piv, V((SX + o[0], SY - 0.05, SZ + o[2])), nrm))
# the hot plate under the kernel, and the backdrop
hp_m, _hpp = principled("HotPlate", (0.03, 0.028, 0.026), rough=0.35, emit=(1.0, 0.13, 0.02), emit_s=0.0)
_hpp.inputs["Metallic"].default_value = 1.0
HOTPLATE = box("HotPlate", (SX - 4.0, SY - 3.0, SZ - 1.45), (SX + 4.0, SY + 3.0, SZ - 1.05), hp_m)
to_set("section", HOTPLATE)
HP_EMIT = _hpp.inputs["Emission Strength"]
glow_backdrop("SecBack", (SX, 14.0, SZ + 1.0), 30.0, WARM, 1.3, ("section",), scale=(0.075, 1.0, 0.075))
area("SKey", (SX - 4.0, SY - 6.0, SZ + 5.0), (SX, SY, SZ), 380, 5.0, (1.0, 0.95, 0.88), "section")
area("SRim", (SX + 4.0, SY + 4.0, SZ + 3.0), (SX, SY, SZ), 500, 3.0, (0.85, 0.9, 1.0), "section")
_sl = bpy.data.lights.new("SecHeatL", "POINT")
_sl.color = (1.0, 0.3, 0.05)
_sl.shadow_soft_size = 1.0
SEC_HEAT_L = bpy.data.objects.new("SecHeatL", _sl)
SEC_HEAT_L.location = (SX, SY - 1.2, SZ - 0.9)
col.objects.link(SEC_HEAT_L)
SETS["section"].append(SEC_HEAT_L)


# ================================================================= per-frame posing
def crack_point():
    """World position of the kernel's crown (where the crack opens)."""
    v = HERO.o.data.vertices
    top = int(np.argmax(HERO.d[:, 2]))
    return V(HERO.o.location) + V(v[top].co)


def pose_pan(t):
    i = T.shot_index(t)
    b = T.burst(t)
    h = T.heat(t)
    PAN_HEAT.default_value = 0.35 + 0.65 * h
    HEAT_L.data.energy = 30 + 90 * h
    CRACK_V.default_value = T.crack(t) * (1 - T.smoother(b / 0.25))
    tr = T.tremble(t)
    shake = (tr * math.sin(t * 83), tr * math.sin(t * 71), abs(tr * math.sin(t * 97)))
    fz, turns = T.flip(t)
    if i == 5 and t >= T.FLIP_T0:
        u = T.clamp((t - T.FLIP_T0) / T.FLIP_DUR)
        lz0 = HERO.pose(T.burst(T.FLIP_T0), HERO_M, (0, 0, 0))
        lz = T.lerp(lz0, FULL_LIFT, u)
        HERO.pose(b, rot_y(2 * math.pi * turns) @ HERO_M, (0.0, 0.0), fixed_lift=lz, extra_z=fz)
    else:
        HERO.pose(b, HERO_M, (0.0, 0.0), shake=shake)
    # others
    for k, kk in enumerate(OTHER_K):
        x, y, yaw, tp = T.OTHERS[k]
        kk.pose(T.other_burst(k, t), kk.M, (x, y))
    COMP.o.hide_render = i != 4
    if i == 4:
        COMP.pose(0.0, COMP_M, (-1.7, -2.6))
    # steam puffs: from the crown, during the first 1.3 s of the burst
    b0 = T.burst_start(t)
    age = (t - b0) if b0 is not None and b0 > -50 else -1.0
    cp = np.array(crack_point())
    w = []
    alpha = 0.0
    for k in range(NST):
        a = age - ST_T[k]
        if 0 < a < 1.4:
            p = cp + ST_DIR[k] * ST_SP[k] * (1 - math.exp(-a / 0.5)) + np.array([0, 0, 0.6 * a])
            r = ST_R[k] * (0.5 + 1.6 * a)
        else:
            p, r = np.array([0.0, 0.0, -50.0]), 0.001
        w.append(_sv * r + p)
    STEAM.set(np.concatenate(w))
    ST_A.default_value = 0.0
    STEAM.o.hide_render = True
    # debris from the crown on every burst
    if 0 <= age < 2.6:
        pose_debris(CHIPS, age, CROWN0)
        pose_debris(CRUMBS, age, CROWN0)
    else:
        pose_debris(CHIPS, -9.0, cp)
        pose_debris(CRUMBS, -9.0, cp)
    # jets (S6)
    j = T.jets(t)
    w = []
    for k in range(NJ):
        if j > 0.01:
            ph_ = ((t * J_SP[k] / 3.0) + J_PH[k]) % 1.0
            p = cp + J_DIR[k] * (0.2 + 3.2 * ph_)
            r = 0.025 * (1 + 2.0 * ph_)
            dj = J_DIR[k]
            v_ = _sv * r
            v_ = v_ + dj[None, :] * (v_ @ dj)[:, None] * 9.0          # streaks along the jet
            w.append(v_ + p)
        else:
            w.append(_sv * 0.001 + np.array([0, 0, -50.0]))
    JETS.set(np.concatenate(w))
    JT_A.default_value = 0.12 * j
    # sound rings (S6): expanding, facing the camera
    ages = T.sound_rings(t)
    loc, tgt, _l = T.camera(t)
    q = (V(loc) - V(cp)).to_track_quat("Z", "Y")
    for k, (ro, ra, rs_) in enumerate(RINGS):
        if k < len(ages):
            a = ages[k]
            ro.location = V(cp) + V((0, 0, 0.2))
            ro.rotation_mode = "QUATERNION"
            ro.rotation_quaternion = q
            s = 0.5 + 2.6 * T.ease_out(a / 1.1)
            ro.scale = (s, s, s * 3)
            ra.default_value = 0.9 * (1 - a / 1.1) ** 1.5
            ro.hide_render = False
        else:
            ro.hide_render = True


def pose_section(t):
    sh = T.section_heat(t)
    SEC_HEAT.default_value = sh
    HP_EMIT.default_value = 0.35 * sh
    SEC_HEAT_L.data.energy = 25 * sh
    bl = 1 + T.bulge(t)
    for o in (SEC_HULL, SEC_FACE):
        o.scale = (bl, bl, bl)
    WDROP.scale = (T.water_drop(t), 0.55 * T.water_drop(t), T.water_drop(t))
    amt, sp = T.steam(t)
    # travelled path: integrate the speed from the start of the steam
    t0 = T.T_STEAM - 0.15
    n = 40
    path = sum(T.steam(t0 + (t - t0) * (k + 0.5) / n)[1] for k in range(n)) * max(0.0, t - t0) / n
    idx = min(SIM_N - 1, int(path / SIM_STEP))
    pos = SIM[idx]
    w = []
    for k in range(NP):
        if k < amt * NP:
            born = T.clamp((amt * NP - k) / 12.0)
            px, pz = pos[k] * born
            p = np.array([SX + px * bl, SY - 0.07, SZ + 0.05 + pz * bl])
            w.append(_pv * P_R[k] * born + p)
        else:
            w.append(_pv * 0.001 + np.array([SX, SY - 50.0, SZ]))
    SDOTS.set(np.concatenate(w))
    SP_A.default_value = 1.0
    p = (T.pressure(t) - 1) / 8
    for k, (piv, base, nrm) in enumerate(ARROWS):
        pulse = 0.5 + 0.5 * math.sin(t * 12 + k * 0.7)
        piv.location = V((SX, SY, SZ)) + (base - V((SX, SY, SZ))) * bl + nrm * (0.08 + 0.06 * pulse * p)
        s = 0.4 + 0.9 * p
        piv.scale = (s, s, s)
    ARR_A.default_value = T.smoother(p * 3)
    ARR_S.default_value = 2.0 + 3.0 * p


def pose(t):
    st = T.shot_set(t)
    for name, objs in SETS.items():
        for o in objs:
            o.hide_render = name != st
    if st == "pan":
        pose_pan(t)
    else:
        pose_section(t)


def cam_shake(t):
    b0 = T.burst_start(t)
    if T.shot_set(t) != "pan" or b0 is None or b0 < -50:
        return (0, 0, 0)
    u = t - b0 - 0.05
    if 0 < u < 0.7:
        k = 0.03 * math.exp(-u / 0.18)
        return (k * math.sin(u * 61), 0, k * math.sin(u * 47))
    return (0, 0, 0)


# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.clip_start = 0.02
cam_d.clip_end = 500
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
c.adaptive_threshold = 0.08
c.use_denoising = True
c.denoising_quality = "BALANCED"
c.denoising_prefilter = "ACCURATE"
c.max_bounces = 8
c.diffuse_bounces = 1
c.glossy_bounces = 3
c.transparent_max_bounces = 16
c.transmission_bounces = 4
c.caustics_reflective = False
c.caustics_refractive = False
c.blur_glossy = 1.0
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0
except Exception:
    pass

SPP = {"pan": 16, "section": 12}
if os.environ.get("PC_EXP"):
    exec(os.environ["PC_EXP"])

for f in FRAMES:
    t = f / T.FPS
    path = os.path.join(OUT, f"f_{f:04d}.png")
    if os.path.exists(path):
        continue
    pose(t)
    loc, tgt, lens = T.camera(t)
    loc = tuple(a + b for a, b in zip(loc, cam_shake(t)))
    cam.location = loc
    cam.rotation_quaternion = (V(tgt) - V(loc)).to_track_quat("-Z", "Y")
    cam_d.lens = lens
    scene.frame_set(f)
    c.samples = max(4, int(SPP[T.shot_set(t)] * QUALITY))
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"rendered {f} ({T.shot_set(t)})", flush=True)
print("done")
