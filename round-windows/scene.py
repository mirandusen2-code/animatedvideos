"""Blender scene for "Why Airplane Windows Are Round" (Cycles, posed per frame). 1 unit = 1 ft.

Sets (only the active one is rendered):
  rip    close-up of a 1950s fuselage: the skin tears open from the corner of a square window (frame 0 / loop)
  cut    a cabin cross-section that swells like a balloon when the cabin is pumped up
  map    a skin panel coloured by stress; "push" lines flow around the window and pile up at its corners
  comet  a 1950s jetliner over the sea that breaks apart
  tank   the same airframe in a water tank, pressure-cycled until it splits at a window corner

Usage: python3 scene.py <out_dir> [--frames a,b,c | --range a b] [--res 1080x1920] [--quality 1.0]
"""
import bpy  # noqa: I001  (bpy must be imported before bmesh)
import bmesh  # noqa: F401
import math
import os
import random  # noqa: F401
import sys

import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector  # noqa: F401

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





SETS = {k: [] for k in ("rip", "cut", "map", "comet", "tank")}

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



def ylathe(name, prof, mat, origin, seg=48):
    """lathe around Z, then turned so Z -> +Y, placed at origin."""
    o = lathe(name, prof, mat, seg)
    o.rotation_euler = (-math.pi / 2, 0, 0)
    o.location = tuple(origin)
    return o


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



# ================================================================= extra helpers
def multi_mat(o, mats, idx):
    """Give an object several materials and a per-face material index."""
    o.data.materials.clear()
    for m in mats:
        o.data.materials.append(m)
    o.data.polygons.foreach_set("material_index", np.asarray(idx, np.int32))
    o.data.update()
    return o


def grid_faces(nu, nv, wrap_v=False):
    f = []
    for i in range(nu - 1):
        for k in range(nv if wrap_v else nv - 1):
            k1 = (k + 1) % nv
            f.append([i * nv + k, (i + 1) * nv + k, (i + 1) * nv + k1, i * nv + k1])
    return f


def slab(n, half_u, half_v, th):
    """n identical thin boxes in local coords (8 verts each), faces list."""
    u, v, w = half_u, half_v, th / 2
    c = np.array([(-u, -v, -w), (u, -v, -w), (u, v, -w), (-u, v, -w), (-u, -v, w), (u, -v, w), (u, v, w), (-u, v, w)])
    ff = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return c, [[k * 8 + a for a in q] for k in range(n) for q in ff]


def flake_burst(name, n, sets, seed, mat, size=(0.05, 0.16)):
    """A Burst whose pieces are flat irregular flakes (skin fragments, paper)."""
    b = Burst(name, n, sets, seed, mat, kind="tet", size=size)
    g = np.random.default_rng(seed + 1)
    L = np.zeros((n, 4, 3))
    for k in range(n):
        s = g.uniform(*size)
        a = np.sort(g.uniform(0, 2 * math.pi, 4))
        rr = s * g.uniform(0.5, 1.0, 4)
        L[k, :, 0] = rr * np.cos(a)
        L[k, :, 1] = rr * np.sin(a)
        L[k, :, 2] = g.uniform(-0.15, 0.15, 4) * s
    b.L = L
    return b


def se_ring(a, b, n, m, scale_out):
    """Superellipse window: inner boundary (m,2) and outer frame boundary."""
    p, _k = G.se_boundary(a, b, n, m)
    q, _k = G.se_boundary(a * scale_out[0], b * scale_out[1], max(2.0, n * 0.8), m)
    return p, q


def disk_faces(m, c0, ring0):
    return [[ring0 + k, ring0 + (k + 1) % m, c0] for k in range(m)]


def ring_faces(m, r0, r1):
    return [[r0 + k, r1 + k, r1 + (k + 1) % m, r0 + (k + 1) % m] for k in range(m)]


# ================================================================= world: blue sky (rip / comet) or dark studio
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
_wsky = ramp(wnt, [(0.0, (0.25, 0.36, 0.52)), (0.5, (0.36, 0.5, 0.72)), (0.52, (0.16, 0.32, 0.64)),
                   (0.75, (0.06, 0.18, 0.48)), (1.0, (0.02, 0.07, 0.26))])
wnt.links.new(_wsep.outputs["Z"], _wsky.inputs[0])
_wmix = wnt.nodes.new("ShaderNodeMixRGB")
_wmix.inputs[1].default_value = (0.008, 0.010, 0.016, 1)
wnt.links.new(_wsky.outputs[0], _wmix.inputs[2])
WSKY = _wmix.inputs[0]
_wbg = wnt.nodes.new("ShaderNodeBackground")
wnt.links.new(_wmix.outputs[0], _wbg.inputs["Color"])
WSTR = _wbg.inputs["Strength"]
wnt.links.new(_wbg.outputs[0], wnt.nodes["World Output"].inputs[0])

# ================================================================= materials
white_m, _ = principled("WhitePaint", (0.86, 0.87, 0.88), rough=0.3, coat=0.5)
blue_m, _ = principled("Cheatline", (0.04, 0.16, 0.48), rough=0.3, coat=0.5)
alu_m, _alu = principled("Aluminium", (0.78, 0.79, 0.81), rough=0.28)
_alu.inputs["Metallic"].default_value = 1.0
primer_m, _ = principled("Primer", (0.32, 0.36, 0.28), rough=0.7)
glass_dark_m, _gl = principled("WinGlass", (0.03, 0.04, 0.055), rough=0.5, coat=0.0)
_gl.inputs["Specular IOR Level"].default_value = 0.08
frame_m, _ = principled("WinFrame", (0.55, 0.56, 0.58), rough=0.35)
interior_m, _ = principled("Interior", (0.13, 0.13, 0.12), rough=0.85)
seat_m, _ = principled("Seat", (0.08, 0.16, 0.42), rough=0.7)
mist_m, _ = principled("Mist", (0.95, 0.96, 0.97), rough=0.9)
insul_m, _ = principled("Insulation", (0.9, 0.78, 0.38), rough=0.85)
smoke_m, _ = principled("Smoke", (0.22, 0.22, 0.23), rough=0.95)
dark_m, _ = principled("TornEdge", (0.05, 0.05, 0.05), rough=0.8)


def zone_mats(s_arc):
    """Material index for a skin face from its arc position (0 white top, 1 blue cheatline, 2 bare metal)."""
    s_arc = np.asarray(s_arc)
    return np.where(s_arc > -1.15, 0, np.where(s_arc > -1.75, 1, 2))


SKIN_MATS = [white_m, blue_m, alu_m]

# ================================================================= set "rip": fuselage close-up, W0 tears open
R = G.RIP_R
TILE = 0.38
TY = (-2.28, 2.28)             # tile region along the fuselage (multiples of TILE around 0)
TS = (-3.04, 4.56)             # tile region around the fuselage (arc length)
_ys = np.concatenate([np.arange(-60.0, TY[0], 1.9), np.arange(TY[0], TY[1] + 1e-6, TILE),
                      np.arange(TY[1] + 1.9, 40.0, 1.9)])
_ys = np.unique(np.round(np.concatenate([_ys, [TY[0], TY[1]]]), 4))
_ss = np.arange(-math.pi * R, math.pi * R, TILE)
_ss = _ss - _ss[np.argmin(np.abs(_ss - TS[0]))] + TS[0]          # align a grid line with the tile edge
_ss = np.sort(np.mod(_ss + math.pi * R, 2 * math.pi * R) - math.pi * R)
_Y, _S = np.meshgrid(_ys, _ss, indexing="ij")
_v = G.rip_surf(_Y, _S).reshape(-1, 3)
_f, _idx = [], []
nsv = len(_ss)
for i in range(len(_ys) - 1):
    for k in range(nsv):
        k1 = (k + 1) % nsv
        yc = 0.5 * (_ys[i] + _ys[i + 1])
        sc = _ss[k] + (TILE / 2 if k1 else 0)
        if TY[0] < yc < TY[1] and TS[0] < sc < TS[1]:
            continue
        _f.append([i * nsv + k, (i + 1) * nsv + k, (i + 1) * nsv + k1, i * nsv + k1])
        _idx.append(int(zone_mats(sc)))
