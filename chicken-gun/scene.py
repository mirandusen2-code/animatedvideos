"""Blender scene for "Engineers Fire Chickens at Airplanes" (Cycles, posed per frame). 1 unit = 1 ft.

Sets (only the active one is rendered; the lab floor and lights belong to every lab set):
  lab    the bird-strike rig: 60 ft air cannon aimed at an airliner cockpit nose; chicken A hits the windshield
  old    an old flat windshield on a stand, shattered by chicken B at 75 mph
  scale  a bench scale: chicken C drops on it (4 lb)
  gun    the breech of the cannon: chicken D is loaded, then fired out of the muzzle
  froz   a table: chicken F frozen in an ice block, then thawed
  sky    an airliner in flight with birds (S2) and over New York with geese in both engines (S3)

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
    def __init__(self, name, verts, faces, mat, sets=("lab",), smooth=True):
        self.o = obj_from(name, verts, faces, mat, smooth)
        self.n = len(verts)
        for s in sets:
            SETS[s].append(self.o)

    def set(self, verts):
        v = np.asarray(verts, np.float32).reshape(-1)
        self.o.data.vertices.foreach_set("co", v)
        self.o.data.update()





SETS = {k: [] for k in ("lab", "old", "scale", "gun", "froz", "sky")}
LABS = ("lab", "old", "scale", "gun", "froz")
rng = np.random.default_rng(7)


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





def put(o, s):
    SETS[s].append(o)
    return o


def icosphere(sub):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    v = np.array([x.co[:] for x in bm.verts])
    f = [[x.index for x in fa.verts] for fa in bm.faces]
    bm.free()
    return v / np.linalg.norm(v, axis=1, keepdims=True), f


class Noise:
    """Smooth pseudo-noise on the unit sphere: a sum of random plane waves (octaves)."""
    def __init__(self, seed, octaves=((3.0, 1.0), (6.0, 0.5), (12.0, 0.25), (24.0, 0.12)), n=8):
        g = np.random.default_rng(seed)
        self.terms = []
        for fr, amp in octaves:
            F = g.normal(0, 1, (n, 3))
            F = F / np.linalg.norm(F, axis=1, keepdims=True) * fr * g.uniform(0.8, 1.2, (n, 1))
            self.terms.append((F, g.uniform(0, 2 * np.pi, n), amp / math.sqrt(n)))

    def __call__(self, d):
        out = np.zeros(len(d))
        for F, ph, a in self.terms:
            out += a * np.sin(d @ F.T + ph).sum(1)
        return out


def attr_mesh(o, names):
    """Per-vertex float attributes, written every frame (drive emission / alpha in the shader)."""
    for n in names:
        o.data.attributes.new(n, "FLOAT", "POINT")


def set_attr(o, name, vals):
    o.data.attributes[name].data.foreach_set("value", np.asarray(vals, np.float32))


def attr_node(nt, name):
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = name
    return a.outputs["Fac"]


def glass_mat(name, tint, ior=1.45, rough=0.03):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=rough, IOR=ior)
    p.inputs["Base Color"].default_value = (*tint, 1)
    p.inputs["Transmission Weight"].default_value = 1.0
    nt.links.new(p.outputs[0], out.inputs[0])
    return m, p


def beam_mat(name, color, strength):
    """Additive-looking laser shaft: emission over transparency; returns (mat, alpha, strength)."""
    m, a, s = fade_emit_mat(name, color, strength)
    return m, a, s


TET = np.array([(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)], float) / math.sqrt(3)
TETF = [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]]
UV = (0.42, 0.3, 1.0)                     # the 351 nm UV beams, shown violet
GOLD = (1.0, 0.72, 0.32)


def rand_dirs(n, g):
    d = g.normal(0, 1, (n, 3))
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def basis(d):
    d = np.asarray(d, float)
    a = np.cross(d, [0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.cross(d, [1.0, 0.0, 0.0])
    a /= np.linalg.norm(a)
    return a, np.cross(d, a)


def tubes_verts(p0, p1, r, seg=6):
    """Many straight tubes at once (n,3)->(n*(seg*2+2),3); faces from tubes_faces."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    n = len(p0)
    d = p1 - p0
    ln = np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    d = d / ln
    ref = np.where(np.abs(d[:, 2:3]) < 0.9, np.array([[0, 0, 1.0]]), np.array([[1.0, 0, 0]]))
    a = np.cross(d, ref)
    a /= np.linalg.norm(a, axis=1, keepdims=True)
    b = np.cross(d, a)
    ang = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    rr = np.asarray(r, float).reshape(-1, 1, 1) if np.ndim(r) else r
    ring = np.cos(ang)[None, :, None] * a[:, None, :] + np.sin(ang)[None, :, None] * b[:, None, :]
    v0 = p0[:, None, :] + rr * ring
    v1 = p1[:, None, :] + rr * ring
    v = np.concatenate([v0, v1, p0[:, None, :], p1[:, None, :]], axis=1)
    return v.reshape(n * (2 * seg + 2), 3)


def tubes_faces(n, seg=6):
    f = []
    st = 2 * seg + 2
    for k in range(n):
        o = k * st
        for j in range(seg):
            j1 = (j + 1) % seg
            f.append([o + j, o + j1, o + seg + j1, o + seg + j])
            f.append([o + j1, o + j, o + 2 * seg])
            f.append([o + seg + j, o + seg + j1, o + 2 * seg + 1])
    return f



def puts(o, sets):
    for s in ((sets,) if isinstance(sets, str) else sets):
        SETS[s].append(o)
    return o


def light(name, kind, loc, target, energy, size, color, sets):
    l = bpy.data.lights.new(name, kind)
    l.energy, l.color = energy, color
    if kind == "AREA":
        l.size, l.shape = size, "DISK"
    elif kind == "SPOT":
        l.shadow_soft_size = size
        l.spot_size = math.radians(50)
        l.spot_blend = 0.6
    else:
        l.shadow_soft_size = size
    o = bpy.data.objects.new(name, l)
    o.location = tuple(loc)
    if target is not None:
        o.rotation_euler = (V(tuple(loc)) - V(tuple(target))).to_track_quat("Z", "Y").to_euler()
    col.objects.link(o)
    return puts(o, sets), l


def rodrigues(ax, ang):
    """Rotation matrices (n,3,3) from unit axes (n,3) and angles (n,)."""
    ax = np.asarray(ax, float)
    c, s = np.cos(ang)[:, None, None], np.sin(ang)[:, None, None]
    K = np.zeros((len(ax), 3, 3))
    K[:, 0, 1], K[:, 0, 2], K[:, 1, 2] = -ax[:, 2], ax[:, 1], -ax[:, 0]
    K[:, 1, 0], K[:, 2, 0], K[:, 2, 1] = ax[:, 2], -ax[:, 1], ax[:, 0]
    I = np.eye(3)[None]
    return I + s * K + (1 - c) * (K @ K)


def smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


# ================================================================= world: dark lab, or a blue sky (camera rays)
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
for n_ in list(wnt.nodes):
    if n_.type != "OUTPUT_WORLD":
        wnt.nodes.remove(n_)
_wtc = wnt.nodes.new("ShaderNodeTexCoord")
_wsep = wnt.nodes.new("ShaderNodeSeparateXYZ")
wnt.links.new(_wtc.outputs["Generated"], _wsep.inputs[0])
_wsky = ramp(wnt, [(0.0, (0.2, 0.32, 0.5)), (0.5, (0.24, 0.38, 0.62)), (0.56, (0.1, 0.24, 0.55)),
                   (1.0, (0.02, 0.07, 0.26))])
wnt.links.new(_wsep.outputs["Z"], _wsky.inputs[0])
_wmix = wnt.nodes.new("ShaderNodeMixRGB")
_wmix.inputs[1].default_value = (0.006, 0.007, 0.009, 1)      # lab: near black
wnt.links.new(_wsky.outputs[0], _wmix.inputs[2])
WSKY = _wmix.inputs[0]
WSKY.default_value = 0.0
_wbg = wnt.nodes.new("ShaderNodeBackground")
wnt.links.new(_wmix.outputs[0], _wbg.inputs["Color"])
_wstr = _wbg.inputs["Strength"]
_wstr.default_value = 1.0
wnt.links.new(_wbg.outputs[0], wnt.nodes["World Output"].inputs[0])

# ================================================================= materials
paint_m, _ = principled("Paint", (0.82, 0.83, 0.85), rough=0.28, coat=0.6)
radome_m, _ = principled("Radome", (0.30, 0.32, 0.35), rough=0.4, coat=0.3)
stripe_m, _ = principled("Stripe", (0.06, 0.22, 0.55), rough=0.3, coat=0.5)
win_m, _ = principled("CockpitGlass", (0.015, 0.02, 0.026), rough=0.05, coat=1.0)
frame_m, _ = principled("WinFrame", (0.015, 0.016, 0.018), rough=0.6)
steel_m, _steel = principled("Steel", (0.35, 0.36, 0.38), rough=0.35)
_steel.inputs["Metallic"].default_value = 0.9
gunm_m, _gunm = principled("Gunmetal", (0.12, 0.13, 0.15), rough=0.3, coat=0.3)
_gunm.inputs["Metallic"].default_value = 0.8
yellow_m, _ = principled("SafetyYellow", (0.95, 0.65, 0.05), rough=0.45)
bore_m, _ = principled("Bore", (0.01, 0.01, 0.012), rough=0.6)


