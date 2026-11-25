"""Blender scene for "Scientists Blast a Fuel Pellet With 192 Lasers" (Cycles, posed per frame).

Sets (each far from the others, only the active one is rendered):
  cap     1 unit = 1 mm : gold hohlraum (cutaway) with the 2 mm fuel capsule, its implosion and burn
  chamber 1 unit = 10 cm: the 10 m target chamber, 192 beams, a star at its centre
  sun     the Sun with a deuterium and a tritium nucleus fusing in front of it
  drop    a drop of seawater with a deuterium nucleus inside
  pepper  1 unit = 1 mm : the capsule next to a peppercorn

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
    def __init__(self, name, verts, faces, mat, sets=("cap",), smooth=True):
        self.o = obj_from(name, verts, faces, mat, smooth)
        self.n = len(verts)
        for s in sets:
            SETS[s].append(self.o)

    def set(self, verts):
        v = np.asarray(verts, np.float32).reshape(-1)
        self.o.data.vertices.foreach_set("co", v)
        self.o.data.update()




# ================================================================= sets
SETS = {k: [] for k in ("cap", "chamber", "sun", "drop", "pepper")}
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


# ================================================================= world: near-black; stars only in the sun set
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
for n_ in list(wnt.nodes):
    if n_.type != "OUTPUT_WORLD":
        wnt.nodes.remove(n_)
_wtc = wnt.nodes.new("ShaderNodeTexCoord")
_wvo = wnt.nodes.new("ShaderNodeTexVoronoi")
_wvo.inputs["Scale"].default_value = 260.0
wnt.links.new(_wtc.outputs["Generated"], _wvo.inputs["Vector"])
_wr = ramp(wnt, [(0.0, (1.0, 1.0, 1.0)), (0.035, (0.25, 0.25, 0.3)), (0.06, (0.0, 0.0, 0.0))])
wnt.links.new(_wvo.outputs["Distance"], _wr.inputs[0])
_wn = wnt.nodes.new("ShaderNodeTexNoise")
_wn.inputs["Scale"].default_value = 900.0
wnt.links.new(_wtc.outputs["Generated"], _wn.inputs["Vector"])
_wt = ramp(wnt, [(0.0, (0, 0, 0)), (0.62, (0, 0, 0)), (0.72, (1, 1, 1))])
wnt.links.new(_wn.outputs["Fac"], _wt.inputs[0])
_wm = wnt.nodes.new("ShaderNodeMixRGB")
_wm.blend_type = "MULTIPLY"
_wm.inputs[0].default_value = 1.0
wnt.links.new(_wr.outputs[0], _wm.inputs[1])
wnt.links.new(_wt.outputs[0], _wm.inputs[2])
_wadd = wnt.nodes.new("ShaderNodeMixRGB")               # stars * k + dark base colour
_wadd.blend_type = "ADD"
_wadd.inputs[0].default_value = 1.0
_wstar = wnt.nodes.new("ShaderNodeMixRGB")
_wstar.blend_type = "MULTIPLY"
_wstar.inputs[0].default_value = 1.0
wnt.links.new(_wm.outputs[0], _wstar.inputs[1])
_wstar.inputs[2].default_value = (0.0, 0.0, 0.0, 1)    # star strength per frame (sun set only)
WSTAR = _wstar.inputs[2]
wnt.links.new(_wstar.outputs[0], _wadd.inputs[1])
_wadd.inputs[2].default_value = (0.0015, 0.0018, 0.003, 1)
wbg = wnt.nodes.new("ShaderNodeBackground")
wbg.inputs["Strength"].default_value = 1.0
wnt.links.new(_wadd.outputs[0], wbg.inputs["Color"])
_wlp = wnt.nodes.new("ShaderNodeLightPath")
_wbk = wnt.nodes.new("ShaderNodeBackground")
_wbk.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1)
_wmx = wnt.nodes.new("ShaderNodeMixShader")
wnt.links.new(_wlp.outputs["Is Camera Ray"], _wmx.inputs[0])
wnt.links.new(_wbk.outputs[0], _wmx.inputs[1])
wnt.links.new(wbg.outputs[0], _wmx.inputs[2])
wnt.links.new(_wmx.outputs[0], wnt.nodes["World Output"].inputs[0])


def point(name, loc, energy, color, radius, s):
    l = bpy.data.lights.new(name, "POINT")
    l.energy, l.color, l.shadow_soft_size = energy, color, radius
    o = bpy.data.objects.new(name, l)
    o.location = loc
    col.objects.link(o)
    return put(o, s), l


# ================================================================= set "cap": hohlraum + capsule (1 unit = 1 mm)
CO = np.array(T.CAP_O)
HR, HL, LEH = 3.2, 5.5, 1.55              # hohlraum inner radius, half length, laser entrance hole radius
CUT0, CUT1 = math.radians(-30), math.radians(210)   # wall kept between these angles: window towards -Y


def lathe_part(name, prof, mat, a0, a1, seg=72, closed=True):
    """Partial surface of revolution around Z (a0..a1), with the cut faces filled."""
    verts, faces = [], []
    n = len(prof)
    for k in range(seg + 1):
        a = a0 + (a1 - a0) * k / seg
        for r, z in prof:
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for k in range(seg):
        for i in range(n if closed else n - 1):
            i1 = (i + 1) % n
            faces.append([k * n + i, k * n + i1, (k + 1) * n + i1, (k + 1) * n + i])
    if closed:
        faces.append(list(range(n))[::-1])
        faces.append([seg * n + i for i in range(n)])
    o = obj_from(name, [tuple(np.array(v) + CO) for v in verts], faces, mat)
    return o


gold_m, _gp = principled("Gold", GOLD, rough=0.22)
_gp.inputs["Metallic"].default_value = 1.0
HOHL = put(lathe_part("Hohlraum", [(LEH, HL), (HR + 0.18, HL), (HR + 0.18, -HL), (LEH, -HL), (LEH, -HL + 0.14),
                                   (HR, -HL + 0.14), (HR, HL - 0.14), (LEH, HL - 0.14)], gold_m, CUT0, CUT1), "cap")
for _m in HOHL.data.polygons:
    _m.use_smooth = False

# inner liner that glows when the laser heats it (bright bands where the beams land)
liner_m, _lnt, _lout = new_mat("Liner")
_lp = node(_lnt, "ShaderNodeBsdfPrincipled", Roughness=0.25, Metallic=1.0)
_lp.inputs["Base Color"].default_value = (*GOLD, 1)
_ltc = node(_lnt, "ShaderNodeTexCoord")
_lsep = _lnt.nodes.new("ShaderNodeSeparateXYZ")
link(_lnt, _ltc.outputs["Object"], _lsep.inputs[0])
_az = math_node(_lnt, "ABSOLUTE", _lsep.outputs["Z"])
_d = math_node(_lnt, "SUBTRACT", _az, 2.6)
_d2 = math_node(_lnt, "MULTIPLY", _d, _d)
_band = math_node(_lnt, "EXPONENT", math_node(_lnt, "MULTIPLY", _d2, -0.9))
LINER_G = value(_lnt, 0.0)
_em = math_node(_lnt, "MULTIPLY", math_node(_lnt, "ADD", math_node(_lnt, "MULTIPLY", _band, 2.2), 0.35), LINER_G)
_lp.inputs["Emission Color"].default_value = (1.0, 0.62, 0.32, 1)
link(_lnt, _em, _lp.inputs["Emission Strength"])
link(_lnt, _lp.outputs[0], _lout.inputs[0])
LINER = put(lathe_part("Liner", [(HR - 0.01, HL - 0.15), (HR - 0.01, -HL + 0.15)], liner_m, CUT0, CUT1,
                       closed=False), "cap")

# capsule: diamond ablator shell broken into shards (tiled sphere), DT fuel ball inside, hot spot
_iv, _if = icosphere(3)
SH_C = np.array([_iv[f].mean(0) for f in _if])
SH_C /= np.linalg.norm(SH_C, axis=1, keepdims=True)
NSH = len(_if)
_sv = []
for k, f in enumerate(_if):
    tri = _iv[f]
    c = SH_C[k]
    tri = c + (tri - c) * 0.965                   # thin seams between shards
    _sv.append(np.concatenate([tri, tri * 0.9]))  # 0.1 mm thick shell
SH_LOCAL = np.array(_sv) - SH_C[:, None, :]       # vertices relative to the shard centre (radius 1)
SH_F = []
for k in range(NSH):
    o = 6 * k
    SH_F += [[o, o + 1, o + 2], [o + 5, o + 4, o + 3], [o, o + 3, o + 4, o + 1], [o + 1, o + 4, o + 5, o + 2],
             [o + 2, o + 5, o + 3, o]]
_g = np.random.default_rng(3)
SH_TS = -0.34 + 0.24 * _g.uniform(0, 1, NSH)      # when each shard lets go (implosion clock)
SH_V = _g.uniform(1.8, 7.5, NSH)                  # outward speed, mm per screen-second
SH_AX = rand_dirs(NSH, _g)
SH_W = _g.uniform(2.0, 9.0, NSH)

shard_m, _snt, _sout = new_mat("Shard")
_spb = node(_snt, "ShaderNodeBsdfPrincipled", Roughness=0.12, IOR=2.4)
_spb.inputs["Base Color"].default_value = (0.1, 0.11, 0.13, 1)
_spb.inputs["Transmission Weight"].default_value = 0.0
_spb.inputs["Emission Color"].default_value = (1.0, 0.35, 0.08, 1)
link(_snt, math_node(_snt, "MULTIPLY", attr_node(_snt, "heat"), 0.35), _spb.inputs["Emission Strength"])
link(_snt, _spb.outputs[0], _sout.inputs[0])
SHARDS = Dyn("Shards", np.zeros((NSH * 6, 3)), SH_F, shard_m, sets=("cap",), smooth=False)
attr_mesh(SHARDS.o, ["heat"])

fuel_m, _fp = principled("DTIce", (0.75, 0.86, 1.0), rough=0.3)
_fp.inputs["Transmission Weight"].default_value = 0.5
_fp.inputs["Emission Color"].default_value = (0.25, 0.45, 1.0, 1)
FUEL_E = _fp.inputs["Emission Strength"]
FUEL = put(sph("Fuel", tuple(CO), 1.0, fuel_m, 48, 24), "cap")

hot_m, HOT_A, HOT_E = fade_emit_mat("HotSpot", (1.0, 0.8, 0.5), 30.0)
soften(hot_m)
HOT = put(sph("Hot", tuple(CO), 1.0, hot_m, 32, 16), "cap")
halo_m, HALO_A, HALO_E = fade_emit_mat("Halo", (1.0, 0.55, 0.22), 2.0)
soften(halo_m)
HALO = put(sph("Halo", tuple(CO), 1.0, halo_m, 32, 16), "cap")
no_bounce([HALO])

# blow-off plasma: glowing grains leaving the surface
NPL = 2600
_g = np.random.default_rng(5)
PL_D = rand_dirs(NPL, _g)
PL_B = _g.uniform(-0.3, 1.8, NPL)
PL_V = _g.uniform(3.0, 11.0, NPL)
PL_S = _g.uniform(0.015, 0.05, NPL)
pl_m, _pnt, _pout = new_mat("Plasma")
_pem = node(_pnt, "ShaderNodeEmission", Strength=1.0)
_prp = ramp(_pnt, [(0.0, (1.0, 0.6, 0.25)), (0.35, (1.0, 0.45, 0.15)), (1.0, (0.45, 0.2, 0.9))])
_page = attr_node(_pnt, "age")
link(_pnt, _page, _prp.inputs[0])
link(_pnt, _prp.outputs[0], _pem.inputs["Color"])
link(_pnt, math_node(_pnt, "MULTIPLY", attr_node(_pnt, "glow"), 3.0), _pem.inputs["Strength"])
_ptr = node(_pnt, "ShaderNodeBsdfTransparent")
_pmx = _pnt.nodes.new("ShaderNodeMixShader")
link(_pnt, math_node(_pnt, "MINIMUM", attr_node(_pnt, "glow"), 1.0), _pmx.inputs[0])
link(_pnt, _ptr.outputs[0], _pmx.inputs[1])
link(_pnt, _pem.outputs[0], _pmx.inputs[2])
link(_pnt, _pmx.outputs[0], _pout.inputs[0])
PLASMA = Dyn("Plasma", np.zeros((NPL * 4, 3)), [[i + 4 * k for i in f] for k in range(NPL) for f in TETF], pl_m,
             sets=("cap",), smooth=False)
attr_mesh(PLASMA.o, ["age", "glow"])
no_bounce([PLASMA.o])

# neutrons from the burn: fast streaks
NNE = 420
_g = np.random.default_rng(8)
NE_D = rand_dirs(NNE, _g)
NE_V = _g.uniform(9.0, 16.0, NNE)
ne_m, NE_A, NE_E = fade_emit_mat("Neutron", (0.7, 0.9, 1.0), 25.0)
NEUT = Dyn("Neutrons", np.zeros((NNE * 14, 3)), tubes_faces(NNE, 6), ne_m, sets=("cap",), smooth=False)
no_bounce([NEUT.o])

# the beams entering both laser entrance holes (one shaft per quad: 4 cones x 24 per side = 48 quads)
CAP_BEAMS = []
for s in (1, -1):
    for th, nphi, ph0 in ((23.5, 4, 0.0), (30.0, 4, 45.0), (44.5, 8, 0.0), (50.0, 8, 22.5)):
        for k in range(nphi):
            ph = math.radians(ph0 + 360.0 * k / nphi)
            t_ = math.radians(th)
            d_in = np.array([math.sin(t_) * math.cos(ph), math.sin(t_) * math.sin(ph), -s * math.cos(t_)])
            leh = np.array([0.0, 0.0, s * HL])
            hit = leh + d_in * ((HR - 0.05) / math.sin(t_))
            far = leh - d_in * 30.0
            az = math.degrees(math.atan2(hit[1], hit[0])) % 360
            if 205 < az < 335:
                hit = leh + d_in * 0.4
            CAP_BEAMS.append((far, leh, hit))
NCB = len(CAP_BEAMS)
cb_m, CB_A, CB_E = beam_mat("CapBeam", UV, 6.0)
_cbv = tubes_verts(np.array([b[0] for b in CAP_BEAMS]) + CO, np.array([b[2] for b in CAP_BEAMS]) + CO, 0.22, 8)
CAPBEAM = put(obj_from("CapBeams", _cbv, tubes_faces(NCB, 8), cb_m, smooth=False), "cap")
no_bounce([CAPBEAM])

# lights
area("CapKey", tuple(CO + np.array([-14.0, -16.0, 12.0])), tuple(CO), 2500.0, 10.0, (0.85, 0.9, 1.0), "cap")
area("CapRim", tuple(CO + np.array([16.0, 14.0, 6.0])), tuple(CO), 1500.0, 8.0, (1.0, 0.8, 0.6), "cap")
CAP_IN, _cap_in = point("CapInner", tuple(CO + np.array([0.0, 1.8, 0.0])), 0.0, (1.0, 0.6, 0.3), 0.8, "cap")
CAP_HOT, _cap_hot = point("CapHot", tuple(CO), 0.0, (1.0, 0.85, 0.7), 0.2, "cap")


def pose_cap(t):
    te = T.imp_clock(t)
    beam = T.cap_beam(t)
    close = T.shot_index(t) in (0, 6, 9)
    CAPBEAM.hide_render = beam < 0.01 or close
    CB_A.default_value = 0.3 * beam
    CB_E.default_value = 2.5 * beam
    g = T.wall_glow(t)
    LINER_G.default_value = (0.12 if close else 0.75) * g
    _cap_in.energy = 25.0 * g
    if te is None:
        te = -5.0
    R = T.capsule_r(te)
    # shards: tile the shell (radius R) until they let go, then fly out spinning
    age = np.maximum(0.0, te - SH_TS)
    rad = np.where(te < SH_TS, R, 1.0 + SH_V * age + 0.6 * age * age)
    heat = np.where(te < SH_TS, 0.0, np.exp(-age / 0.4)) * (te > -0.4)
    rot = []
    for k in range(NSH):
        if age[k] <= 0:
            rot.append(np.eye(3))
        else:
            rot.append(np.array(Matrix.Rotation(SH_W[k] * age[k], 3, V(SH_AX[k]))))
    rot = np.array(rot)
    sc = np.where(te < SH_TS, R, 1.0)[:, None, None]
    v = np.einsum("kij,kvj->kvi", rot, SH_LOCAL * sc) + (SH_C * rad[:, None])[:, None, :] + CO
    SHARDS.set(v)
    set_attr(SHARDS.o, "heat", np.repeat(heat, 6))
    burn = T.burn_age(t)
    SHARDS.o.hide_render = not T.shards_on(t)
    # fuel ball compresses; hot spot heats up
    rf = 0.9 * R
    FUEL.scale = (rf, rf, rf)
    comp = T.compression(te)
    FUEL_E.default_value = 0.05 + 0.5 * comp
    FUEL.hide_render = burn is not None and burn > 0.25
    hs = 0.5 * rf * (0.3 + 0.7 * comp)
    HOT.hide_render = comp < 0.02 and burn is None
    HOT_A.default_value = min(1.0, comp * 1.5)
    HOT_E.default_value = 4.0 + 18.0 * comp
    HOT.scale = (hs, hs, hs)
    _cap_hot.energy = 3.0 * comp
    # plasma grains: born on the surface, glow, fade
    pa = te - PL_B
    alive = (pa > 0) & (te > -0.4)
    pr = R + PL_V * np.maximum(pa, 0)
    glow = np.where(alive, np.exp(-np.maximum(pa, 0) / 0.8), 0.0)
    pos = PL_D * pr[:, None] + CO
    sz = PL_S * (1 + 0.8 * np.maximum(pa, 0))
    PLASMA.set(pos[:, None, :] + TET[None] * sz[:, None, None])
    set_attr(PLASMA.o, "age", np.repeat(np.clip(pa / 1.2, 0, 1), 4))
    set_attr(PLASMA.o, "glow", np.repeat(glow, 4))
    PLASMA.o.hide_render = not alive.any()
    ha = max(0.0, te + 0.3)
    hr = 1.0 + 0.8 * (1 - math.exp(-ha / 0.4))
    HALO.hide_render = te < -0.3 or ha > 1.6
    HALO.scale = (hr, hr, hr)
    HALO_A.default_value = 0.35 * math.exp(-ha / 0.5)
    HALO_E.default_value = 1.5
    # ignition burn: the hot spot blows up, neutrons stream out
    if burn is not None and burn >= 0:
        b = burn
        rr = rf * 0.5 + 3.5 * (1 - math.exp(-b / 0.35))
        HOT.hide_render = False
        HOT.scale = (rr, rr, rr)
        HOT_A.default_value = 0.85 * max(0.0, 1.0 - b / 1.6)
        HOT_E.default_value = 50.0 * math.exp(-b / 0.4) + 3.0
        _cap_hot.energy = 1500.0 * math.exp(-b / 0.4) + 60.0
        d = NE_V * b
        NEUT.o.hide_render = False
        NEUT.set(tubes_verts(NE_D * np.maximum(d - 2.2, 0)[:, None] + CO, NE_D * d[:, None] + CO, 0.025, 6))
        NE_A.default_value = 1.0
        NE_E.default_value = 25.0
    else:
        NEUT.o.hide_render = True


# ================================================================= set "chamber" (1 unit = 10 cm; radius 5 m)
HO = np.array(T.CH_O)
CHR = 50.0
wall_m, _wp = principled("ChamberWall", (0.07, 0.08, 0.1), rough=0.45, bump=0.25, bump_scale=0.6)
_wp.inputs["Metallic"].default_value = 0.7
_cw = sph("ChamberWall", tuple(HO), CHR, wall_m, 96, 48)
for _p in _cw.data.polygons:
    _p.flip()
put(_cw, "chamber")
_g = np.random.default_rng(12)
PORTS = []                                          # 48 beam ports (24 top, 24 bottom)
for s in (1, -1):
    for th, nphi, ph0 in ((23.5, 4, 0.0), (30.0, 4, 45.0), (44.5, 8, 0.0), (50.0, 8, 22.5)):
        for k in range(nphi):
            ph = math.radians(ph0 + 360.0 * k / nphi)
            t_ = math.radians(th)
            PORTS.append(np.array([math.sin(t_) * math.cos(ph), math.sin(t_) * math.sin(ph), s * math.cos(t_)]))
PORTS = np.array(PORTS)
DIAG = rand_dirs(70, _g)
DIAG = DIAG[np.abs(DIAG[:, 2]) < 0.6]
port_m, _pp = principled("Port", (0.05, 0.05, 0.06), rough=0.35)
_pp.inputs["Metallic"].default_value = 0.9
flange_m, _fl = principled("Flange", (0.55, 0.58, 0.62), rough=0.3)
_fl.inputs["Metallic"].default_value = 1.0
_bp, _bf = Builder(), Builder()
CYL_V = np.array([(math.cos(2 * math.pi * k / 20), math.sin(2 * math.pi * k / 20), z) for z in (0, 1) for k in range(20)])
CYL_F = [[k, (k + 1) % 20, 20 + (k + 1) % 20, 20 + k] for k in range(20)] + [list(range(20))[::-1],
                                                                            list(range(20, 40))]
for d, rad in [(p, 1.8) for p in PORTS] + [(p, 1.1) for p in DIAG]:
    a, b = basis(d)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2] = a * rad, b * rad, d * 1.4
    M[:3, 3] = HO + d * (CHR - 0.5)
    _bp.add(CYL_V, CYL_F[:-1], M)
    M2 = M.copy()
    M2[:3, 0], M2[:3, 1], M2[:3, 2] = a * rad * 1.35, b * rad * 1.35, d * 0.25
    M2[:3, 3] = HO + d * (CHR - 0.35)
    _bf.add(CYL_V, CYL_F, M2)
put(_bp.build("Ports", port_m, smooth=False), "chamber")
put(_bf.build("Flanges", flange_m, smooth=False), "chamber")
# positioner arm and target
arm_m, _ap = principled("Arm", (0.7, 0.72, 0.75), rough=0.3)
_ap.inputs["Metallic"].default_value = 1.0
put(tube("Arm", [tuple(HO + np.array([0.0, 0.0, 0.0]) + np.array([-0.4, 0, 0])),
                 tuple(HO + np.array([-CHR + 1.0, 0.0, 0.0]))], [0.12, 0.6], arm_m, 16), "chamber")
_tg = sph("Target", tuple(HO), 0.25, gold_m, 24, 12, scale=(1, 1, 1.8))
put(_tg, "chamber")
# 192 beams: 48 quads of 4
CH_BEAM0, CH_BEAM1 = [], []
for d in PORTS:
    a, b = basis(d)
    for ox, oy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        off = (a * ox + b * oy) * 0.32
        CH_BEAM0.append(HO + d * (CHR - 1.0) + off)
        CH_BEAM1.append(HO + off * 0.04)
CH_BEAM0, CH_BEAM1 = np.array(CH_BEAM0), np.array(CH_BEAM1)
NCH = len(CH_BEAM0)
chb_m, CHB_A, CHB_E = beam_mat("ChamberBeam", UV, 8.0)
CHBEAM = Dyn("ChamberBeams", np.zeros((NCH * 14, 3)), tubes_faces(NCH, 6), chb_m, sets=("chamber",), smooth=False)
no_bounce([CHBEAM.o])
# port glow rings (beam on)
star_m, STAR_A, STAR_E = fade_emit_mat("Star", (1.0, 0.93, 0.78), 40.0)
STAR = put(sph("Star", tuple(HO), 1.0, star_m, 48, 24), "chamber")
cor_m, COR_A, COR_E = fade_emit_mat("Corona", (1.0, 0.55, 0.2), 6.0)
soften(cor_m)
COR = put(sph("Corona", tuple(HO), 1.0, cor_m, 48, 24), "chamber")
no_bounce([COR])
CH_STAR, _ch_star = point("ChStar", tuple(HO), 0.0, (1.0, 0.85, 0.65), 1.0, "chamber")
area("ChKey", tuple(HO + np.array([-20.0, -30.0, 25.0])), tuple(HO), 12000.0, 20.0, (0.7, 0.8, 1.0), "chamber")
area("ChFill", tuple(HO + np.array([25.0, 20.0, -20.0])), tuple(HO), 5000.0, 20.0, (0.6, 0.65, 0.9), "chamber")


def pose_chamber(t):
    p, inten = T.chamber_beams(t)
    CHBEAM.o.hide_render = inten < 0.01
    if inten >= 0.01:
        CHBEAM.set(tubes_verts(CH_BEAM0, CH_BEAM0 + (CH_BEAM1 - CH_BEAM0) * p, 0.09, 6))
        CHB_A.default_value = 0.85 * inten
        CHB_E.default_value = 10.0 * inten
    r, br = T.star(t)
    STAR.hide_render = br < 0.01
    COR.hide_render = br < 0.01
    STAR.scale = (r, r, r)
    COR.scale = (2.4 * r, 2.4 * r, 2.4 * r)
    STAR_A.default_value = min(1.0, br * 2)
    STAR_E.default_value = 45.0 * br
    COR_A.default_value = 0.5 * min(1.0, br * 2)
    COR_E.default_value = 5.0 * br
    _ch_star.energy = 3.0e5 * br


# ================================================================= set "sun": D + T -> He + n in front of the Sun
SO = np.array(T.SUN_O)
sun_m, _snt2, _sout2 = new_mat("SunSurface")
_stc = node(_snt2, "ShaderNodeTexCoord")
_snz = node(_snt2, "ShaderNodeTexNoise", Scale=0.045, Detail=8.0, Roughness=0.62)
link(_snt2, _stc.outputs["Object"], _snz.inputs["Vector"])
_svo = node(_snt2, "ShaderNodeTexVoronoi", Scale=0.12)
link(_snt2, _stc.outputs["Object"], _svo.inputs["Vector"])
_smix = math_node(_snt2, "ADD", math_node(_snt2, "MULTIPLY", _snz.outputs["Fac"], 0.7),
                  math_node(_snt2, "MULTIPLY", _svo.outputs["Distance"], 0.5))
_srp = ramp(_snt2, [(0.25, (0.35, 0.03, 0.0)), (0.5, (0.9, 0.22, 0.0)), (0.7, (1.0, 0.5, 0.08)),
                    (0.9, (1.0, 0.82, 0.45))])
link(_snt2, _smix, _srp.inputs[0])
_sem = node(_snt2, "ShaderNodeEmission", Strength=0.9)
link(_snt2, _srp.outputs[0], _sem.inputs["Color"])
link(_snt2, _sem.outputs[0], _sout2.inputs[0])
SUN_SPHERE = put(sph("Sun", tuple(SO + np.array(T.SUN_BODY)), T.SUN_RAD, sun_m, 128, 64), "sun")
proton_m = pmat("Proton", (0.85, 0.1, 0.07), rough=0.3, coat=0.6, bump=0.04, bump_scale=6.0)
neutron_m = pmat("Neutron", (0.55, 0.62, 0.72), rough=0.3, coat=0.6, bump=0.04, bump_scale=6.0)


def nucleus(name, layout, s):
    """layout: list of (kind, offset); returns a parent empty."""
    root = empty(name, (0, 0, 0))
    put(root, s)
    for i, (kind, off) in enumerate(layout):
        o = sph(f"{name}_{i}", tuple(off), 1.0, proton_m if kind == "p" else neutron_m, 32, 16)
        o.parent = root
        put(o, s)
    return root


D_NUC = nucleus("Deut", [("p", (-0.55, 0, 0)), ("n", (0.55, 0.1, 0.1))], "sun")
T_NUC = nucleus("Trit", [("p", (0, 0.6, 0)), ("n", (-0.55, -0.35, 0.1)), ("n", (0.55, -0.35, -0.1))], "sun")
HE_NUC = nucleus("Helium", [("p", (0.58, 0.58, 0.58)), ("p", (-0.58, -0.58, 0.58)), ("n", (-0.58, 0.58, -0.58)),
                            ("n", (0.58, -0.58, -0.58))], "sun")
N_OUT = put(sph("FreeNeutron", (0, 0, 0), 1.0, neutron_m, 32, 16), "sun")
fl_m, FLASH_A, FLASH_E = fade_emit_mat("FusionFlash", (1.0, 0.92, 0.75), 30.0)
soften(fl_m)
FUSE_FLASH = put(sph("FuseFlash", (0, 0, 0), 1.0, fl_m, 32, 16), "sun")
no_bounce([FUSE_FLASH])
SUN_KEY, _sun_key = point("SunKey", tuple(SO + np.array([0.0, 60.0, 30.0])), 4.0e5, (1.0, 0.75, 0.45), 8.0, "sun")
area("SunFill", tuple(SO + np.array([-12.0, -30.0, 10.0])), tuple(SO), 2500.0, 12.0, (0.7, 0.8, 1.0), "sun")
FUSE_L, _fuse_l = point("FuseLight", tuple(SO), 0.0, (1.0, 0.9, 0.7), 0.5, "sun")


def pose_sun(t):
    nu = T.sun_nuclei(t)
    a = nu["age"]
    spin = t * 1.7
    if a < 0:
        D_NUC.location = tuple(SO + np.array(nu["D"]))
        T_NUC.location = tuple(SO + np.array(nu["T"]))
        D_NUC.rotation_euler = (spin, 0.4 * spin, 0)
        T_NUC.rotation_euler = (-0.6 * spin, spin, 0.2)
    for o in (D_NUC, T_NUC):
        o.hide_render = a >= 0
        for ch in o.children:
            ch.hide_render = a >= 0
    HE_NUC.hide_render = a < 0
    for ch in HE_NUC.children:
        ch.hide_render = a < 0
    N_OUT.hide_render = a < 0
    if a >= 0:
        HE_NUC.location = tuple(SO + np.array(nu["He"]))
        HE_NUC.rotation_euler = (0.8 * spin, 1.2 * spin, 0)
        N_OUT.location = tuple(SO + np.array(nu["n"]))
    f = math.exp(-a / 0.25) if a >= 0 else 0.0
    FUSE_FLASH.hide_render = f < 0.01
    s = 1.5 + 5.0 * (1 - f)
    FUSE_FLASH.scale = (s, s, s)
    FUSE_FLASH.location = tuple(SO)
    FLASH_A.default_value = f
    FLASH_E.default_value = 40.0 * f
    _fuse_l.energy = 2.0e4 * f
    SUN_SPHERE.rotation_euler = (0, 0, 0.03 * t)


# ================================================================= set "drop": seawater with deuterium inside
DO = np.array(T.DROP_O)
DROP_R = 8.0
_dv, _df = icosphere(5)
DROP_D = _dv
drop_m, _dpb = glass_mat("Seawater", (0.8, 0.93, 1.0), ior=1.333, rough=0.0)
DROP = Dyn("Drop", DO + _dv * DROP_R, _df, drop_m, sets=("drop",))
DROP.o.visible_shadow = False
DROP_N = Noise(21, octaves=((2.0, 1.0), (3.0, 0.5)))
deu2 = nucleus("Deut2", [("p", (-0.55, 0, 0)), ("n", (0.55, 0.1, 0.1))], "drop")
deu2.scale = (1.5, 1.5, 1.5)
dg_m, DG_A, DG_E = fade_emit_mat("DeutGlow", (0.45, 0.8, 1.0), 6.0)
soften(dg_m)
DGLOW = put(sph("DeutGlow", tuple(DO), 1.0, dg_m, 32, 16), "drop")
# water molecules inside the drop (O red-white + 2 H)
_bw = Builder()
_g = np.random.default_rng(31)
for k in range(12):
    p = rand_dirs(1, _g)[0] * _g.uniform(2.5, 6.2)
    if np.linalg.norm(p[:2]) < 2.3 and abs(p[2]) < 2.3:
        continue
    ax = rand_dirs(1, _g)[0]
    a, b = basis(ax)
    _bw.sphere(tuple(DO + p), (0.55, 0.55, 0.55))
    for s in (1, -1):
        _bw.sphere(tuple(DO + p + (a * math.cos(0.91) * s + b * math.sin(0.91)) * 0.6), (0.33, 0.33, 0.33))
water_mol_m = pmat("WaterMol", (0.85, 0.9, 0.98), rough=0.25, coat=0.4, bump=0.0)
put(_bw.build("WaterMols", water_mol_m), "drop")
# backdrop: deep ocean-blue gradient behind the drop (so the refraction reads)
bd_m, _bnt, _bout = new_mat("Backdrop")
_btc = node(_bnt, "ShaderNodeTexCoord")
_bsep = _bnt.nodes.new("ShaderNodeSeparateXYZ")
link(_bnt, _btc.outputs["Generated"], _bsep.inputs[0])
_brp = ramp(_bnt, [(0.0, (0.0, 0.03, 0.08)), (0.5, (0.0, 0.12, 0.25)), (0.8, (0.05, 0.35, 0.55)),
                   (1.0, (0.3, 0.7, 0.9))])
link(_bnt, _bsep.outputs["Z"], _brp.inputs[0])
_bem = node(_bnt, "ShaderNodeEmission", Strength=1.0)
link(_bnt, _brp.outputs[0], _bem.inputs["Color"])
link(_bnt, _bem.outputs[0], _bout.inputs[0])
_bdv = [(-80, 30, -60), (80, 30, -60), (80, 30, 60), (-80, 30, 60)]
put(obj_from("Backdrop", [tuple(DO + np.array(v)) for v in _bdv], [[0, 1, 2, 3]], bd_m, smooth=False), "drop")
area("DropKey", tuple(DO + np.array([-25.0, -30.0, 30.0])), tuple(DO), 60000.0, 15.0, (1.0, 0.97, 0.92), "drop")
area("DropRim", tuple(DO + np.array([25.0, 10.0, 15.0])), tuple(DO), 30000.0, 10.0, (0.6, 0.85, 1.0), "drop")


def pose_drop(t):
    w = DROP_N(DROP_D + 0.0) * 0.0
    ph = t * 3.1
    rad = DROP_R * (1 + 0.035 * np.sin(3 * DROP_D[:, 0] + ph) * np.cos(2 * DROP_D[:, 2] + 0.7 * ph)
                    + 0.02 * np.sin(4 * DROP_D[:, 1] - 1.3 * ph)) + w
    DROP.set(DO + DROP_D * rad[:, None])
    deu2.location = tuple(DO + np.array([0.0, -1.0, 0.3 * math.sin(t * 2.0)]))
    deu2.rotation_euler = (t * 1.1, t * 0.7, 0)
    g = T.deut_glow(t)
    DGLOW.hide_render = g < 0.01
    s = 2.6 + 0.6 * g
    DGLOW.scale = (s, s, s)
    DGLOW.location = deu2.location
    DG_A.default_value = 0.6 * g
    DG_E.default_value = 4.0 * g


# ================================================================= set "pepper": capsule next to a peppercorn (mm)
PO = np.array(T.PEP_O)
table_m, _tp = principled("Table", (0.04, 0.045, 0.055), rough=0.32, bump=0.05, bump_scale=3.0)
put(obj_from("Table", [tuple(PO + np.array(v)) for v in [(-60, -60, 0), (60, -60, 0), (60, 60, 0), (-60, 60, 0)]],
             [[0, 1, 2, 3]], table_m, smooth=False), "pepper")
_pv, _pf = icosphere(5)
PN = Noise(41, octaves=((5.0, 1.0), (9.0, 0.6), (17.0, 0.35), (30.0, 0.15)), n=10)(_pv)
PN2 = Noise(42, octaves=((60.0, 0.1),), n=10)(_pv)
pepper_r = 2.5 * (1 + 0.045 * np.abs(PN) * -1.0 + 0.018 * PN + 0.004 * PN2)
pep_m, _pmp = principled("Peppercorn", (0.06, 0.035, 0.022), rough=0.55, bump=0.35, bump_scale=9.0)
put(obj_from("Peppercorn", PO + _pv * pepper_r[:, None] + np.array([2.4, 0.0, 2.45]), _pf, pep_m), "pepper")
cap2_m, _c2 = glass_mat("Capsule2", (0.85, 0.87, 0.9), ior=2.4, rough=0.08)
put(sph("Capsule2", tuple(PO + np.array([-1.4, 0.0, 1.0])), 1.0, cap2_m, 64, 32), "pepper")
put(sph("Capsule2In", tuple(PO + np.array([-1.4, 0.0, 1.0])), 0.9, fuel_m, 48, 24), "pepper")
area("PepKey", tuple(PO + np.array([-12.0, -14.0, 16.0])), tuple(PO + np.array([0.5, 0, 1.5])), 2600.0, 10.0,
     (1.0, 0.96, 0.9), "pepper")
area("PepRim", tuple(PO + np.array([10.0, 16.0, 8.0])), tuple(PO + np.array([0.5, 0, 1.5])), 2200.0, 8.0,
     (0.7, 0.8, 1.0), "pepper")


# ================================================================= pose everything
ALL_SETS = list(SETS)


def pose(t):
    s = T.SET_OF[T.shot_index(t)]
    for k, objs in SETS.items():
        for o in objs:
            if k != s:
                o.hide_render = True
    for o in SETS[s]:
        o.hide_render = False
    WSTAR.default_value = (0.9, 0.9, 0.9, 1) if s == "sun" else (0.0, 0.0, 0.0, 1)
    if s == "cap":
        pose_cap(t)
    elif s == "chamber":
        pose_chamber(t)
    elif s == "sun":
        pose_sun(t)
    elif s == "drop":
        pose_drop(t)


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

SPP = 12   # 12 is visually identical to 24 after OIDN here (checked frames 30, 75)
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