RIPSKIN = puts(obj_from("RipSkin", _v + G.RIP_O, _f, white_m), "rip")
multi_mat(RIPSKIN, SKIN_MATS, _idx)
# cabin interior behind the skin (seen through the hole) + seat backs
_Yi, _Si = np.meshgrid(np.linspace(-20, 20, 30), np.linspace(-math.pi * (R - 0.3), math.pi * (R - 0.3), 64),
                       indexing="ij")
_vi = G.rip_surf(_Yi, _Si, R - 0.3).reshape(-1, 3)
puts(obj_from("RipInterior", _vi + G.RIP_O, grid_faces(30, 64, True), interior_m), "rip")
_bs = Builder()
for y in np.arange(-6.0, 7.0, 2.6):
    for x in (-3.9, -2.5):
        _bs.add(*box_vf(x - 0.55, x + 0.55, y - 0.15, y + 0.15, -0.6, 1.8), Matrix.Identity(4))
puts(_bs.build("RipSeats", seat_m, smooth=False), "rip")

# skin tiles (fly off when the skin tears)
_ty = np.arange(TY[0] + TILE / 2, TY[1], TILE)
_tsa = np.arange(TS[0] + TILE / 2, TS[1], TILE)
TYc, TSc = [a.ravel() for a in np.meshgrid(_ty, _tsa, indexing="ij")]
NT = len(TYc)
_tl, TILE_F = slab(NT, TILE / 2 * 1.002, TILE / 2 * 1.002, 0.05)
TILES = Dyn("RipTiles", np.zeros((NT * 8, 3)), TILE_F, white_m, sets=("rip",), smooth=False)
multi_mat(TILES.o, SKIN_MATS, np.repeat(zone_mats(TSc), 6))
TILE_P = G.rip_surf(TYc, TSc, R - 0.025)
TILE_N = G.rip_normal(TSc)
_tang = np.stack([np.zeros(NT), np.ones(NT), np.zeros(NT)], -1)
TILE_B = np.stack([_tang, np.cross(TILE_N, _tang), TILE_N], 1)        # rows: local x (y), y (around), z (normal)
_tl_world = _tl                                                        # local verts (8,3)
_gt = np.random.default_rng(5)
cy, cs = G.W0_CORNER
TILE_D = np.hypot(TYc - cy, (TSc - cs) * 1.15) + _gt.uniform(0, 0.25, NT)
TILE_V = (TILE_N * _gt.uniform(5, 12, NT)[:, None] + np.array([0, -1.0, 0]) * _gt.uniform(4, 13, NT)[:, None]
          + _gt.normal(0, 1.5, (NT, 3)))
TILE_AX = rand_dirs(NT, _gt)
TILE_W = _gt.uniform(4, 14, NT) * _gt.choice([-1, 1], NT)
TEAR_V = 5.5                                                           # tear front speed (ft/s, slow motion)


def tile_pose(te):
    """te: slow-motion time since the tear (negative = intact)."""
    trel = TILE_D / TEAR_V
    a = np.maximum(0.0, te - trel) if te is not None else np.zeros(NT)
    # a tile within the hole region but close to the window may be skipped (window covers it)
    k = 1.6
    p = TILE_P + TILE_V * ((1 - np.exp(-k * a)) / k)[:, None]
    ang = TILE_W * a
    Rm = rodrigues(TILE_AX, ang)
    loc = np.einsum("kij,vj->kvi", TILE_B.transpose(0, 2, 1), _tl_world)
    v = np.einsum("kij,kvj->kvi", Rm, loc) + p[:, None, :]
    TILES.set(v + G.RIP_O)


# windows on the rip fuselage (superellipse glass + frame), morphable; W0 is its own object (flies off)
WM = 56


def rip_window_verts(yc, n, scale=1.0):
    p, q = se_ring(G.WIN_A * scale, G.WIN_B * scale, n, WM, (1.2, 1.17))
    gl = G.rip_surf(yc + p[:, 0], p[:, 1], R + 0.035)
    c = G.rip_surf(yc, 0.0, R + 0.05)[None]
    fi = G.rip_surf(yc + p[:, 0], p[:, 1], R + 0.06)
    fo = G.rip_surf(yc + q[:, 0], q[:, 1], R + 0.04)
    return np.vstack([c, gl, fi, fo])


def window_faces(nw):
    gf, ff = [], []
    per = 1 + 3 * WM
    for w in range(nw):
        o = w * per
        gf += [[o + 1 + k, o + 1 + (k + 1) % WM, o] for k in range(WM)]
        ff += [[o + 1 + WM + k, o + 1 + WM + (k + 1) % WM, o + 1 + 2 * WM + (k + 1) % WM, o + 1 + 2 * WM + k]
               for k in range(WM)]
    return gf, ff


OTHER_WY = [y for y in G.WIN_YS if abs(y) > 1e-6]
_gf, _ff = window_faces(len(OTHER_WY))
RWIN = Dyn("RipWindows", np.zeros((len(OTHER_WY) * (1 + 3 * WM), 3)), _gf + _ff, glass_dark_m, sets=("rip",),
           smooth=False)
multi_mat(RWIN.o, [glass_dark_m, frame_m], [0] * len(_gf) + [1] * len(_ff))
_gf0, _ff0 = window_faces(1)
W0 = Dyn("RipW0", np.zeros((1 + 3 * WM, 3)), _gf0 + _ff0, glass_dark_m, sets=("rip",), smooth=False)
multi_mat(W0.o, [glass_dark_m, frame_m], [0] * len(_gf0) + [1] * len(_ff0))
_g0 = np.random.default_rng(17)
W0_V = G.rip_normal(0.0) * 9.0 + np.array([0, -7.0, 5.5])   # flies at the camera and skims just over the lens
W0_AX = rand_dirs(1, _g0)[0]
W0_T = 0.06                 # the window frame pops out this long after the tear starts

# crack running from the W0 corner (before the tear, in the loop): a dark ribbon on the skin
_gcr = np.random.default_rng(23)
_cp = [np.array(G.W0_CORNER)]
_ca = math.radians(62)
for _ in range(36):
    _ca += _gcr.normal(0, 0.3)
    _ca = min(max(_ca, math.radians(30)), math.radians(100))
    _cp.append(_cp[-1] + 0.075 * np.array([math.cos(_ca), math.sin(_ca)]))
RIP_CRACK = np.array(_cp)                                        # (y, s) points, ~2.7 ft
RIP_CRACK_CUM = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(RIP_CRACK, axis=0), axis=1))])
RCR = Dyn("RipCrack", np.zeros((len(RIP_CRACK) * 2, 3)),
          [[2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2] for i in range(len(RIP_CRACK) - 1)], dark_m, sets=("rip",),
          smooth=False)