def concrete_mat():
    m, nt, out = new_mat("Concrete")
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.75)
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=0.08, Detail=4.0)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    r = ramp(nt, [(0.3, (0.16, 0.16, 0.17)), (0.7, (0.24, 0.24, 0.25))])
    nt.links.new(nz.outputs["Fac"], r.inputs[0])
    nt.links.new(r.outputs[0], p.inputs["Base Color"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


def feather_mat(name, base=(0.86, 0.84, 0.79)):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.65)
    p.inputs["Sheen Weight"].default_value = 0.6
    p.inputs["Subsurface Weight"].default_value = 0.15
    p.inputs["Subsurface Radius"].default_value = (0.1, 0.08, 0.06)
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=26.0, Detail=3.0)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = node(nt, "ShaderNodeBump", Strength=0.25, Distance=0.01)
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    mix = nt.nodes.new("ShaderNodeMixRGB")                  # base colour, or frost (driven per frame)
    mix.inputs[1].default_value = (*base, 1)
    mix.inputs[2].default_value = (0.55, 0.72, 0.9, 1)
    mix.inputs[0].default_value = 0.0
    nt.links.new(mix.outputs[0], p.inputs["Base Color"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m, mix.inputs[0]


feath_m, _ = feather_mat("Feather")
frost_m, FROST = feather_mat("FrostFeather")
comb_m, _ = principled("Comb", (0.72, 0.04, 0.03), rough=0.4, coat=0.3)
beak_m, _ = principled("Beak", (0.98, 0.62, 0.08), rough=0.4)
eye_m, _ = principled("Eye", (0.01, 0.01, 0.01), rough=0.1, coat=1.0)

# ================================================================= the lab floor + lights (all lab sets)
floor = puts(obj_from("Floor", [(-500, -500, 0), (500, -500, 0), (500, 500, 0), (-500, 500, 0)], [[0, 1, 2, 3]],
                      concrete_mat(), smooth=False), LABS)
# painted safety lines along the firing line
for k, x in enumerate((-4.0, 4.0)):
    puts(box(f"Line{k}", (G.P_I[0] + x - 0.15, -130, 0.0), (G.P_I[0] + x + 0.15, -2, 0.01), yellow_m), "lab")

PI_ = G.P_I
light("LabKey", "AREA", (PI_[0] - 30, PI_[1] - 25, 40), PI_, 60000, 25, (1.0, 0.96, 0.9), "lab")
light("LabRim", "AREA", (PI_[0] + 35, PI_[1] + 20, 30), PI_, 30000, 18, (0.75, 0.85, 1.0), "lab")
light("LabFill", "AREA", (PI_[0] - 10, PI_[1] - 90, 25), (PI_[0], PI_[1] - 60, 5), 40000, 30, (1.0, 0.95, 0.9), "lab")

# ================================================================= the cockpit nose (test article)
def nose_mesh(L, ns=70, nphi=72):
    ss = np.concatenate([np.linspace(0.0, G.NOSE_LN, ns) ** 1.0, np.linspace(G.NOSE_LN, L, 8)[1:]])
    ss[0] = 0.0
    phis = np.linspace(-math.pi, math.pi, nphi, endpoint=False)
    S_, P_ = np.meshgrid(ss, phis, indexing="ij")
    v = G.surf(S_, P_).reshape(-1, 3)
    f = []
    for i in range(len(ss) - 1):
        for k in range(nphi):
            k1 = (k + 1) % nphi
            f.append([i * nphi + k, (i + 1) * nphi + k, (i + 1) * nphi + k1, i * nphi + k1])
    # back cap
    c = len(v)
    v = np.vstack([v, [[0.0, L, G.zc_of(L)]]])
    i = len(ss) - 1
    for k in range(nphi):
        f.append([i * nphi + k, i * nphi + (k + 1) % nphi, c])
    return v, f, ss


_nv, _nf, _nss = nose_mesh(G.NOSE_L)
primer_m, _ = principled("Primer", (0.3, 0.38, 0.34), rough=0.4, coat=0.2)
NOSE = obj_from("Nose", _nv, _nf, primer_m)
NOSE.data.materials.append(radome_m)
NOSE.data.materials.append(stripe_m)
_nphi = 72
for pi_, pg in enumerate(NOSE.data.polygons):
    i = pi_ // _nphi if pi_ < (len(_nss) - 1) * _nphi else len(_nss) - 1
    sm = _nss[min(i, len(_nss) - 1)]
    cz = np.mean([_nv[j][2] for j in pg.vertices])
    if sm < 1.9:
        pg.material_index = 1
    elif sm > 8.6 and G.NOSE_ZC - 2.6 < cz < G.NOSE_ZC - 1.5:
        pg.material_index = 2
puts(NOSE, "lab")


def patch(name, s0, s1, p0, p1, off, mat, n=(12, 14)):
    ss = np.linspace(s0, s1, n[0])
    ps = np.linspace(p0, p1, n[1])
    S_, P_ = np.meshgrid(ss, ps, indexing="ij")
    v = G.surf(S_, P_) + G.normal(S_, P_) * off
    v = v.reshape(-1, 3)
    f = [[i * n[1] + k, i * n[1] + k + 1, (i + 1) * n[1] + k + 1, (i + 1) * n[1] + k]
         for i in range(n[0] - 1) for k in range(n[1] - 1)]
    return puts(obj_from(name, v, f, mat), "lab")


for nm, (s0, s1), (p0, p1) in (("PaneL", G.PANE_S, G.PANE_L), ("PaneR", G.PANE_S, G.PANE_R),
                               ("SideL", G.SIDE_S, G.SIDE_L), ("SideR", G.SIDE_S, G.SIDE_R)):
    patch(nm, s0, s1, p0, p1, 0.05, win_m)
    m = math.radians(2.5)
    patch(nm + "Frame", s0 - 0.25, s1 + 0.25, p0 - m, p1 + m, 0.03, frame_m)

# stand under the nose: two steel cradles + columns
for k, y in enumerate((9.0, 19.0)):
    puts(box(f"ColL{k}", (-4.2, y - 0.6, 0), (-3.0, y + 0.6, G.NOSE_ZC - 5.0), steel_m), "lab")
    puts(box(f"ColR{k}", (3.0, y - 0.6, 0), (4.2, y + 0.6, G.NOSE_ZC - 5.0), steel_m), "lab")
    puts(box(f"Beam{k}", (-5.0, y - 0.7, G.NOSE_ZC - 6.2), (5.0, y + 0.7, G.NOSE_ZC - 5.0), steel_m), "lab")
puts(box("Base", (-7, 6, 0), (7, 22, 0.6), steel_m), "lab")

# ================================================================= the air cannon (barrel along +Y)
def ylathe(name, prof, mat, origin, seg=48):
    """lathe around Z, then turned so Z -> +Y, placed at origin."""
    o = lathe(name, prof, mat, seg)
    o.rotation_euler = (-math.pi / 2, 0, 0)
    o.location = tuple(origin)
    return o


_blen = 60.0
_bprof = [(G.BORE_R, 0.0), (0.95, 0.0), (0.95, _blen - 1.2), (1.15, _blen - 1.2), (1.15, _blen), (G.BORE_R, _blen),
          (G.BORE_R, 0.3)]
BARREL = puts(ylathe("Barrel", _bprof, gunm_m, G.BREECH), ("lab", "gun"))
BOREIN = puts(ylathe("BoreDark", [(G.BORE_R - 0.01, 0.3), (G.BORE_R - 0.01, _blen - 0.05)], bore_m, G.BREECH),
              ("lab", "gun"))
for k in range(1, 6):
    y = k * 10.0
    puts(ylathe(f"Flange{k}", [(0.94, y - 0.3), (1.25, y - 0.3), (1.25, y + 0.3), (0.94, y + 0.3)], gunm_m,
                G.BREECH), ("lab", "gun"))
for k in range(5):
    y = G.BREECH[1] + 6 + k * 12.5
    bz = G.BREECH[2]
    puts(box(f"Stand{k}", (G.P_I[0] - 1.6, y - 0.4, 0), (G.P_I[0] + 1.6, y + 0.4, 0.5), steel_m), ("lab", "gun"))
    puts(box(f"StandP{k}", (G.P_I[0] - 0.3, y - 0.3, 0.5), (G.P_I[0] + 0.3, y + 0.3, bz - 0.9), yellow_m),
         ("lab", "gun"))
    puts(box(f"StandC{k}", (G.P_I[0] - 1.1, y - 0.35, bz - 1.1), (G.P_I[0] + 1.1, y + 0.35, bz - 0.85), yellow_m),
         ("lab", "gun"))
# pressure tank beside the breech, pipe into the breech
_tk = G.BREECH + np.array([6.0, 4.0, 0.0])
TANK = puts(ylathe("Tank", [(0.0, -6.0), (2.2, -5.6), (2.8, -4.6), (2.8, 4.6), (2.2, 5.6), (0.0, 6.0)], gunm_m,
                   _tk), ("lab", "gun"))
puts(box("TankStand", (_tk[0] - 2.4, _tk[1] - 4, 0), (_tk[0] + 2.4, _tk[1] + 4, _tk[2] - 2.5), steel_m),
     ("lab", "gun"))
puts(tube("Pipe", [tuple(_tk + np.array([-2.6, 0, 0])), tuple(G.BREECH + np.array([1.5, 4.0, 0])),
                   tuple(G.BREECH + np.array([0.8, 4.0, 0]))], [0.35, 0.35, 0.35], steel_m), ("lab", "gun"))
puts(sph("Gauge", tuple(_tk + np.array([-1.4, -2.0, 2.4])), 0.55, steel_m, scale=(1, 0.35, 1)), ("lab", "gun"))
puts(sph("GaugeFace", tuple(_tk + np.array([-1.4, -2.2, 2.4])), 0.46,
         emit_mat("GaugeFace", (0.95, 0.95, 0.9), 0.6)[0], scale=(1, 0.1, 1)), ("lab", "gun"))
GAUGE_P = _tk + np.array([-1.4, -2.3, 2.4])
light("GunKey", "AREA", G.BREECH + np.array([-14, -10, 14]), G.BREECH + np.array([0, 4, 0]), 9000, 10,
      (1.0, 0.95, 0.88), "gun")
light("GunRim", "AREA", G.BREECH + np.array([10, -6, 10]), G.BREECH, 5000, 8, (0.7, 0.85, 1.0), "gun")
light("GunMuzzle", "AREA", G.MUZZLE + np.array([-9, 10, 8]), G.MUZZLE, 16000, 10, (1.0, 0.96, 0.9), "gun")
light("GunMuzzle2", "AREA", G.MUZZLE + np.array([8, 4, 6]), G.MUZZLE, 8000, 8, (0.7, 0.85, 1.0), "gun")
puts(floor, "gun")


# ================================================================= chickens
def build_chicken(name, sets, feather=None, scale=1.0):
    """A white hen, ~1.25 ft long, head along local +X, up +Z. Returns the root empty."""
    root = empty(name, (0, 0, 0))
    fm = feather or feath_m
    bw, bc, bb, be = Builder(), Builder(), Builder(), Builder()
    bw.sphere((0, 0, 0), (0.42, 0.30, 0.31))
    bw.sphere((0.17, 0, -0.06), (0.29, 0.27, 0.26))
    bw.sphere((-0.33, 0, 0.1), (0.22, 0.2, 0.2), (0, 0.5, 0))
    for k in range(5):                                       # tail fan
        a = (k - 2) * 0.3
        bw.sphere((-0.5, 0.06 * (k - 2), 0.3), (0.17, 0.03, 0.09), (a * 0.3, -0.9, 0))
    for sgn in (-1, 1):                                      # wings folded on the sides
        bw.sphere((-0.03, sgn * 0.26, 0.05), (0.34, 0.07, 0.18), (sgn * 0.15, 0.12, 0))
        bw.sphere((-0.3, sgn * 0.22, 0.12), (0.2, 0.05, 0.1), (sgn * 0.2, 0.35, 0))
    bw.sphere((0.36, 0, 0.17), (0.14, 0.12, 0.19), (0, -0.45, 0))      # neck
    bw.sphere((0.47, 0, 0.33), (0.11, 0.095, 0.1))                    # head
    for k, (x, z, r) in enumerate(((0.42, 0.43, 0.035), (0.47, 0.45, 0.045), (0.52, 0.435, 0.04), (0.56, 0.41, 0.03))):
        bc.sphere((x, 0, z), (r, 0.018, r))
    bc.sphere((0.55, 0, 0.235), (0.03, 0.016, 0.05))
    for sgn in (-1, 1):
        bc.sphere((0.535, sgn * 0.045, 0.27), (0.022, 0.012, 0.035))
    bb.add(*cone_vf(0.06, 0.12), Matrix.Translation((0.55, 0, 0.32)) @ Matrix.Rotation(math.radians(-100), 4, "Y"))
    for sgn in (-1, 1):
        be.sphere((0.525, sgn * 0.075, 0.355), (0.018, 0.012, 0.018))
        # legs tucked back
        bb.add(*tube_vf([(-0.05, sgn * 0.1, -0.24), (-0.22, sgn * 0.11, -0.31), (-0.36, sgn * 0.11, -0.3)],
                        [0.035, 0.03, 0.025]), Matrix.Identity(4))
    parts = []
    for b, m, nm in ((bw, fm, "Body"), (bc, comb_m, "Comb"), (bb, beak_m, "Beak"), (be, eye_m, "Eye")):
        o = b.build(f"{name}{nm}", m)
        o.parent = root
        parts.append(puts(o, sets))
    root.scale = (scale, scale, scale)
    return root, parts


def cone_vf(r, h, seg=12):
    v = [(r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), 0.0) for k in range(seg)]
    v += [(0, 0, h), (0, 0, 0)]
    f = [[k, (k + 1) % seg, seg] for k in range(seg)] + [[(k + 1) % seg, k, seg + 1] for k in range(seg)]
    return np.array(v), f


def tube_vf(pts, radii, seg=10):
    pts = [V(p) for p in pts]
    verts, faces = [], []
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = d.orthogonal().normalized()
        b = d.cross(a)
        for k in range(seg):
            ang = 2 * math.pi * k / seg
            verts.append(tuple(p + radii[i] * (math.cos(ang) * a + math.sin(ang) * b)))
    for i in range(len(pts) - 1):
        for k in range(seg):
            faces.append([i * seg + k, i * seg + (k + 1) % seg, (i + 1) * seg + (k + 1) % seg, (i + 1) * seg + k])
    n = len(pts)
    for ring in (0, n - 1):
        verts.append(tuple(pts[ring]))
        c = len(verts) - 1
        for k in range(seg):
            faces.append([ring * seg + k, ring * seg + (k + 1) % seg, c])
    return np.array(verts), faces


def show(parts, on):
    for o in parts:
        o.hide_render = not bool(on)


# heading: local +X -> world +Y (towards the nose)
ROT_FWD = (0.0, 0.0, math.pi / 2)
CHA, CHA_P = build_chicken("ChickA", "lab")
CHB, CHB_P = build_chicken("ChickB", "old")
CHC, CHC_P = build_chicken("ChickC", "scale")
CHD, CHD_P = build_chicken("ChickD", "gun", scale=0.92)
CHF, CHF_P = build_chicken("ChickF", "froz", feather=frost_m)
for r_ in (CHA, CHB, CHD):
    r_.rotation_euler = ROT_FWD


# ================================================================= feather bursts (one Dyn per burst)
def feather_shape(g, n, lmin, lmax):
    L = g.uniform(lmin, lmax, n)
    W = L * g.uniform(0.22, 0.32, n)
    cv = g.uniform(-0.8, 0.8, n)
    xs = np.array([0.0, 0.33, 0.66, 1.0])
    prof = np.array([0.25, 1.0, 0.85, 0.2])
    out = np.zeros((n, 8, 3))
    for j in range(4):
        x = xs[j] * L
        for side, sg in ((0, -1), (1, 1)):
            out[:, j * 2 + side, 0] = x - 0.4 * L
            out[:, j * 2 + side, 1] = sg * 0.5 * W * prof[j]
            out[:, j * 2 + side, 2] = cv * (xs[j] - 0.4) ** 2 * L
    f = []
    for k in range(n):
        o = k * 8
        for j in range(3):
            f.append([o + 2 * j, o + 2 * j + 1, o + 2 * j + 3, o + 2 * j + 2])
    return out, f


class Burst:
    """Feathers (or fluff tets) flying out of an impact: p(a) = p0 + v0 (1 - e^-ka)/k - g a^2/2 + flutter."""
    def __init__(self, name, n, sets, seed, mat, kind="feather", size=(0.16, 0.36)):
        g = np.random.default_rng(seed)
        self.g, self.n, self.kind = g, n, kind
        if kind == "feather":
            self.L, f = feather_shape(g, n, *size)
        else:
            self.L = np.repeat(TET[None] * 1.0, n, 0) * g.uniform(*size, (n, 1, 1))
            f = [[k * 4 + a for a in tri] for k in range(n) for tri in TETF]
        self.dyn = Dyn(name, np.zeros((n * self.L.shape[1], 3)), f, mat, sets=sets, smooth=False)
        self.ax = rand_dirs(n, g)
        self.w = g.uniform(3.0, 12.0, n) * g.choice([-1, 1], n)
        self.ph = g.uniform(0, 6.28, n)
        self.R0 = rodrigues(rand_dirs(n, g), g.uniform(0, 6.28, n))
        self.flut = g.uniform(0.05, 0.25, n)

    def emit(self, p0, v0, t0, k, grav):
        self.p0, self.v0, self.t0 = np.asarray(p0, float), np.asarray(v0, float), np.asarray(t0, float)
        self.k = np.asarray(k, float) * np.ones(self.n)
        self.grav = grav

    def pose(self, te, offset=None):
        a = np.maximum(0.0, te - self.t0)
        on = (te >= self.t0).astype(float)
        k = self.k
        p = self.p0 + self.v0 * ((1 - np.exp(-k * a)) / k)[:, None]
        p[:, 2] -= 0.5 * self.grav * a * a
        p[:, 0] += self.flut * np.sin(3.0 * a + self.ph) * np.minimum(1.0, a * 3)
        if offset is not None:
            p = p + offset
        R = rodrigues(self.ax, self.w * a + self.ph) @ self.R0
        sc = on * np.minimum(1.0, 0.3 + a * 20.0)
        v = np.einsum("kij,kvj->kvi", R, self.L * sc[:, None, None]) + p[:, None, :]
        self.dyn.set(v)


TET = np.array([(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)], float) / math.sqrt(3)
TETF = [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]]
fluff_m, _ = principled("Fluff", (0.92, 0.9, 0.86), rough=0.8)


def spray(burst, center, nrm, g, n_out=(2.0, 12.0), n_rad=(5.0, 22.0), t_span=0.18, k=(1.2, 3.5), grav=3.0,
          along=None, r0=0.45):
    """Set up a radial spray across the surface with normal nrm (plus some out of it)."""
    n = burst.n
    nrm = np.asarray(nrm, float) / np.linalg.norm(nrm)
    a, b = basis(nrm)
    th = g.uniform(0, 2 * math.pi, n)
    rad = np.cos(th)[:, None] * a + np.sin(th)[:, None] * b
    p0 = center + rad * g.uniform(0.05, r0, n)[:, None] + nrm * g.uniform(0.0, 0.3, n)[:, None]
    v0 = rad * g.uniform(*n_rad, n)[:, None] + nrm * g.uniform(*n_out, n)[:, None]
    if along is not None:
        v0 = v0 + np.asarray(along)[None] * g.uniform(0.5, 1.0, n)[:, None]
    t0 = g.uniform(-0.01, t_span, n) ** 1.0
    burst.emit(p0, v0, t0, g.uniform(*k, n), grav)


# --- impact A on the cockpit windshield
FA = Burst("FeathersA", 750, ("lab",), 11, feath_m)
spray(FA, G.P_I + G.N_I * 0.2, G.N_I, np.random.default_rng(12))
FLA = Burst("FluffA", 1400, ("lab",), 13, fluff_m, kind="tet", size=(0.015, 0.04))
spray(FLA, G.P_I + G.N_I * 0.15, G.N_I, np.random.default_rng(14), n_out=(1.0, 9.0), n_rad=(4.0, 26.0),
      t_span=0.12, k=(2.0, 5.0), grav=1.5)