def crack_ribbon(L):
    """Ribbon vertices for crack length L (ft); collapsed beyond L."""
    pts = RIP_CRACK.copy()
    lim = np.minimum(RIP_CRACK_CUM, L)
    # move points beyond L onto the tip
    j = np.searchsorted(RIP_CRACK_CUM, L)
    j = min(max(j, 1), len(pts) - 1)
    tip = pts[j - 1] + (pts[j] - pts[j - 1]) * ((L - RIP_CRACK_CUM[j - 1]) /
                                                max(RIP_CRACK_CUM[j] - RIP_CRACK_CUM[j - 1], 1e-6))
    pts[RIP_CRACK_CUM > L] = tip
    d = np.gradient(pts, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], -1)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    w = 0.028 * np.clip(1 - lim / max(L, 1e-3), 0.15, 1.0)[:, None]
    a = G.rip_surf(pts[:, 0] + nrm[:, 0] * w[:, 0], pts[:, 1] + nrm[:, 1] * w[:, 0], R + 0.04)
    b = G.rip_surf(pts[:, 0] - nrm[:, 0] * w[:, 0], pts[:, 1] - nrm[:, 1] * w[:, 0], R + 0.04)
    return np.stack([a, b], 1).reshape(-1, 3)


# decompression: mist, insulation, paper flakes, blasting out of the hole toward the camera
MIST = Burst("RipMist", 1600, ("rip",), 31, mist_m, kind="tet", size=(0.02, 0.07))
INSUL = Burst("RipInsul", 260, ("rip",), 32, insul_m, kind="tet", size=(0.03, 0.09))
PAPER = flake_burst("RipPaper", 160, ("rip",), 33, white_m, size=(0.06, 0.16))


def emit_hole(b, n_speed, back_speed, t_span, seed, kk=(1.0, 2.6)):
    g = np.random.default_rng(seed)
    n = b.n
    # sources spread over the growing hole: start near the corner, later further out
    t0 = g.uniform(0.0, t_span, n) ** 1.3
    rad = np.minimum(TEAR_V * t0, 3.6) * np.sqrt(g.uniform(0, 1, n))
    ang = g.uniform(0, 2 * math.pi, n)
    yy = cy + rad * np.cos(ang) * 0.8
    ss = cs + rad * np.sin(ang)
    p0 = G.rip_surf(yy, ss, R - 0.2) + G.RIP_O
    nn = G.rip_normal(ss)
    v0 = (nn * g.uniform(*n_speed, n)[:, None] + np.array([0, -1.0, 0]) * g.uniform(*back_speed, n)[:, None]
          + g.normal(0, 2.0, (n, 3)))
    b.emit(p0, v0, t0, g.uniform(*kk, n), 0.0)


emit_hole(MIST, (6, 16), (3, 14), 1.4, 41)
emit_hole(INSUL, (5, 12), (4, 12), 1.0, 42)
emit_hole(PAPER, (4, 10), (5, 14), 1.2, 43)

# clouds far below (move backwards: the plane flies +Y)


def cloud_mat(name="CloudDeck", alpha=False):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.9)
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=0.0011, Detail=7.0, Roughness=0.62)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    r = ramp(nt, [(0.44, (0.5, 0.62, 0.78)), (0.58, (0.97, 0.98, 1.0))])
    nt.links.new(nz.outputs["Fac"], r.inputs[0])
    nt.links.new(r.outputs[0], p.inputs["Base Color"])
    if alpha:
        a = ramp(nt, [(0.47, (0, 0, 0)), (0.56, (1, 1, 1))])
        nt.links.new(nz.outputs["Fac"], a.inputs[0])
        tr = node(nt, "ShaderNodeBsdfTransparent")
        mx = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(a.outputs[0], mx.inputs[0])
        nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(p.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs[0])
    else:
        nt.links.new(p.outputs[0], out.inputs[0])
    return m


RIP_CLOUDS = puts(obj_from("RipClouds", [(-60000, -60000, 0), (60000, -60000, 0), (60000, 60000, 0),
                                         (-60000, 60000, 0)], [[0, 1, 2, 3]], cloud_mat(), smooth=False), "rip")
RIP_CLOUDS.location = (0, 0, -2600)
sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy, sun_d.angle, sun_d.color = 4.2, math.radians(1.5), (1.0, 0.96, 0.9)
SUN = bpy.data.objects.new("Sun", sun_d)
SUN.rotation_euler = (math.radians(48), 0, math.radians(-60))
col.objects.link(SUN)
puts(SUN, ("rip", "comet"))


def pose_rip(te, n_win, crack_len, tsky):
    """te: time since the tear (None/negative = intact); n_win: window shape; crack_len: crack before the tear."""
    tile_pose(te if te is not None and te > 0 else None)
    v = np.vstack([rip_window_verts(y, n_win) for y in OTHER_WY])
    RWIN.set(v + G.RIP_O)
    w0 = rip_window_verts(0.0, n_win)
    a = (te - W0_T) if te is not None else -1.0
    if a > 0:
        c0 = w0.mean(0)
        k = 1.4
        p = W0_V * (1 - math.exp(-k * a)) / k
        Rm = rodrigues(W0_AX[None], np.array([7.0 * a]))[0]
        w0 = (w0 - c0) @ Rm.T + c0 + p
    W0.set(w0 + G.RIP_O)
    on = te is None or te < 0.05
    RCR.o.hide_render = bool(not on or crack_len <= 0.01)
    if crack_len > 0.01:
        RCR.set(crack_ribbon(crack_len) + G.RIP_O)
    for b in (MIST, INSUL, PAPER):
        b.dyn.o.hide_render = bool(te is None or te <= 0)
        if te is not None and te > 0:
            b.pose(te)
    RIP_CLOUDS.location = (0, -260.0 * tsky, -2600)


# ================================================================= set "cut": cabin cross-section, pumped up like a balloon
CO = G.CUT_O
CUT_E = bpy.data.objects.new("CutRoot", None)
CUT_E.location = tuple(CO)
col.objects.link(CUT_E)
RC_OUT, RC_IN, CUT_L = 5.5, 5.12, 40.0
lining_m, _ = principled("Lining", (0.86, 0.83, 0.76), rough=0.6)
carpet_m, _ = principled("Carpet", (0.16, 0.2, 0.3), rough=0.9)
edge_m, _ = principled("CutEdge", (0.62, 0.64, 0.66), rough=0.4)


def cut_obj(o):
    o.parent = CUT_E
    return puts(o, "cut")


_ph = np.linspace(-math.pi, math.pi, 97)[:-1]
_yy = np.linspace(0, CUT_L, 24)
_Y2, _P2 = np.meshgrid(_yy, _ph, indexing="ij")
_so = np.stack([RC_OUT * np.sin(_P2), _Y2, RC_OUT * np.cos(_P2)], -1).reshape(-1, 3)
_si = np.stack([RC_IN * np.sin(_P2), _Y2, RC_IN * np.cos(_P2)], -1).reshape(-1, 3)
_fo = grid_faces(len(_yy), len(_ph), True)
_arc = (_P2[:-1, :] * RC_OUT).ravel()
cut_skin = cut_obj(obj_from("CutSkin", _so, _fo, white_m))
_ph_c = 0.5 * (_ph + np.roll(_ph, -1))
_ph_c[-1] = math.pi
_arc_c = np.tile(-np.abs(_ph_c) * RC_OUT + RC_OUT * math.radians(78), len(_yy) - 1)   # arc from window band
multi_mat(cut_skin, SKIN_MATS, zone_mats(_arc_c))
cut_obj(obj_from("CutLining", _si, [f[::-1] for f in _fo], lining_m))
_er = np.vstack([np.stack([RC_OUT * np.sin(_ph), np.zeros_like(_ph), RC_OUT * np.cos(_ph)], -1),
                 np.stack([RC_IN * np.sin(_ph), np.zeros_like(_ph), RC_IN * np.cos(_ph)], -1)])
_m = len(_ph)
cut_obj(obj_from("CutEdgeRing", _er, [[k, (k + 1) % _m, _m + (k + 1) % _m, _m + k] for k in range(_m)], edge_m,
                 smooth=False))