# --- cracks on the captain's pane, mapped from local (u, v) around the impact onto the curved surface
_dps = np.linalg.norm(G.surf(G.S_I + 0.01, G.PHI_I) - G.surf(G.S_I - 0.01, G.PHI_I)) / 0.02
_ri = float(G.r_of(G.S_I))


def on_pane(uv, off=0.075):
    uv = np.asarray(uv, float)
    s = G.S_I - uv[..., 1] / _dps            # v up the windshield (towards the tip is down)
    ph = G.PHI_I + uv[..., 0] / _ri
    return G.surf(s, ph) + G.normal(s, ph) * off


def crack_paths(g):
    paths = []
    nr = 17
    for k in range(nr):
        th = 2 * math.pi * k / nr + g.uniform(-0.15, 0.15)
        L = g.uniform(0.9, 1.55)
        rr = np.linspace(0.05, L, 9)
        th_j = th + np.cumsum(g.normal(0, 0.07, 9))
        paths.append(np.stack([rr * np.cos(th_j), rr * np.sin(th_j)], -1))
    for R_ in (0.28, 0.55, 0.9):
        m = 26
        th = np.linspace(0, 2 * math.pi, m)
        rr = R_ * (1 + g.normal(0, 0.06, m))
        rr[-1] = rr[0]
        pts = np.stack([rr * np.cos(th), rr * np.sin(th)], -1)
        # break the ring into pieces with gaps
        for j in range(0, m - 1, 3):
            if g.random() < 0.75:
                paths.append(pts[j:j + 3])
    return paths


_cp = crack_paths(np.random.default_rng(21))
CR_V, CR_F, CR_R = [], [], []
for pth in _cp:
    for j in range(len(pth) - 1):
        a0, a1 = pth[j], pth[j + 1]
        d = (a1 - a0) / (np.linalg.norm(a1 - a0) + 1e-9)
        nrm2 = np.array([-d[1], d[0]])
        w = 0.012 + 0.012 * math.exp(-np.linalg.norm(a0) / 0.4)
        o = len(CR_V)
        CR_V += [a0 - nrm2 * w, a0 + nrm2 * w, a1 + nrm2 * w, a1 - nrm2 * w]
        CR_F.append([o, o + 1, o + 2, o + 3])
        CR_R += [np.linalg.norm(a0)] * 2 + [np.linalg.norm(a1)] * 2
CR_UV = np.array(CR_V)
CR_R = np.array(CR_R)
crack_m, _ = principled("Crack", (0.9, 0.93, 0.95), rough=0.2, emit=(0.8, 0.88, 1.0), emit_s=0.6)
CRACK = Dyn("Cracks", on_pane(CR_UV * 0), CR_F, crack_m, sets=("lab",), smooth=False)

# snarge: a flattened cream splat on the pane
splat_m, _ = principled("Splat", (0.85, 0.8, 0.7), rough=0.35, coat=0.6)
SPLAT = puts(sph("Splat", tuple(G.P_I), 1.0, splat_m, 24, 12), "lab")
SPLAT.rotation_euler = V(tuple(G.N_I)).to_track_quat("Z", "Y").to_euler()


def pose_lab_impact(te):
    """te: time since chicken A touched the pane (slow motion seconds); negative = still flying in."""
    if te is None:
        te = -9.0
    V_IN = 26.0
    fwd = G.GUN_DIR
    if te < 0:
        show(CHA_P, True)
        CHA.location = tuple(G.P_I - fwd * (0.62 + V_IN * (-te)))
        CHA.scale = (1, 1, 1)
        CHA.rotation_euler = (0.0, 0.0, math.pi / 2)
    else:
        q = min(1.0, te / 0.2)
        sq = 1.0 - 0.72 * smooth01(q)                     # squash along the flight direction
        wide = 1.0 + 0.75 * smooth01(q)
        fade = 1.0 - smooth01((te - 0.24) / 0.24)        # the body disappears into the feather cloud
        show(CHA_P, fade > 0.02)
        CHA.location = tuple(G.P_I - fwd * (0.62 * sq) + G.N_I * 0.05)
        CHA.scale = (sq * max(fade, 0.02), wide * max(fade, 0.02), wide * max(fade, 0.02))
    FA.pose(te)
    FLA.pose(te)
    g = smooth01(te / 0.06) if te > -0.005 else 0.0
    vis = (CR_R <= 0.05 + g * 1.6).astype(float)[:, None]
    uv = CR_UV * vis + (1 - vis) * CR_UV[::1] * 0.0
    CRACK.set(on_pane(uv))
    CRACK.o.hide_render = bool(te < 0)
    s = smooth01(te / 0.2) * (te > 0)
    SPLAT.hide_render = bool(s < 0.01)
    SPLAT.scale = (0.75 * s + 0.01, 0.55 * s + 0.01, 0.06)


# ================================================================= set "old": flat 1950s-style pane, shattered
OC = G.OLD_O + np.array([0.0, 0.0, 6.0])        # pane centre; pane in the x-z plane, chicken flies +Y
OW, OH, OT = 3.4, 2.4, 0.06
_g = np.random.default_rng(31)
_nx, _nz = 21, 15
gx = np.linspace(-OW / 2, OW / 2, _nx)
gz = np.linspace(-OH / 2, OH / 2, _nz)
GX, GZ = np.meshgrid(gx, gz, indexing="ij")
jit = np.zeros_like(GX), np.zeros_like(GZ)
GXj = GX + np.where((np.abs(GX) < OW / 2 - 1e-6), _g.uniform(-0.06, 0.06, GX.shape), 0)
GZj = GZ + np.where((np.abs(GZ) < OH / 2 - 1e-6), _g.uniform(-0.05, 0.05, GZ.shape), 0)
tris = []
for i in range(_nx - 1):
    for j in range(_nz - 1):
        p00, p10 = (GXj[i, j], GZj[i, j]), (GXj[i + 1, j], GZj[i + 1, j])
        p01, p11 = (GXj[i, j + 1], GZj[i, j + 1]), (GXj[i + 1, j + 1], GZj[i + 1, j + 1])
        if _g.random() < 0.5:
            tris += [(p00, p10, p11), (p00, p11, p01)]
        else:
            tris += [(p00, p10, p01), (p10, p11, p01)]
tris = np.array(tris)                                   # (n,3,2) in (x,z)
NS = len(tris)
SC_ = tris.mean(1)
SH_LOC = np.zeros((NS, 6, 3))
for k in range(3):
    SH_LOC[:, k, 0] = tris[:, k, 0] - SC_[:, 0]
    SH_LOC[:, k, 2] = tris[:, k, 1] - SC_[:, 1]
    SH_LOC[:, k, 1] = -OT / 2
    SH_LOC[:, k + 3] = SH_LOC[:, k]
    SH_LOC[:, k + 3, 1] = OT / 2
SH_F = []
for k in range(NS):
    o = k * 6
    SH_F += [[o, o + 2, o + 1], [o + 3, o + 4, o + 5], [o, o + 1, o + 4, o + 3], [o + 1, o + 2, o + 5, o + 4],
             [o + 2, o, o + 3, o + 5]]
OHIT = np.array([0.25, 0.2])                           # hit point in pane coords (x, z)
_d = np.linalg.norm(SC_ - OHIT, axis=1)
SH_T = _d / 16.0
SH_FREE = _d < 1.6
_dir = (SC_ - OHIT) / (_d[:, None] + 1e-6)
SH_V = np.zeros((NS, 3))
SH_V[:, 1] = (5.0 + 16.0 * np.exp(-_d / 0.7)) * _g.uniform(0.6, 1.2, NS)
SH_V[:, 0] = _dir[:, 0] * _g.uniform(1.0, 6.0, NS)
SH_V[:, 2] = _dir[:, 1] * _g.uniform(1.0, 6.0, NS) + _g.uniform(-1, 2, NS)
SH_AX = rand_dirs(NS, _g)
SH_W = _g.uniform(2.0, 9.0, NS)
oglass_m, _ = glass_mat("OldGlass", (0.88, 0.97, 0.94), ior=1.5, rough=0.02)
SHARDS = Dyn("OldShards", np.zeros((NS * 6, 3)), SH_F, oglass_m, sets=("old",), smooth=False)
OPANE = puts(box("OldPane", tuple(OC + (-OW / 2, -OT / 2, -OH / 2)), tuple(OC + (OW / 2, OT / 2, OH / 2)), oglass_m), "old")
# frame + stand
for nm, lo, hi in (("OFt", (-OW / 2 - 0.25, -0.15, OH / 2), (OW / 2 + 0.25, 0.15, OH / 2 + 0.25)),
                   ("OFb", (-OW / 2 - 0.25, -0.15, -OH / 2 - 0.25), (OW / 2 + 0.25, 0.15, -OH / 2)),
                   ("OFl", (-OW / 2 - 0.25, -0.15, -OH / 2), (-OW / 2, 0.15, OH / 2)),
                   ("OFr", (OW / 2, -0.15, -OH / 2), (OW / 2 + 0.25, 0.15, OH / 2))):
    puts(box(nm, tuple(OC + lo), tuple(OC + hi), steel_m), "old")
for sx in (-1, 1):
    x0 = sx * (OW / 2 + 0.1)
    puts(box(f"OLeg{sx}", tuple(G.OLD_O + (x0 - 0.15, -0.15, 0)), tuple(G.OLD_O + (x0 + 0.15, 0.15, 6.0 - OH / 2)),
         steel_m), "old")
    puts(box(f"OFoot{sx}", tuple(G.OLD_O + (x0 - 0.4, -1.5, 0)), tuple(G.OLD_O + (x0 + 0.4, 1.5, 0.3)), steel_m),
         "old")
_om = G.OLD_O + np.array([0.25, -32.0, 6.2])
puts(ylathe("OldGun", [(0.5, 0.0), (0.8, 0.0), (0.8, 30.0), (0.5, 30.0)], gunm_m, _om - np.array([0, 30, 0])), "old")
light("OldKey", "AREA", OC + np.array([-12, 10, 10]), OC, 9000, 10, (1.0, 0.95, 0.88), "old")
light("OldBack", "AREA", OC + np.array([6, -14, 6]), OC, 9000, 12, (0.7, 0.85, 1.0), "old")
light("OldFill", "AREA", OC + np.array([10, 12, 2]), OC, 3000, 10, (1.0, 0.9, 0.8), "old")
FB = Burst("FeathersB", 380, ("old",), 33, feath_m)
FLB = Burst("FluffB", 600, ("old",), 34, fluff_m, kind="tet", size=(0.015, 0.035))


def pose_old(te):
    if te is None:
        te = -9.0
    hit = OC + np.array([OHIT[0], 0.0, OHIT[1]])
    # chicken: in at 30 ft/s, through the pane, slowing to 14 ft/s, slightly falling
    if te < 0:
        y = -0.62 - 30.0 * (-te)
    else:
        y = -0.62 + 14.0 * te + 16.0 * (1 - math.exp(-te / 0.3)) * 0.3 * 3
    CHB.location = tuple(hit + np.array([0.15 * max(te, 0), y, -1.2 * max(te, 0) ** 2]))
    CHB.rotation_euler = (0.0, 0.25 * max(te, 0), math.pi / 2 + 0.3 * max(te, 0))
    a = np.maximum(0.0, te - SH_T) * SH_FREE
    R = rodrigues(SH_AX, SH_W * a)
    pos = np.zeros((NS, 3))
    pos[:, 0], pos[:, 2] = SC_[:, 0], SC_[:, 1]
    pos = pos + OC + SH_V * ((1 - np.exp(-0.6 * a)) / 0.6)[:, None]
    pos[:, 2] -= 0.5 * 12.0 * a * a
    v = np.einsum("kij,kvj->kvi", R, SH_LOC) + pos[:, None, :]
    SHARDS.set(v)
    SHARDS.o.hide_render = bool(te < 0)
    OPANE.hide_render = bool(te >= 0)
    off = np.array([0.0, (y + 0.62) if te > 0 else 0.0, 0.0]) * 0.0
    FB.pose(te)
    FLB.pose(te)


_go = np.random.default_rng(35)
_hb = OC + np.array([OHIT[0], 0.1, OHIT[1]])
spray(FB, _hb, np.array([0.0, 1.0, 0.0]), _go, n_out=(6.0, 20.0), n_rad=(2.0, 10.0), t_span=0.3, k=(0.8, 2.0),
      grav=4.0)
spray(FLB, _hb, np.array([0.0, 1.0, 0.0]), _go, n_out=(4.0, 18.0), n_rad=(2.0, 14.0), t_span=0.25, k=(1.5, 3.5),
      grav=2.0)


# ================================================================= set "scale": a bench scale on a workbench
SO = G.SCALE_O
wood_m, _ = principled("Wood", (0.32, 0.2, 0.11), rough=0.55, coat=0.2)
TOPZ = 3.0
puts(box("Bench", tuple(SO + (-4.0, -2.2, TOPZ - 0.25)), tuple(SO + (4.0, 2.2, TOPZ)), wood_m), "scale")
for sx in (-1, 1):
    for sy in (-1, 1):
        puts(box(f"BLeg{sx}{sy}", tuple(SO + (sx * 3.6 - 0.15, sy * 1.9 - 0.15, 0)),
                 tuple(SO + (sx * 3.6 + 0.15, sy * 1.9 + 0.15, TOPZ - 0.25)), steel_m), "scale")
dark_m, _ = principled("ScaleBody", (0.05, 0.055, 0.06), rough=0.35, coat=0.4)
puts(box("ScaleBase", tuple(SO + (-1.1, -0.9, TOPZ)), tuple(SO + (1.1, 0.9, TOPZ + 0.28)), dark_m), "scale")
puts(box("ScalePlate", tuple(SO + (-1.0, -0.82, TOPZ + 0.28)), tuple(SO + (1.0, 0.82, TOPZ + 0.34)), steel_m), "scale")
puts(box("ScalePost", tuple(SO + (-0.08, 0.95, TOPZ)), tuple(SO + (0.08, 1.1, TOPZ + 1.3)), dark_m), "scale")
puts(box("ScaleHead", tuple(SO + (-0.6, 0.85, TOPZ + 1.3)), tuple(SO + (0.6, 1.15, TOPZ + 1.85)), dark_m), "scale")
scr_m = emit_mat("Screen", (0.05, 0.12, 0.08), 0.6)[0]
puts(box("ScaleScreen", tuple(SO + (-0.5, 0.83, TOPZ + 1.38)), tuple(SO + (0.5, 0.86, TOPZ + 1.77)), scr_m), "scale")
SCREEN_P = SO + np.array([0.0, 0.84, TOPZ + 1.575])
PLATE_Z = TOPZ + 0.34
light("ScKey", "AREA", SO + (-6, -7, 8), SO + (0, 0, TOPZ), 5000, 7, (1.0, 0.95, 0.88), "scale")
light("ScRim", "AREA", SO + (5, 5, 6), SO + (0, 0, TOPZ), 3500, 6, (0.7, 0.85, 1.0), "scale")
light("ScFill", "AREA", SO + (6, -6, 3), SO + (0, 0, TOPZ), 1200, 6, (1.0, 0.9, 0.8), "scale")


def pose_scale(te):
    """te: time since the chicken lands on the plate."""
    if te is None:
        te = -9.0
    h0 = 2.6
    base = PLATE_Z + 0.33
    if te < 0:
        fall = max(0.0, 0.5 * 18.0 * (te + 0.54) ** 2) if te > -0.54 else 0.0
        z = base + h0 - min(h0, fall) if te > -0.54 else base + h0
        sq = 1.0
    else:
        z = base + 0.12 * math.exp(-te / 0.12) * abs(math.sin(te * 18.0))
        sq = 1.0 - 0.22 * math.exp(-te / 0.08) * math.cos(te * 30)
    CHC.location = tuple(SO + np.array([0.0, -0.1, 0.0]) + np.array([0, 0, z]))
    CHC.rotation_euler = (0.0, 0.0, math.radians(-30))
    CHC.scale = (1 / math.sqrt(sq), 1 / math.sqrt(sq), sq)