_fz = -1.6
_fw = math.sqrt(RC_IN ** 2 - _fz ** 2)
cut_obj(obj_from("CutFloor", [(-_fw, 0, _fz), (_fw, 0, _fz), (_fw, CUT_L, _fz), (-_fw, CUT_L, _fz)], [[0, 1, 2, 3]],
                 carpet_m, smooth=False))
# floor beam section (cut face) and the cargo hold below
cut_obj(obj_from("CutFloorEdge", [(-_fw, -0.01, _fz - 0.35), (_fw, -0.01, _fz - 0.35), (_fw, -0.01, _fz),
                                  (-_fw, -0.01, _fz)], [[0, 1, 2, 3]], edge_m, smooth=False))
_bs = Builder()
for y in np.arange(3.0, CUT_L - 2, 2.7):
    for x in (-3.4, -2.35, 2.35, 3.4):
        _bs.add(*box_vf(x - 0.48, x + 0.48, y - 0.45, y + 0.45, _fz, _fz + 1.45), Matrix.Identity(4))
        _bs.add(*box_vf(x - 0.48, x + 0.48, y + 0.3, y + 0.5, _fz + 1.0, _fz + 3.3), Matrix.Identity(4))
cut_obj(_bs.build("CutSeats", seat_m, smooth=False))
_bb = Builder()
for sx in (-1, 1):
    _bb.add(*box_vf(sx * 4.4 - 0.75, sx * 4.4 + 0.75, 0.6, CUT_L, 2.4, 3.6), Matrix.Identity(4))
cut_obj(_bb.build("CutBins", lining_m, smooth=False))
# cabin windows seen from inside (square, like the 1950s jet)
_bw = Builder()
for y in np.arange(2.0, CUT_L, 3.1):
    for sx in (-1, 1):
        ang = sx * math.radians(78)
        p = np.array([RC_IN * 0.985 * math.sin(ang), y, RC_IN * 0.985 * math.cos(ang)])
        _bw.add(*box_vf(-0.05, 0.05, -0.55, 0.55, -0.7, 0.7),
                Matrix.Translation(V(tuple(p))) @ Matrix.Rotation(-ang, 4, "Y") @ Matrix.Rotation(math.pi / 2, 4, "Y"))
cut_obj(_bw.build("CutWins", emit_mat("CutWinSky", (0.45, 0.62, 0.95), 1.6)[0], smooth=False))
light("CutCabin", "AREA", CO + np.array([0, 14, 3.6]), CO + np.array([0, 14, -2]), 900, 6, (1.0, 0.92, 0.8), "cut")
light("CutKey", "AREA", CO + np.array([-14, -16, 10]), CO + np.array([0, 4, 0]), 9000, 10, (1.0, 0.96, 0.9), "cut")
light("CutRim", "AREA", CO + np.array([12, -6, 8]), CO + np.array([0, 2, 0]), 5000, 8, (0.6, 0.75, 1.0), "cut")

# air molecules inside (cyan dots; more and faster as the cabin is pumped up)
air_m, _ = emit_mat("Air", (0.35, 0.8, 1.0), 4.0)
NA = 900
_ga = np.random.default_rng(61)
AIR_P = np.stack([_ga.uniform(-4.6, 4.6, NA), _ga.uniform(0.3, 14, NA), _ga.uniform(_fz + 0.2, 4.6, NA)], -1)
_keep = AIR_P[:, 0] ** 2 + AIR_P[:, 2] ** 2 < (RC_IN - 0.35) ** 2
AIR_P = AIR_P[_keep]
NA = len(AIR_P)
AIR_ORDER = _ga.uniform(0, 1, NA)
AIR_PH = _ga.uniform(0, 6.28, (NA, 3))
AIR_F = _ga.uniform(1.5, 4.0, (NA, 3))
_av, _af = sphere_vf(6, 4)
AIR = Dyn("AirDots", np.zeros((NA * len(_av), 3)), [[k * len(_av) + i for i in fc] for k in range(NA) for fc in _af],
          air_m, sets=("cut",), smooth=False)
AIR_V = _av * 0.055

# push arrows around the wall, pointing outward
arrow_m, _ = emit_mat("Arrow", (1.0, 0.45, 0.08), 3.0)
NARW = 16
_cv, _cf = cone_vf(0.3, 0.55, 12)
_bv, _bf = slab(1, 0.07, 0.07, 1.0)
ARW_V = len(_cv) + 8
ARW = Dyn("Arrows", np.zeros((NARW * 2 * ARW_V, 3)),
          [[k * ARW_V + i for i in fc] for k in range(NARW * 2) for fc in _cf]
          + [[k * ARW_V + len(_cv) + i for i in fc] for k in range(NARW * 2) for fc in _bf],
          arrow_m, sets=("cut",), smooth=False)


def pose_cut(p, ta):
    """p: cabin pressure 0..1 (scaled by the pump); ta: running time for the air jitter."""
    e = 0.075 * p
    CUT_E.scale = (1 + e, 1, 1 + e)
    n_on = AIR_ORDER < (0.25 + 0.75 * p)
    jig = (0.12 + 0.25 * p) * np.sin(AIR_F * ta * (1 + 1.5 * p) + AIR_PH)
    P = AIR_P * np.array([1 + e, 1, 1 + e]) + jig
    sc = np.where(n_on, 1.0, 0.0)[:, None, None]
    AIR.set((AIR_V[None] * sc + P[:, None, :]).reshape(-1, 3) + CO)
    verts = []
    L = 0.25 + 1.5 * p
    for ring, y in enumerate((0.25, 7.0)):
        for k in range(NARW):
            a = 2 * math.pi * (k + 0.5 * ring) / NARW
            d = np.array([math.sin(a), 0, math.cos(a)])
            r_tip = (RC_IN - 0.12) * (1 + e)
            if (r_tip * d[2]) < _fz + 0.2:          # no arrows under the floor: collapse them
                verts.append(np.zeros((ARW_V, 3)) + np.array([0, y, _fz - 1.0]))
                continue
            else:
                tip = r_tip * d + np.array([0, y, 0])
                Lk = L
            ba, bb = basis(d)
            Mx = np.array([ba, bb, d])
            cone = _cv @ Mx * min(1.0, Lk / 0.6 + 0.2)
            cone = cone + tip - d * 0.55 * min(1.0, Lk / 0.6 + 0.2)
            shaft_c = tip - d * (0.55 + Lk / 2)
            sh = (_bv * np.array([1, 1, Lk])) @ Mx + shaft_c
            verts.append(np.vstack([cone, sh]))
    ARW.set(np.vstack(verts) + CO)


# ================================================================= set "map": skin panel coloured by stress
MO = G.MAP_O