# ================================================================= set "gun": loading at the breech, then the muzzle
foam_m, _ = principled("Sabot", (0.9, 0.35, 0.08), rough=0.8)
SABOT = puts(ylathe("Sabot", [(0.0, -0.9), (0.58, -0.9), (0.58, 0.2), (0.0, 0.2)], foam_m, (0, 0, 0)), "gun")
PUFF = Burst("MuzzlePuff", 500, ("gun", "lab"), 41, fluff_m, kind="tet", size=(0.03, 0.08))
_gp = np.random.default_rng(42)
_n = PUFF.n
_th = _gp.uniform(0, 2 * math.pi, _n)
_rd = np.stack([np.cos(_th), np.zeros(_n), np.sin(_th)], -1)
PUFF.emit(G.MUZZLE + _rd * _gp.uniform(0.3, 0.9, _n)[:, None],
          _rd * _gp.uniform(2, 8, _n)[:, None] + np.array([0, 1, 0]) * _gp.uniform(2, 16, _n)[:, None],
          _gp.uniform(0.0, 0.08, _n), _gp.uniform(1.5, 4.0, _n), 0.5)


def pose_gun(tl, tf):
    """tl: time since loading starts (chicken slides into the breech); tf: time since the shot leaves the muzzle."""
    if tl is None:
        tl = -9.0
    if tf is None:
        tf = -9.0
    if tf < 0:
        x = smooth01(tl / 0.7)
        y = G.BREECH[1] - 2.4 + 3.2 * x
        CHD.location = tuple(np.array([G.BREECH[0], y, G.BREECH[2] - 0.05]))
        SABOT.location = tuple(np.array([G.BREECH[0], y - 0.55, G.BREECH[2]]))
        show(CHD_P, True)
        SABOT.hide_render = False
    else:
        CHD.location = tuple(G.MUZZLE + G.GUN_DIR * (0.4 + 22.0 * tf) + np.array([0, 0, -0.05]))
        SABOT.hide_render = True
        show(CHD_P, True)
    PUFF.pose(tf)
    PUFF.dyn.o.hide_render = bool(tf < 0)


# ================================================================= set "froz": chicken frozen in an ice block
FO = G.FROZ_O
steelt_m, _ = principled("SteelTable", (0.45, 0.46, 0.48), rough=0.25)
puts(box("FTable", tuple(FO + (-3.5, -2.0, TOPZ - 0.15)), tuple(FO + (3.5, 2.0, TOPZ)), steelt_m), "froz")
for sx in (-1, 1):
    for sy in (-1, 1):
        puts(box(f"FLeg{sx}{sy}", tuple(FO + (sx * 3.2 - 0.12, sy * 1.7 - 0.12, 0)),
                 tuple(FO + (sx * 3.2 + 0.12, sy * 1.7 + 0.12, TOPZ - 0.15)), steel_m), "froz")


def superbox(hx, hy, hz, e=0.25, u=40, v=20):
    vv, ff = sphere_vf(u, v)
    s = np.sign(vv) * np.abs(vv) ** e
    return s * np.array([hx, hy, hz]), ff


ice_m, _ice = glass_mat("Ice", (0.82, 0.93, 1.0), ior=1.31, rough=0.12)
_int = _ice.id_data
_tc = node(_int, "ShaderNodeTexCoord")
_nz = node(_int, "ShaderNodeTexNoise", Scale=4.0, Detail=6.0)
_int.links.new(_tc.outputs["Object"], _nz.inputs["Vector"])
_bp = node(_int, "ShaderNodeBump", Strength=0.35, Distance=0.05)
_int.links.new(_nz.outputs["Fac"], _bp.inputs["Height"])
_int.links.new(_bp.outputs["Normal"], _ice.inputs["Normal"])
_iv, _if = superbox(0.85, 0.62, 0.6)
ICE = puts(obj_from("IceBlock", _iv, _if, ice_m), "froz")
water_m, _ = principled("Water", (0.42, 0.44, 0.47), rough=0.12, coat=0.6)
PUDDLE = puts(sph("Puddle", (0, 0, 0), 1.0, water_m, 32, 8), "froz")
CHIPS = Burst("IceChips", 90, ("froz",), 51, ice_m, kind="tet", size=(0.03, 0.08))
_gc = np.random.default_rng(52)
_th = _gc.uniform(0, 2 * math.pi, 90)
CHIPS.emit(FO + np.array([0, 0, TOPZ + 0.05]) + np.stack([np.cos(_th) * 0.9, np.sin(_th) * 0.65, np.zeros(90)], -1),
           np.stack([np.cos(_th), np.sin(_th), np.zeros(90)], -1) * _gc.uniform(2, 7, 90)[:, None]
           + np.array([0, 0, 1.0]) * _gc.uniform(2, 6, 90)[:, None], _gc.uniform(0, 0.03, 90), 0.5, 22.0)
light("FKey", "AREA", FO + (-6, -7, 8), FO + (0, 0, TOPZ), 5000, 7, (1.0, 0.96, 0.9), "froz")
light("FRim", "AREA", FO + (5, 6, 6), FO + (0, 0, TOPZ), 5000, 6, (0.6, 0.8, 1.0), "froz")
light("FFill", "AREA", FO + (6, -6, 3), FO + (0, 0, TOPZ), 1200, 6, (1.0, 0.9, 0.8), "froz")


def pose_froz(td, tm):
    """td: time since the block lands on the table; tm: time since melting starts."""
    if td is None:
        td = -9.0
    if tm is None:
        tm = -9.0
    if td < 0:
        z0 = TOPZ + 0.6 + (min(2.4, 0.5 * 20 * (td + 0.49) ** 2) if td > -0.49 else 2.4)
        z0 = TOPZ + 0.6 + 2.4 - min(2.4, 0.5 * 20 * (td + 0.49) ** 2) if td > -0.49 else TOPZ + 0.6 + 2.4
    else:
        z0 = TOPZ + 0.6 + 0.08 * math.exp(-td / 0.1) * abs(math.sin(td * 25))
    m = smooth01(tm / 1.3)
    s = 1.0 - 0.97 * m
    ICE.hide_render = bool(s < 0.04)
    ICE.scale = (max(s, 0.04) ** 0.9, max(s, 0.04) ** 0.9, max(s, 0.04))
    ICE.location = tuple(FO + np.array([0, 0, z0 - 0.6 + 0.6 * max(s, 0.04)]))
    CHF.location = tuple(FO + np.array([0, 0, z0 - 0.6 + 0.4 + 0.2 * max(s, 0.0) * (1 - m)]))
    CHF.rotation_euler = (0.0, 0.0, math.radians(-25))
    FROST.default_value = 1.0 - m
    PUDDLE.hide_render = True
    PUDDLE.scale = (0.2 + 1.0 * m, 0.18 + 0.75 * m, 0.006)
    PUDDLE.location = tuple(FO + np.array([0, 0, TOPZ + 0.002]))
    CHIPS.pose(td)
    CHIPS.dyn.o.hide_render = bool(td < 0 or td > 1.2)


# ================================================================= set "sky": an airliner (static at SKY_O; the world moves)
SK = G.SKY_O
FL, FR, FLN = 120.0, 6.5, 11.0


def fus_r(s):
    s = np.asarray(s, float)
    u = np.clip(s / FLN, 0, 1)
    r = FR * np.sqrt(np.clip(1 - (1 - u) ** 2, 0, 1)) ** 0.85
    t = np.clip((s - 88.0) / (FL - 88.0), 0, 1)
    return r * (1 - 0.8 * t ** 1.4)


def fus_zc(s):
    s = np.asarray(s, float)
    u = np.clip(s / FLN, 0, 1)
    t = np.clip((s - 88.0) / (FL - 88.0), 0, 1)
    return -1.8 * (1 - u) ** 2 + 4.6 * t ** 1.6


def fus_surf(s, phi):
    s, phi = np.broadcast_arrays(np.asarray(s, float), np.asarray(phi, float))
    r = fus_r(s)
    return np.stack([r * np.sin(phi), s, fus_zc(s) + r * np.cos(phi)], -1)


def build_plane():
    ss = np.concatenate([np.linspace(0, FLN, 40), np.linspace(FLN, 88, 10)[1:], np.linspace(88, FL, 16)[1:]])
    nph = 48
    ph = np.linspace(-math.pi, math.pi, nph, endpoint=False)
    S_, P_ = np.meshgrid(ss, ph, indexing="ij")
    v = fus_surf(S_, P_).reshape(-1, 3)
    f = [[i * nph + k, (i + 1) * nph + k, (i + 1) * nph + (k + 1) % nph, i * nph + (k + 1) % nph]
         for i in range(len(ss) - 1) for k in range(nph)]
    c = len(v)
    v = np.vstack([v, [[0, FL + 0.3, fus_zc(FL)]]])
    f += [[(len(ss) - 1) * nph + k, (len(ss) - 1) * nph + (k + 1) % nph, c] for k in range(nph)]
    parts = [puts(obj_from("Fuselage", v + SK, f, paint_m), "sky")]

    def wing(name, root, span, sweep, c0, c1, t0, t1, dih, mat, vertical=False):
        sec = np.array([(0.0, 0.0), (0.12, 0.6), (0.45, 0.5), (1.0, 0.0), (0.45, -0.35), (0.12, -0.4)])
        vv, ff = [], []
        for side in ((1,) if vertical else (-1, 1)):
            o = len(vv)
            for j, (cc, tt, e) in enumerate(((c0, t0, 0.0), (c1, t1, 1.0))):
                for (u, w) in sec:
                    if vertical:
                        p = (w * tt, root[1] + e * span * math.tan(sweep) + u * cc, root[2] + e * span)
                    else:
                        p = (side * (root[0] + e * span), root[1] + e * span * math.tan(sweep) + u * cc,
                             root[2] + e * span * math.tan(dih) + w * tt)
                    vv.append(p)
            m = len(sec)
            for k in range(m):
                k1 = (k + 1) % m
                q = [o + k, o + k1, o + m + k1, o + m + k]
                ff.append(q if side > 0 else q[::-1])
            ff.append([o + k for k in range(m)][::-1] if side > 0 else [o + k for k in range(m)])
            ff.append([o + m + k for k in range(m)] if side > 0 else [o + m + k for k in range(m)][::-1])
        return puts(obj_from(name, np.array(vv) + SK, ff, mat, smooth=False), "sky")

    parts.append(wing("Wings", (4.0, 44.0, -3.8), 54.0, math.radians(27), 22.0, 6.0, 2.2, 0.5, math.radians(5), paint_m))
    parts.append(wing("Stab", (1.5, 104.0, 4.2), 19.0, math.radians(30), 11.0, 4.0, 0.9, 0.3, math.radians(4), paint_m))
    parts.append(wing("Fin", (0.0, 96.0, 6.0), 22.0, math.radians(38), 18.0, 6.5, 1.1, 0.4, 0, stripe_m,
                      vertical=True))
    # cabin windows + cockpit windows (dark)
    bw_ = Builder()
    for side in (-1, 1):
        for k in range(30):
            s = 20.0 + k * 2.3
            ph = side * math.radians(62)
            p = fus_surf(s, ph)
            bw_.sphere(tuple(p), (0.32, 0.45, 0.45), (0, 0, 0))
        for (s, ph) in ((7.4, math.radians(-26)), (7.4, math.radians(26)), (8.8, math.radians(-58)),
                        (8.8, math.radians(58))):
            p = fus_surf(s, ph)
            bw_.sphere(tuple(p), (1.2, 0.8, 0.55), (0, 0, 0))
    parts.append(puts(bw_.build("CabinWin", win_m), "sky"))
    for o in parts[-1:]:
        o.location = tuple(SK)
    return parts


PLANE = build_plane()
ENG_X, ENG_Y, ENG_Z = 18.5, 36.0, -8.6
nac_m, _ = principled("Nacelle", (0.7, 0.72, 0.75), rough=0.3, coat=0.5)
fan_m, _fan = principled("Fan", (0.25, 0.27, 0.3), rough=0.25)
_fan.inputs["Metallic"].default_value = 0.9
FANS, ENG_IN, ENG_OUT = [], [], []
for side in (-1, 1):
    o = SK + np.array([side * ENG_X, ENG_Y, ENG_Z])
    puts(ylathe(f"Nacelle{side}", [(3.0, 0.0), (3.45, 0.4), (3.55, 2.0), (3.3, 9.0), (2.4, 13.5), (1.6, 13.5),
                                     (2.6, 9.0), (3.0, 2.0), (2.95, 0.5)], nac_m, o), "sky")
    puts(ylathe(f"Intake{side}", [(2.94, 0.45), (2.9, 1.6)], bore_m, o), "sky")
    bf = Builder()
    for k in range(22):
        a = 2 * math.pi * k / 22
        bf.add(*box_vf(-0.18, 0.18, -0.06, 0.06, 0.55, 2.85),
               Matrix.Rotation(a, 4, "Y") @ Matrix.Rotation(0.45, 4, "Z"))
    bf.add(*cone_vf(0.7, 1.1), Matrix.Rotation(math.pi / 2, 4, "X"))
    fo = puts(bf.build(f"Fan{side}", fan_m, smooth=False), "sky")
    fo.location = tuple(o + np.array([0, 1.4, 0]))
    FANS.append(fo)
    ENG_IN.append(o + np.array([0, 0.0, 0]))
    ENG_OUT.append(o + np.array([0, 13.5, 0]))
    puts(box(f"Pylon{side}", tuple(o + np.array([-0.3, 4.0, 2.6])), tuple(o + np.array([0.3, 12.0, 5.4])), nac_m),
         "sky")

sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy, sun_d.angle, sun_d.color = 4.5, math.radians(1.5), (1.0, 0.96, 0.9)
SUN = puts(bpy.data.objects.new("Sun", sun_d), "sky")
SUN.rotation_euler = (math.radians(50), 0, math.radians(-35))
col.objects.link(SUN)

# birds: one Dyn per flock; body (small sphere) + two 2-segment wings
BV, BF = sphere_vf(8, 6)


def bird_mesh(n):
    nb = len(BV)
    f = []
    for k in range(n):
        o = k * (nb + 12)
        f += [[o + i for i in fc] for fc in BF]
        w = o + nb
        for s in (0, 6):
            f += [[w + s + 0, w + s + 1, w + s + 3, w + s + 2], [w + s + 2, w + s + 3, w + s + 5, w + s + 4]]
    return f


class Flock:
    def __init__(self, name, n, mat, size, seed):
        self.n, self.size = n, size
        self.g = np.random.default_rng(seed)
        self.ph = self.g.uniform(0, 6.28, n)
        self.dyn = Dyn(name, np.zeros((n * (len(BV) + 12), 3)), bird_mesh(n), mat, sets=("sky",), smooth=False)

    def pose(self, pos, heading, t, alive, rate=9.0):
        out = []
        s = self.size
        for k in range(self.n):
            hd = heading[k] / np.linalg.norm(heading[k])
            side = np.cross(hd, [0, 0, 1.0])
            side /= np.linalg.norm(side)
            up = np.cross(side, hd)
            sc = s * (1.0 if alive[k] else 0.0)
            body = BV * np.array([0.22, 0.6, 0.2])
            M = np.stack([side, hd, up], 1)
            bv = body @ M.T * sc + pos[k]
            a = 0.55 * math.sin(rate * t + self.ph[k])
            wv = []
            for sg in (-1, 1):
                c = math.cos(a)
                sn = math.sin(a)
                root = np.array([0.0, 0.0, 0.0])
                mid = np.array([sg * 0.9 * c, 0.0, 0.9 * sn])
                tip = mid + np.array([sg * 0.9 * math.cos(a * 1.6), -0.15, 0.9 * math.sin(a * 1.6)])
                for p, chord in ((root, 0.45), (mid, 0.35), (tip, 0.12)):
                    wv.append(p + np.array([0, chord * 0.5, 0]))
                    wv.append(p + np.array([0, -chord * 0.5, 0]))
            wv = np.array(wv) @ M.T * sc + pos[k]
            out.append(np.vstack([bv, wv]))
        self.dyn.set(np.vstack(out))


gull_m, _ = principled("Gull", (0.82, 0.83, 0.85), rough=0.6)
goose_m, _ = principled("Goose", (0.12, 0.1, 0.08), rough=0.7)
GULLS = Flock("Gulls", 40, gull_m, 2.6, 61)
GEESE = Flock("Geese", 14, goose_m, 4.2, 62)
FS = Burst("FeathersSky", 330, ("sky",), 63, gull_m, size=(0.7, 1.4))
FG = [Burst(f"FeathersEng{k}", 160, ("sky",), 64 + k, goose_m, size=(0.6, 1.2)) for k in range(2)]
flame_m = emit_mat("Flame", (1.0, 0.45, 0.1), 30.0)[0]
smoke_m, _ = principled("Smoke", (0.05, 0.05, 0.055), rough=0.9)
FLAMES = [puts(sph(f"Flame{k}", (0, 0, 0), 1.0, flame_m, 16, 8), "sky") for k in range(2)]
SMOKE = [Burst(f"Smoke{k}", 700, ("sky",), 70 + k, smoke_m, kind="tet", size=(1.2, 3.2)) for k in range(2)]

# ground: New York (S3) or a cloud deck (S2); both slide past along +Y
GZ = SK[2] - 2800.0
bld_m, _ = principled("Buildings", (0.42, 0.42, 0.44), rough=0.6)
river_m, _ = principled("River", (0.04, 0.09, 0.13), rough=0.08, coat=0.8)
land_m, _ = principled("Land", (0.2, 0.23, 0.2), rough=0.9)
_bb = Builder()
_gb = np.random.default_rng(81)
for k in range(2600):
    x = _gb.uniform(-9000, 9000)
    y = _gb.uniform(-6000, 20000)
    if -1700 < x < -500:                      # the Hudson
        continue
    w = _gb.uniform(60, 180)
    h = _gb.uniform(40, 220) * (2.6 if (abs(x - 1500) < 2500 and abs(y - 5000) < 3000) else 1.0)
    _bb.add(*box_vf(-w / 2, w / 2, -w / 2, w / 2, 0, h), Matrix.Translation((x, y, 0)))
CITY = puts(_bb.build("City", bld_m, smooth=False), "sky")
LAND = puts(obj_from("Land", [(-20000, -20000, 0), (-1700, -20000, 0), (-1700, 40000, 0), (-20000, 40000, 0),
                              (-500, -20000, 0), (20000, -20000, 0), (20000, 40000, 0), (-500, 40000, 0)],
                     [[0, 1, 2, 3], [4, 5, 6, 7]], land_m, smooth=False), "sky")