def heat_mat():
    m, nt, out = new_mat("Heat")
    a = attr_node(nt, "stress")
    mr = node(nt, "ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 1.0
    mr.inputs["From Max"].default_value = 3.7
    nt.links.new(a, mr.inputs["Value"])
    r = ramp(nt, [(0.0, (0.02, 0.06, 0.32)), (0.12, (0.03, 0.22, 0.62)), (0.3, (0.0, 0.62, 0.7)),
                  (0.45, (0.25, 0.8, 0.2)), (0.6, (0.98, 0.85, 0.08)), (0.75, (1.0, 0.42, 0.02)),
                  (0.9, (0.95, 0.06, 0.03)), (1.0, (1.0, 0.85, 0.8))])
    nt.links.new(mr.outputs[0], r.inputs[0])
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.45)
    p.inputs["Metallic"].default_value = 0.25
    nt.links.new(r.outputs[0], p.inputs["Base Color"])
    nt.links.new(r.outputs[0], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 0.55
    # rivet rows: subtle bump on a grid
    tc = node(nt, "ShaderNodeTexCoord")
    bt = node(nt, "ShaderNodeTexBrick")
    bt.inputs["Scale"].default_value = 1.0
    nt.links.new(tc.outputs["Object"], bt.inputs["Vector"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


_mx = np.concatenate([np.linspace(-G.MAP_W, -4.2, 26)[:-1], np.linspace(-4.2, 4.2, 211), np.linspace(4.2, G.MAP_W, 26)[1:]])
_mz = np.concatenate([np.linspace(-G.MAP_H, -4.6, 34)[:-1], np.linspace(-4.6, 4.6, 231), np.linspace(4.6, G.MAP_H, 34)[1:]])
MX, MZ = np.meshgrid(_mx, _mz, indexing="ij")
_mv = np.stack([MX, np.zeros_like(MX), MZ], -1).reshape(-1, 3)
PANEL = puts(obj_from("Panel", _mv + MO, grid_faces(len(_mx), len(_mz)), heat_mat(), smooth=True), "map")
attr_mesh(PANEL, ["stress"])
# the window on the panel: dark glass + light frame (morphs square <-> round)
MWM = 160
_mwf_g = [[1 + k, 1 + (k + 1) % MWM, 0] for k in range(MWM)]
_mwf_f = [[1 + MWM + k, 1 + MWM + (k + 1) % MWM, 1 + 2 * MWM + (k + 1) % MWM, 1 + 2 * MWM + k] for k in range(MWM)]
MWIN = Dyn("MapWin", np.zeros((1 + 3 * MWM, 3)), _mwf_g + _mwf_f, glass_dark_m, sets=("map",), smooth=False)
multi_mat(MWIN.o, [glass_dark_m, frame_m], [0] * MWM + [1] * MWM)


def map_window_verts(n):
    p, q = se_ring(G.MAP_A, G.MAP_B, n, MWM, (1.09, 1.07))
    c = np.array([[0, -0.03, 0]])
    g = np.stack([p[:, 0], np.full(MWM, -0.03), p[:, 1]], -1)
    fi = np.stack([p[:, 0], np.full(MWM, -0.05), p[:, 1]], -1)
    fo = np.stack([q[:, 0], np.full(MWM, -0.05), q[:, 1]], -1)
    return np.vstack([c, g, fi, fo])


# "push" particles: vertical lines of glowing dashes that flow around the window
push_m, _ = emit_mat("Push", (0.85, 0.95, 1.0), 5.0)
PX0 = np.concatenate([np.linspace(-8.4, -0.3, 20), np.linspace(0.3, 8.4, 20)])
NPL, NPP = len(PX0), 30
_dv, _df = slab(NPL * NPP, 0.026, 0.03, 0.3)          # long axis = local z
PUSH = Dyn("PushDash", np.zeros((NPL * NPP * 8, 3)), _df, push_m, sets=("map",), smooth=False)
PUSH_PH = np.random.default_rng(71).uniform(0, 1, (NPL, NPP)) * 0.25
X1 = 5.2


def smooth_w(n, z):
    """Window half width at heights z, blurred so the lines start bending a little before the window."""
    zz = np.linspace(-6, 6, 1201)
    w = G.se_halfwidth(G.MAP_A + 0.16, G.MAP_B + 0.12, n, zz)
    sig = 0.22
    kz = np.exp(-0.5 * (np.arange(-120, 121) * 0.01 / sig) ** 2)
    ws = np.convolve(w, kz / kz.sum(), mode="same")
    ws = np.maximum(ws, w * 0.97)
    return np.interp(z, zz, ws, left=0, right=0)


def deflect(x0, z, n):
    w = smooth_w(n, z)
    ax = np.abs(x0)
    inside = ax < X1
    xn = np.where(inside, w + ax * (X1 - w) / X1, ax)
    return np.sign(x0) * xn, np.where(inside, X1 / np.maximum(X1 - w, 0.2), 1.0)


def pose_push(tf, n, vis):
    span = 2 * G.MAP_H
    # each line: particles at evenly spaced phase, moving up; speed boosted where the lines are squeezed
    s0 = (np.arange(NPP)[None, :] / NPP + PUSH_PH + tf * 0.11) % 1.0
    z = -G.MAP_H + s0 * span
    x0 = np.repeat(PX0[:, None], NPP, 1)
    x, sq = deflect(x0, z, n)
    xa, _s = deflect(x0, z + 0.05, n)
    dxdz = (xa - x) / 0.05
    ang = np.arctan(dxdz)
    sc = vis * np.clip(1.0 + 0.5 * (sq - 1), 1, 2.2)                  # squeezed dashes are longer (faster)
    c, s_ = np.cos(ang), np.sin(ang)
    L = _dv[:8]
    lx = L[None, None, :, 0]
    lz = L[None, None, :, 2] * sc[..., None]
    ly = L[None, None, :, 1]
    vx = lx * c[..., None] + lz * s_[..., None] + x[..., None]
    vz = -lx * s_[..., None] + lz * c[..., None] + z[..., None]
    vy = ly - 0.09
    v = np.stack([vx, np.broadcast_to(vy, vx.shape), vz], -1).reshape(-1, 3)
    PUSH.set(v + MO)


# crack from the upper-right corner (a dark ribbon with a glowing tip)
crack_m, _ = principled("Crack", (0.01, 0.01, 0.01), rough=0.9)
CP, CCUM = G.crack_path()
MCR = Dyn("MapCrack", np.zeros((len(CP) * 2, 3)), [[2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2] for i in range(len(CP) - 1)],
          crack_m, sets=("map",), smooth=False)
tip_m, _ = emit_mat("CrackTip", (1.0, 0.9, 0.7), 12.0)
MTIP = puts(sph("CrackTip", (0, 0, 0), 0.07, tip_m, 16, 10), "map")


def map_crack(L, widen=1.0):
    j = np.searchsorted(CCUM, L)
    j = min(max(j, 1), len(CP) - 1)
    f = (L - CCUM[j - 1]) / max(CCUM[j] - CCUM[j - 1], 1e-6)
    tip = CP[j - 1] + (CP[j] - CP[j - 1]) * min(max(f, 0), 1)
    pts = CP.copy()
    pts[CCUM > L] = tip
    d = np.gradient(pts, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], -1)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    w = (0.035 * np.clip(1 - np.minimum(CCUM, L) / max(L, 1e-3), 0.12, 1.0) + 0.01)[:, None] * widen
    a = pts + nrm * w
    b = pts - nrm * w
    v = np.stack([np.stack([a[:, 0], np.full(len(a), -0.06), a[:, 1]], -1),
                  np.stack([b[:, 0], np.full(len(b), -0.06), b[:, 1]], -1)], 1).reshape(-1, 3)
    return v, tip


light("MapKey", "AREA", MO + np.array([-10, -18, 12]), MO, 9000, 14, (1.0, 0.97, 0.92), "map")
light("MapFill", "AREA", MO + np.array([12, -14, -6]), MO, 4000, 14, (0.8, 0.88, 1.0), "map")


def pose_map(n, gain, tf, push_vis, crack_len, pulse):
    s = G.stress(MX, MZ, n, gain * (1 + 0.12 * pulse))
    set_attr(PANEL, "stress", np.maximum(s.ravel(), 0.0))
    MWIN.set(map_window_verts(n) + MO)
    PUSH.o.hide_render = bool(push_vis <= 0.01)
    if push_vis > 0.01:
        pose_push(tf, n, push_vis)
    on = crack_len > 0.02
    MCR.o.hide_render = bool(not on)
    MTIP.hide_render = bool(not on)
    if on:
        v, tip = map_crack(crack_len)
        MCR.set(v + MO)
        MTIP.location = tuple(MO + np.array([tip[0], -0.08, tip[1]]))


# ================================================================= the 1950s jetliner (comet + tank sets)
def jet_sections(prefix, origin, sets, split=True):
    """Build the jet as rigid sections, each parented to an empty: returns {name: empty}."""
    secs = {}
    bounds = [(0.0, G.JET_SPLIT[0]), (G.JET_SPLIT[0], G.JET_SPLIT[1]), (G.JET_SPLIT[1], G.JET_L)] if split \
        else [(0.0, G.JET_L)]
    names = ["nose", "mid", "tail"] if split else ["all"]
    nph = 56
    ph = np.linspace(-math.pi, math.pi, nph, endpoint=False)
    for (s0, s1), nm in zip(bounds, names):
        e = bpy.data.objects.new(f"{prefix}_{nm}", None)
        col.objects.link(e)
        piv = G.jet_surf(0.5 * (s0 + s1), 0.0) * np.array([0, 1, 0]) + np.array([0, 0, G.jet_zc(0.5 * (s0 + s1))])
        e.location = tuple(np.asarray(origin) + piv)
        secs[nm] = (e, piv)
        if s0 == 0.0:
            ss = np.concatenate([np.linspace(0, G.JET_NOSE, 26) ** 1.0, np.linspace(G.JET_NOSE, s1, 12)[1:]])
            ss[0] = 0.02
        else:
            ss = np.linspace(s0, s1, max(6, int((s1 - s0) / 2.5)))
        S_, P_ = np.meshgrid(ss, ph, indexing="ij")
        v = G.jet_surf(S_, P_).reshape(-1, 3) - piv
        f = grid_faces(len(ss), nph, True)
        f = [q[::-1] for q in f]
        arc = (-np.abs(0.5 * (P_[:-1] + np.roll(P_, -1, 1)[:-1])) * G.JET_R + G.JET_R * math.radians(78)).ravel()
        o = obj_from(f"{prefix}_{nm}_skin", v, f, white_m)
        multi_mat(o, SKIN_MATS, zone_mats(arc))
        o.parent = e
        puts(o, sets)
        # torn end caps (dark) where the sections separate
        for se_ in ((s0,) if s0 > 0 else ()) + ((s1,) if s1 < G.JET_L else ()):
            rr = G.jet_r(se_) * 0.985
            cv = np.vstack([[[0, -se_, G.jet_zc(se_)]],
                            np.stack([rr * np.sin(ph), np.full(nph, -se_), G.jet_zc(se_) + rr * np.cos(ph)], -1)])
            cap = obj_from(f"{prefix}_{nm}_cap{int(se_)}", cv - piv, disk_faces(nph, 0, 1), dark_m, smooth=False)
            cap.parent = e
            puts(cap, sets)
        # square windows (and cockpit glazing on the nose)
        bw = Builder()
        for s in G.JET_WIN_S:
            if not (s0 < s < s1):
                continue
            for sx in (-1, 1):
                ang = sx * math.radians(78)
                p = G.jet_surf(s, ang) - piv
                bw.add(*box_vf(-0.04, 0.04, -0.62, 0.62, -0.62, 0.62),
                       Matrix.Translation(V(tuple(p))) @ Matrix.Rotation(-ang, 4, "Y")
                       @ Matrix.Rotation(math.pi / 2, 4, "Y"))
        if s0 == 0.0:
            for (s, a_) in ((5.2, -24), (5.2, 24), (6.6, -55), (6.6, 55)):
                p = G.jet_surf(s, math.radians(a_)) - piv
                bw.sphere(tuple(p), (0.75, 0.55, 0.38), (0, math.radians(-a_), 0))
        if bw.v:
            o = bw.build(f"{prefix}_{nm}_win", glass_dark_m, smooth=False)
            o.parent = e
            puts(o, sets)
    return secs


def jet_wing(name, root, span, sweep, c0, c1, t0, t1, dih, mat, vertical=False):
    sec = np.array([(0.0, 0.0), (0.12, 0.6), (0.45, 0.5), (1.0, 0.0), (0.45, -0.35), (0.12, -0.4)])
    vv, ff = [], []
    for side in ((1,) if vertical else (-1, 1)):
        o = len(vv)
        for (cc, tt, e) in ((c0, t0, 0.0), (c1, t1, 1.0)):
            for (u, w) in sec:
                if vertical:
                    p = (w * tt, root[1] - e * span * math.tan(sweep) - u * cc, root[2] + e * span)
                else:
                    p = (side * (root[0] + e * span), root[1] - e * span * math.tan(sweep) - u * cc,
                         root[2] + e * span * math.tan(dih) + w * tt)
                vv.append(p)
        m = len(sec)
        for k in range(m):
            k1 = (k + 1) % m
            q = [o + k, o + k1, o + m + k1, o + m + k]
            ff.append(q if side < 0 else q[::-1])
        ff.append([o + k for k in range(m)][::-1] if side < 0 else [o + k for k in range(m)])
        ff.append([o + m + k for k in range(m)] if side < 0 else [o + m + k for k in range(m)][::-1])
    return obj_from(name, np.array(vv), ff, mat, smooth=False)


def jet_build(prefix, origin, sets, split=True):
    secs = jet_sections(prefix, origin, sets, split)
    mid = secs["mid" if split else "all"]
    tail = secs["tail" if split else "all"]
    wing = jet_wing(f"{prefix}_wing", (2.6, -36.0, -3.2), 52.0, math.radians(20), 26.0, 7.0, 2.6, 0.6,
                    math.radians(3), alu_m)
    wing.location = tuple(-mid[1])
    wing.parent = mid[0]
    puts(wing, sets)
    # engines buried in the wing roots: dark intakes in the leading edge, exhausts at the trailing edge
    bi = Builder()
    for sx in (-1, 1):
        for k in (0, 1):
            x = sx * (5.3 + k * 3.0)
            bi.sphere((x, -36.4 + abs(x) * math.tan(math.radians(20)) * 0.3, -3.0), (1.15, 0.5, 0.9))
            bi.sphere((x, -59.0 + abs(x) * math.tan(math.radians(20)) * 0.2, -3.1), (0.95, 0.4, 0.75))
    eng = bi.build(f"{prefix}_intakes", glass_dark_m)
    eng.location = tuple(-mid[1])
    eng.parent = mid[0]
    puts(eng, sets)
    for nm, args_ in (("stab", ((1.0, -78.0, 2.4), 17.0, math.radians(24), 11.0, 4.5, 0.9, 0.35, math.radians(6),
                                alu_m, False)),
                      ("fin", ((0.0, -72.0, 4.2), 15.0, math.radians(35), 15.0, 6.0, 1.1, 0.45, 0, white_m, True))):
        o = jet_wing(f"{prefix}_{nm}", *args_[:-1], vertical=args_[-1])
        o.location = tuple(-tail[1])
        o.parent = tail[0]
        puts(o, sets)
    return secs


# ================================================================= set "comet": over the sea, breaks apart
CMO = G.COMET_O
JET = jet_build("Comet", CMO, ("comet",), split=True)
sea_m, _sea = principled("Sea", (0.02, 0.1, 0.2), rough=0.12, coat=0.4)
_snt = sea_m.node_tree
_stc = node(_snt, "ShaderNodeTexCoord")
_snz = node(_snt, "ShaderNodeTexNoise", Scale=0.004, Detail=8.0)
_snt.links.new(_stc.outputs["Object"], _snz.inputs["Vector"])
_sbp = node(_snt, "ShaderNodeBump", Strength=0.35, Distance=1.0)
_snt.links.new(_snz.outputs["Fac"], _sbp.inputs["Height"])
_snt.links.new(_sbp.outputs["Normal"], _sea.inputs["Normal"])
SEA = puts(obj_from("Sea", [(-90000, -90000, 0), (90000, -90000, 0), (90000, 90000, 0), (-90000, 90000, 0)],
                    [[0, 1, 2, 3]], sea_m, smooth=False), "comet")
CCL = puts(obj_from("CometClouds", [(-60000, -60000, 0), (60000, -60000, 0), (60000, 60000, 0), (-60000, 60000, 0)],
                    [[0, 1, 2, 3]], cloud_mat("CloudsPatchy", alpha=True), smooth=False), "comet")
C_DEBRIS = flake_burst("CometDebris", 320, ("comet",), 81, alu_m, size=(0.3, 1.1))
C_MIST = Burst("CometMist", 900, ("comet",), 82, mist_m, kind="tet", size=(0.15, 0.5))
C_SMOKE = Burst("CometSmoke", 600, ("comet",), 83, smoke_m, kind="tet", size=(0.3, 0.9))
_gcb = np.random.default_rng(84)
_rup = G.jet_surf(G.JET_SPLIT[0], 0.0, CMO)                        # rupture at the cabin roof, ahead of the wing


def _emit_comet(b, n_sp, back, span, seed, k=(0.8, 2.0), grav=4.0):
    g = np.random.default_rng(seed)
    n = b.n
    d = rand_dirs(n, g)
    d[:, 2] = np.abs(d[:, 2]) * 0.8 + 0.2
    b.emit(_rup + g.normal(0, 1.0, (n, 3)),
           d * g.uniform(*n_sp, n)[:, None] + np.array([0, -1.0, 0]) * g.uniform(*back, n)[:, None],
           g.uniform(0, span, n) ** 1.2, g.uniform(*k, n), grav)


_emit_comet(C_DEBRIS, (10, 40), (5, 40), 0.5, 85, grav=10.0)
_emit_comet(C_MIST, (8, 30), (10, 50), 1.2, 86)
_emit_comet(C_SMOKE, (4, 14), (20, 60), 2.5, 87, grav=1.0)
_gsec = {"nose": (np.array([0.4, -0.9, 0.2]), np.array([-1.6, 0.0, -0.4]), 7.0, 1.3),
         "mid": (np.array([0.1, 0.2, 1.0]), np.array([0.25, 0.0, 0.1]), 3.0, 0.3),
         "tail": (np.array([0.8, 0.1, -0.3]), np.array([1.4, 0.2, 0.5]), 12.0, 1.8)}


def pose_comet(tb, tw):
    """tb: time since the rupture (negative = intact); tw: running time for the sea / clouds."""
    SEA.location = (0, -380.0 * tw, CMO[2] - 9000)
    CCL.location = (0, -380.0 * tw, CMO[2] - 3200)
    a = max(0.0, tb)
    for nm, (e, piv) in JET.items():
        ax, w, drag, fall = _gsec[nm]
        if a > 0:
            axn = ax / np.linalg.norm(ax)
            ang = np.linalg.norm(w) * a * (0.5 + 0.5 * min(1, a / 0.6))
            e.rotation_mode = "QUATERNION"
            e.rotation_quaternion = Quaternion(V(tuple(axn)), ang * np.sign(w[np.argmax(np.abs(w))]))
            off = np.array([0.0, -drag * a * a, -fall * 4.0 * a * a])
            if nm == "nose":
                off += np.array([0, 3.0 * a, -2.0 * a])
            e.location = tuple(CMO + piv + off)
        else:
            e.rotation_mode = "QUATERNION"
            e.rotation_quaternion = (1, 0, 0, 0)
            e.location = tuple(CMO + piv + np.array([0, 0, 0.15 * math.sin(tw * 1.3)]))
    for b in (C_DEBRIS, C_MIST, C_SMOKE):
        b.dyn.o.hide_render = bool(tb <= 0)
        if tb > 0:
            b.pose(tb)


# ================================================================= set "tank": the airframe in a water tank
TO = G.TANK_O
TJET = jet_build("TankJet", TO, ("tank",), split=False)
TJ_E, TJ_P = TJET["all"]
water_m, _wnt = new_mat("Water")[:2]
_wo = water_m.node_tree.nodes["Material Output"]
_wtr = node(_wnt, "ShaderNodeBsdfTransparent", Color=(0.42, 0.78, 0.88, 1))
_wgl = node(_wnt, "ShaderNodeBsdfGlossy", Roughness=0.08)
_wfr = node(_wnt, "ShaderNodeFresnel", IOR=1.33)
_wmx = _wnt.nodes.new("ShaderNodeMixShader")
_wnt.links.new(_wfr.outputs[0], _wmx.inputs[0])
_wnt.links.new(_wtr.outputs[0], _wmx.inputs[1])
_wnt.links.new(_wgl.outputs[0], _wmx.inputs[2])
_wnt.links.new(_wmx.outputs[0], _wo.inputs[0])
TK = dict(x0=-15.0, x1=15.0, y0=-100.0, y1=8.0, z0=-14.0, z1=11.0)


def tbox(name, lo, hi, mat):
    return puts(box(name, tuple(TO + np.array(lo)), tuple(TO + np.array(hi)), mat), "tank")


# water: one volume (blue absorption + a little haze) filling the tank, and a glossy surface on top
wvol_m, _wv_nt, _wv_out = new_mat("WaterVol")
_wpv = node(_wv_nt, "ShaderNodeVolumeAbsorption")
_wpv.inputs["Color"].default_value = (0.3, 0.75, 0.88, 1)
_wpv.inputs["Density"].default_value = 0.035
_wv_nt.links.new(_wpv.outputs[0], _wv_out.inputs["Volume"])
tbox("WaterVolume", (TK["x0"], TK["y0"], TK["z0"]), (TK["x1"], TK["y1"], TK["z1"] - 0.5), wvol_m)
tankwall_m, _ = principled("TankWall", (0.3, 0.52, 0.62), rough=0.55, bump=0.08, bump_scale=0.6)
tbox("TankBack", (TK["x1"], TK["y0"], TK["z0"] - 1), (TK["x1"] + 1, TK["y1"], TK["z1"] + 2), tankwall_m)
tbox("TankEnd0", (TK["x0"], TK["y0"] - 1, TK["z0"] - 1), (TK["x1"], TK["y0"], TK["z1"] + 2), tankwall_m)
tbox("TankEnd1", (TK["x0"], TK["y1"], TK["z0"] - 1), (TK["x1"], TK["y1"] + 1, TK["z1"] + 2), tankwall_m)
tbox("TankBottom", (TK["x0"], TK["y0"], TK["z0"] - 1), (TK["x1"], TK["y1"], TK["z0"]), tankwall_m)
hall_m, _ = principled("HallFloor", (0.2, 0.2, 0.21), rough=0.8)
tbox("HallFloor", (TK["x0"] - 80, TK["y0"] - 60, TK["z0"] - 2), (TK["x1"] + 80, TK["y1"] + 60, TK["z0"] - 1), hall_m)
tbox("HallWall", (TK["x1"] + 30, TK["y0"] - 60, TK["z0"] - 2), (TK["x1"] + 31, TK["y1"] + 60, TK["z1"] + 40), hall_m)
rim_m, _ = principled("TankRim", (0.85, 0.6, 0.08), rough=0.5)
tbox("TankRimFront", (TK["x0"] - 1.2, TK["y0"], TK["z1"]), (TK["x0"], TK["y1"], TK["z1"] + 0.8), rim_m)
tbox("TankFrontLow", (TK["x0"] - 1.2, TK["y0"], TK["z0"] - 1), (TK["x0"], TK["y1"], TK["z0"] + 0.6), rim_m)
light("TankIn1", "AREA", TO + np.array([-12, -20, 9]), TO + np.array([0, -24, 0]), 6000, 6, (0.6, 0.9, 1.0), "tank")
light("TankIn2", "AREA", TO + np.array([-12, -55, 9]), TO + np.array([0, -55, 0]), 6000, 6, (0.6, 0.9, 1.0), "tank")
light("TankTop", "AREA", TO + np.array([-6, -40, 9.5]), TO + np.array([0, -40, 0]), 14000, 30, (0.85, 0.95, 1.0),
      "tank")
surf_m, _sfp = principled("WaterSurf", (0.1, 0.35, 0.45), rough=0.12, coat=0.0)
_sfp.inputs["Metallic"].default_value = 0.6
puts(obj_from("WaterSurf", [tuple(TO + np.array(p)) for p in ((TK["x0"], TK["y0"], TK["z1"] - 0.5),
                                                                (TK["x0"], TK["y1"], TK["z1"] - 0.5),
                                                                (TK["x1"], TK["y1"], TK["z1"] - 0.5),
                                                                (TK["x1"], TK["y0"], TK["z1"] - 0.5))],
              [[0, 1, 2, 3]], surf_m, smooth=False), "tank")
light("TankKey", "AREA", TO + np.array([-40, -10, 18]), TO + np.array([0, -30, 0]), 40000, 20, (1.0, 0.95, 0.88),
      "tank")
# the split: skin flap at a window corner + bubbles jetting out
SPLIT_S = G.JET_WIN_S[3]
_ang = -math.radians(78)
SPLIT_P = G.jet_surf(SPLIT_S - 0.62, _ang + 0.62 / G.JET_R, TO)          # forward-upper corner of a window
SPLIT_N = np.array([math.sin(_ang + 0.12), 0, math.cos(_ang + 0.12)])
bub_m, _bub = new_mat("Bubble")[:2]
_bo = bub_m.node_tree.nodes["Material Output"]
_bgl = node(_bub, "ShaderNodeBsdfGlossy", Roughness=0.05)
_btr = node(_bub, "ShaderNodeBsdfTransparent")
_bmx = _bub.nodes.new("ShaderNodeMixShader")
_bmx.inputs[0].default_value = 0.55
_bub.links.new(_btr.outputs[0], _bmx.inputs[1])
_bub.links.new(_bgl.outputs[0], _bmx.inputs[2])
_bub.links.new(_bmx.outputs[0], _bo.inputs[0])
BUB = Burst("Bubbles", 1100, ("tank",), 91, bub_m, kind="tet", size=(0.03, 0.12))
_sv, _sf = sphere_vf(10, 7)
BUB.L = np.repeat(_sv[None], BUB.n, 0) * np.random.default_rng(92).uniform(0.04, 0.2, (BUB.n, 1, 1))
BUB.dyn.o.data.clear_geometry()
BUB.dyn.o.data.from_pydata(np.zeros((BUB.n * len(_sv), 3)).tolist(), [],
                           [[k * len(_sv) + i for i in fc] for k in range(BUB.n) for fc in _sf])
BUB.dyn.o.data.shade_smooth()
_gb = np.random.default_rng(93)
# a steady stream out of the tear that rises away (it must not bury the tear or fill the lens)
BUB.L *= 0.6
_bd = SPLIT_N[None] * _gb.uniform(0.8, 3.0, BUB.n)[:, None] + _gb.normal(0, 0.5, (BUB.n, 3)) + np.array([0, 0.4, 1.6])
_bp = SPLIT_P + np.outer(_gb.uniform(0, 1, BUB.n), np.array([0, -0.9, 0.35])) + _gb.normal(0, 0.05, (BUB.n, 3))
BUB.emit(_bp + SPLIT_N * 0.05, _bd, 0.2 + _gb.uniform(0.0, 3.8, BUB.n) ** 1.3, _gb.uniform(1.2, 2.5, BUB.n), -6.0)
FLAP_L, FLAP_F = slab(1, 0.6, 0.42, 0.04)
FLAP = Dyn("Flap", np.zeros((8, 3)), FLAP_F, alu_m, sets=("tank",), smooth=False)
HOLE = Dyn("TearHole", np.zeros((8, 3)), FLAP_F, crack_m, sets=("tank",), smooth=False)   # the dark gap the flap leaves
_tcr = Dyn("TankCrack", np.zeros((len(CP) * 2, 3)),
           [[2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2] for i in range(len(CP) - 1)], crack_m, sets=("tank",),
           smooth=False)


def pose_tank(press, ts):
    """press: pressure 0..1 in the current cycle; ts: time since the split (negative = intact)."""
    e = 0.012 * press
    TJ_E.scale = (1 + e, 1, 1 + e)
    a = max(0.0, ts)
    b_on = ts > 0
    BUB.dyn.o.hide_render = bool(not b_on)
    if b_on:
        BUB.pose(a)
    # flap: hinged at the corner, peels outward
    ang = (1 - math.exp(-a / 0.12)) * math.radians(105) if b_on else 0.0
    t_ = np.array([0, 1.0, 0])
    nb = np.cross(SPLIT_N, t_)
    B = np.array([t_, nb, SPLIT_N])
    loc = FLAP_L @ B + np.array([0, 0, 0])
    hinge = SPLIT_P - t_ * 0.0
    Rm = rodrigues(nb[None], np.array([ang]))[0]
    FLAP.set(((loc + t_ * 0.6 + SPLIT_N * 0.03) @ Rm.T) + hinge)
    FLAP.o.hide_render = True                 # the gaping crack reads better than a flap at this distance
    hs = min(1.0, a / 0.15)
    HOLE.set((FLAP_L * np.array([hs, hs, 0.2])) @ B + t_ * 0.6 * hs + SPLIT_N * 0.012 + hinge)
    HOLE.o.hide_render = True
    # crack on the skin growing just before the split
    L = 0.0 if ts < -0.6 else min(2.4, (ts + 0.6) * 2.5)
    _tcr.o.hide_render = bool(L <= 0.02)
    if L > 0.02:
        v, _tip = map_crack(L, 1.0 + 7.0 * (1 - math.exp(-a / 0.12)) if b_on else 1.0)   # the crack gapes open
        # map (x, z) crack coords onto the fuselage near the split point: x -> along -Y (aft), z -> around
        mx_ = v[:, 0] - G.MAP_CORNER[0]
        mz_ = v[:, 2] - G.MAP_CORNER[1]
        w = G.jet_surf(SPLIT_S - 0.62 + mx_ * 0.9, _ang + (0.62 + mz_ * 0.9) / G.JET_R, TO)
        w = w + (w - (TO + np.array([0, w[0, 1] - TO[1], G.jet_zc(SPLIT_S)]))) * 0.022   # stays above the skin when the hull swells
        _tcr.set(w)


# ================================================================= per-frame pose
for _o in list(SETS["cut"]):
    pass


def pose(t):
    i = T.shot_index(t)
    s = T.SET_OF[i]
    for k, objs in SETS.items():
        for o in objs:
            o.hide_render = True
    for o in SETS[s]:
        o.hide_render = False
    SUN.hide_render = s not in ("rip", "comet")
    sky = s in ("rip", "comet")
    WSKY.default_value = 1.0 if sky else 0.0
    WSTR.default_value = 1.0
    if s == "rip":
        te, n, crack = T.rip_state(t)
        pose_rip(te, n, crack, t)
    elif s == "comet":
        pose_comet(*T.comet_clock(t))
    elif s == "cut":
        pose_cut(*T.cut_state(t))
    elif s == "map":
        pose_map(*T.map_state(t))
    elif s == "tank":
        pose_tank(*T.tank_state(t))


# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.clip_start = 0.01
cam_d.clip_end = 200000
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
c.volume_step_rate = 6.0
c.volume_preview_step_rate = 6.0
c.volume_bounces = 0
c.volume_max_steps = 256
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