RIVER = puts(obj_from("River", [(-1700, -20000, -2), (-500, -20000, -2), (-500, 40000, -2), (-1700, 40000, -2)],
                      [[0, 1, 2, 3]], river_m, smooth=False), "sky")


def cloud_mat():
    m, nt, out = new_mat("CloudDeck")
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.9)
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=0.0009, Detail=6.0, Roughness=0.6)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    r = ramp(nt, [(0.42, (0.42, 0.55, 0.72)), (0.55, (0.95, 0.96, 0.98))])
    nt.links.new(nz.outputs["Fac"], r.inputs[0])
    nt.links.new(r.outputs[0], p.inputs["Base Color"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


CLOUDS = puts(obj_from("Clouds", [(-60000, -60000, 0), (60000, -60000, 0), (60000, 60000, 0), (-60000, 60000, 0)],
                       [[0, 1, 2, 3]], cloud_mat(), smooth=False), "sky")


VR, VG = 50.0, 220.0        # birds' speed relative to the plane; ground speed (both "slow motion")
_gs = np.random.default_rng(91)


def flock_targets(n, special, hits):
    tg = np.zeros((n, 3))
    for k in range(n):
        while True:
            p = np.array([_gs.uniform(-26, 26), _gs.uniform(-6, 30), _gs.uniform(-12, 18)])
            if not (abs(p[0]) < 14 and -16 < p[2] < 12):
                break
        tg[k] = p
    tk = _gs.uniform(-1.0, 6.0, n)
    for j, (p, t_) in enumerate(zip(special, hits)):
        tg[j], tk[j] = p, t_
    return tg, tk


NOSE_HIT = [np.array([-1.2, 0.6, -0.4]), np.array([1.5, 1.2, 1.2]), np.array([-0.4, 2.0, 2.6])]
GULL_T, GULL_TK = flock_targets(GULLS.n, NOSE_HIT, T.SKY_HITS)
ENG_HIT = [np.array([-ENG_X - 0.6, ENG_Y - 0.5, ENG_Z + 0.5]), np.array([-ENG_X + 0.8, ENG_Y - 0.5, ENG_Z - 0.6]),
           np.array([ENG_X + 0.5, ENG_Y - 0.5, ENG_Z + 0.4]), np.array([ENG_X - 0.7, ENG_Y - 0.5, ENG_Z - 0.5])]
EH = T.ENG_HITS
GOOSE_T, GOOSE_TK = flock_targets(GEESE.n, ENG_HIT, [EH[0] - 0.12, EH[0], EH[1] - 0.12, EH[1]])
GULL_HD = np.tile([1.0, -0.4, 0.05], (GULLS.n, 1)) + _gs.normal(0, 0.2, (GULLS.n, 3))
GOOSE_HD = np.tile([-1.0, -0.5, 0.0], (GEESE.n, 1)) + _gs.normal(0, 0.1, (GEESE.n, 3))
_fsg = np.random.default_rng(92)
_parts = np.array_split(np.arange(FS.n), 3)
_p0, _v0, _t0 = np.zeros((FS.n, 3)), np.zeros((FS.n, 3)), np.zeros(FS.n)
for j, idx in enumerate(_parts):
    sub = Burst.__new__(Burst)
    sub.n = len(idx)
    spray(sub, SK + NOSE_HIT[j], np.array([0, -1.0, 0.3]), _fsg, n_out=(3, 12), n_rad=(5, 16), t_span=0.1,
          k=(0.8, 1.6), grav=3.0, along=np.array([0, VR * 0.35, 0]), r0=0.6)
    _p0[idx], _v0[idx], _t0[idx] = sub.p0, sub.v0, sub.t0 + T.SKY_HITS[j]
FS.emit(_p0, _v0, _t0, np.full(FS.n, 0.8), 3.0)
for side in range(2):
    spray(FG[side], ENG_IN[side], np.array([0, -1.0, 0]), _fsg, n_out=(2, 10), n_rad=(4, 14), t_span=0.15,
          k=(0.5, 1.2), grav=4.0, along=np.array([0, VR * 0.9, 0]), r0=1.5)
    FG[side].t0 = FG[side].t0 + EH[side]
    ns = SMOKE[side].n
    SMOKE[side].emit(ENG_OUT[side] + _fsg.normal(0, 0.6, (ns, 3)),
                     np.array([0, VR * 0.95, 0]) + _fsg.normal(0, 3.0, (ns, 3)),
                     EH[side] + 0.1 + np.sort(_fsg.uniform(0, 4.0, ns)), np.full(ns, 0.15), -1.0)


def pose_sky(mode, tp):
    WSKY.default_value = 1.0
    gulls = mode == "gulls"
    GULLS.dyn.o.hide_render = bool(not gulls)
    GEESE.dyn.o.hide_render = bool(gulls)
    FS.dyn.o.hide_render = bool(not gulls)
    for o in (CITY, LAND, RIVER):
        o.hide_render = bool(gulls)
        o.location = (0, -9000 + VG * tp, GZ)
    RIVER.location = (300, -9000 + VG * tp, GZ)
    LAND.location = (300, -9000 + VG * tp, GZ)
    CITY.location = (300, -9000 + VG * tp, GZ)
    CLOUDS.hide_render = bool(not gulls)
    CLOUDS.location = (0, VG * tp, SK[2] - 1500)
    if gulls:
        pos = SK + GULL_T + np.array([0, 1.0, 0]) * (VR * (tp - GULL_TK))[:, None] \
            + GULL_HD * 5.0 * (tp - GULL_TK)[:, None]
        alive = [not (k < 3 and tp >= GULL_TK[k]) for k in range(GULLS.n)]
        GULLS.pose(pos, GULL_HD, tp, alive, rate=7.0)
        FS.pose(tp)
        for b in FG + SMOKE:
            b.dyn.o.hide_render = True
        for fl in FLAMES:
            fl.hide_render = True
        ang = [9.0 * tp, 9.0 * tp + 1.0]
    else:
        pos = SK + GOOSE_T + np.array([0, 1.0, 0]) * (VR * (tp - GOOSE_TK))[:, None] \
            + GOOSE_HD * 6.0 * (tp - GOOSE_TK)[:, None]
        alive = [not (k < 4 and tp >= GOOSE_TK[k]) for k in range(GEESE.n)]
        GEESE.pose(pos, GOOSE_HD, tp, alive, rate=5.0)
        ang = []
        for side in range(2):
            th = EH[side]
            FG[side].dyn.o.hide_render = bool(tp < th)
            FG[side].pose(tp)
            SMOKE[side].dyn.o.hide_render = bool(tp < th)
            SMOKE[side].pose(tp)
            a = tp - th
            fl = FLAMES[side]
            fl.hide_render = bool(a < 0)
            if a >= 0:
                flick = 1.0 + 0.25 * math.sin(a * 37 + side) + 0.15 * math.sin(a * 61)
                if a < 0.25:
                    fl.location = tuple(ENG_IN[side] + np.array([0, 0.8, 0]))
                    r = 3.6 * (1 - a / 0.25) + 1.4 * (a / 0.25)
                    fl.scale = (r, r * 0.6, r)
                else:
                    fl.location = tuple(ENG_OUT[side] + np.array([0, 2.0, 0]))
                    r = (1.8 * math.exp(-(a - 0.25) / 1.5) + 0.6) * flick
                    fl.scale = (r, r * 2.2, r)
            if a < 0:
                ang.append(9.0 * tp)
            else:
                ang.append(9.0 * th + 9.0 * 0.6 * (1 - math.exp(-a / 0.6)) + 0.4 * a)
    for side in range(2):
        FANS[side].rotation_euler = (0, ang[side] * (1 if side else -1), 0)


def pose(t):
    i = T.shot_index(t)
    s = T.SET_OF[i]
    for k, objs in SETS.items():
        for o in objs:
            o.hide_render = True
    for o in SETS[s]:
        o.hide_render = False
    WSKY.default_value = 0.0
    if s == "lab":
        te = T.imp_clock(t)
        pose_lab_impact(te)
        tf = T.lab_fire_clock(t)
        PUFF.dyn.o.hide_render = bool(tf is None or tf < 0 or tf > 1.5)
        if tf is not None:
            PUFF.pose(tf)
    elif s == "old":
        pose_old(T.old_clock(t))
    elif s == "scale":
        pose_scale(T.scale_clock(t))
    elif s == "gun":
        pose_gun(*T.gun_clocks(t))
    elif s == "froz":
        pose_froz(*T.froz_clocks(t))
    elif s == "sky":
        pose_sky(*T.sky_clock(t))

# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.clip_start = 0.01
cam_d.clip_end = 20000
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
c.adaptive_threshold = 0.06
c.use_denoising = True
c.denoising_quality = "BALANCED"
c.denoising_prefilter = "ACCURATE"
c.max_bounces = 6
c.diffuse_bounces = 1
c.glossy_bounces = 2
c.transparent_max_bounces = 24
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

SPP = 12
if os.environ.get("PC_EXP"):
    exec(os.environ["PC_EXP"])

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
