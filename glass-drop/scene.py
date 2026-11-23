"""Blender scene for "This Glass Drop Just Exploded" (Cycles, posed per frame).

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
SETS = {"drop": [], "water": [], "section": [], "hammer": []}
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


# ================================================================= world: a dark polariscope
world = bpy.data.worlds.new("Studio")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
for n_ in list(wnt.nodes):
    if n_.type != "OUTPUT_WORLD":
        wnt.nodes.remove(n_)
wtc = wnt.nodes.new("ShaderNodeTexCoord")
wsep = wnt.nodes.new("ShaderNodeSeparateXYZ")
wnt.links.new(wtc.outputs["Generated"], wsep.inputs[0])
wr = ramp(wnt, [(0.0, (0.002, 0.002, 0.003)), (0.5, (0.005, 0.005, 0.009)), (1.0, (0.014, 0.016, 0.030))])
wnt.links.new(wsep.outputs["Z"], wr.inputs[0])
wbg = wnt.nodes.new("ShaderNodeBackground")
WORLD_S = wbg.inputs["Strength"]
wnt.links.new(wr.outputs[0], wbg.inputs["Color"])
wnt.links.new(wbg.outputs[0], wnt.nodes["World Output"].inputs[0])


# ================================================================= the drop geometry
ZS_PROF = np.concatenate([np.linspace(-1.0, 0.0, 26)[:-1], np.linspace(0.0, 1.6, 26)[:-1],
                          np.linspace(1.6, T.Z_TOP, 50)])


def drop_vf(seg=72, a0=0.0, a1=2 * math.pi, closed=True, scale=1.0):
    verts, faces = [], []
    n_a = seg if closed else seg + 1
    zs = ZS_PROF
    for z in zs:
        r = T.radius(z)
        cx = T.bend(z)
        for k in range(n_a):
            a = a0 + (a1 - a0) * k / seg
            verts.append(((cx + r * math.cos(a)) * scale, r * math.sin(a) * scale, z * scale))
    for i in range(len(zs) - 1):
        for k in range(seg):
            k1 = (k + 1) % n_a
            faces.append([i * n_a + k, i * n_a + k1, (i + 1) * n_a + k1, (i + 1) * n_a + k])
    verts.append((T.bend(T.Z_TOP) * scale, 0.0, (T.Z_TOP + 0.03) * scale))   # tail tip cap
    c = len(verts) - 1
    i = len(zs) - 1
    for k in range(seg):
        faces.append([i * n_a + k, i * n_a + (k + 1) % n_a, c])
    return verts, faces


RAINBOW = [(0.00, (0.45, 0.0, 1.0)), (0.12, (0.0, 0.15, 1.0)), (0.24, (0.0, 0.8, 1.0)), (0.36, (0.0, 1.0, 0.2)),
           (0.48, (1.0, 0.85, 0.0)), (0.60, (1.0, 0.25, 0.0)), (0.72, (1.0, 0.0, 0.3)), (0.80, (0.02, 0.0, 0.04)),
           (0.92, (0.02, 0.0, 0.04)), (1.00, (0.45, 0.0, 1.0))]


def glass_mat(name, rb_strength, with_front=False):
    """Clear glass with photoelastic rainbow fringes (emission); optionally the crack front / powder cut."""
    m, nt, out = new_mat(name)
    tc = node(nt, "ShaderNodeTexCoord")
    sep = node(nt, "ShaderNodeSeparateXYZ")
    link(nt, tc.outputs["Object"], sep.inputs[0])
    zc = sep.outputs["Z"]
    gl = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.0, IOR=1.52)
    gl.inputs["Transmission Weight"].default_value = 1.0
    gl.inputs["Base Color"].default_value = (1, 1, 1, 1)
    lw = node(nt, "ShaderNodeLayerWeight", Blend=0.5)
    # fringe order: grows toward the silhouette and toward the head (where the stress is)
    fr = math_node(nt, "MULTIPLY", lw.outputs["Facing"], 2.6)
    fz = math_node(nt, "MULTIPLY", zc, -0.42)
    fs = math_node(nt, "ADD", fr, fz)
    fs = math_node(nt, "ADD", fs, 0.35)
    ff = math_node(nt, "FRACT", fs)
    rr = ramp(nt, RAINBOW)
    link(nt, ff, rr.inputs[0])
    em = node(nt, "ShaderNodeEmission")
    link(nt, rr.outputs[0], em.inputs["Color"])
    rbs = value(nt, rb_strength)
    w = math_node(nt, "POWER", lw.outputs["Facing"], 1.3)
    w = math_node(nt, "MULTIPLY", w, 0.8)
    w = math_node(nt, "ADD", w, 0.2)
    link(nt, math_node(nt, "MULTIPLY", w, rbs), em.inputs["Strength"])
    # red warning glow on the thin tail
    tg = value(nt, 0.0)
    tm = math_node(nt, "SUBTRACT", zc, 2.6)
    tm = math_node(nt, "MULTIPLY", tm, 0.8, clamp=True)
    tgs = math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", tm, tg), 40.0)
    tem = node(nt, "ShaderNodeEmission", Color=(1.0, 0.04, 0.02, 1))
    link(nt, tgs, tem.inputs["Strength"])
    add1 = node(nt, "ShaderNodeAddShader")
    link(nt, gl.outputs[0], add1.inputs[0])
    link(nt, em.outputs[0], add1.inputs[1])
    add2 = node(nt, "ShaderNodeAddShader")
    link(nt, add1.outputs[0], add2.inputs[0])
    link(nt, tem.outputs[0], add2.inputs[1])
    res = {"rb": rbs, "tail": tg}
    if not with_front:
        link(nt, add2.outputs[0], out.inputs[0])
        return m, res
    F = value(nt, 99.0)
    d = math_node(nt, "SUBTRACT", zc, F)
    below_snip = math_node(nt, "LESS_THAN", zc, T.Z_SNIP)
    cracked = math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", d, 0.0), below_snip)
    gone = math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", d, 0.13), below_snip)
    # crack network: a white, glowing web in the band just behind the front
    vo = node(nt, "ShaderNodeTexVoronoi", Scale=9.0)
    vo.feature = "DISTANCE_TO_EDGE"
    link(nt, tc.outputs["Object"], vo.inputs["Vector"])
    web = math_node(nt, "LESS_THAN", vo.outputs["Distance"], 0.06)
    cem = node(nt, "ShaderNodeEmission", Color=(0.85, 0.93, 1.0, 1))
    link(nt, math_node(nt, "ADD", math_node(nt, "MULTIPLY", web, 14.0), 0.35), cem.inputs["Strength"])
    cadd = node(nt, "ShaderNodeAddShader")
    link(nt, add2.outputs[0], cadd.inputs[0])
    link(nt, cem.outputs[0], cadd.inputs[1])
    mx1 = node(nt, "ShaderNodeMixShader")
    link(nt, cracked, mx1.inputs[0])
    link(nt, add2.outputs[0], mx1.inputs[1])
    link(nt, cadd.outputs[0], mx1.inputs[2])
    tr = node(nt, "ShaderNodeBsdfTransparent")
    mx2 = node(nt, "ShaderNodeMixShader")
    link(nt, gone, mx2.inputs[0])
    link(nt, mx1.outputs[0], mx2.inputs[1])
    link(nt, tr.outputs[0], mx2.inputs[2])
    link(nt, mx2.outputs[0], out.inputs[0])
    res["front"] = F
    return m, res


drop_m, DROP_K = glass_mat("DropGlass", 1.5, with_front=True)
DV, DF = drop_vf()
DROP = obj_from("Drop", DV, DF, drop_m)
to_set("drop", DROP)

metal_m, _ = principled("Steel", (0.42, 0.43, 0.46), rough=0.28)
_.inputs["Metallic"].default_value = 1.0
dark_metal_m, _p = principled("DarkSteel", (0.16, 0.17, 0.19), rough=0.32)
_p.inputs["Metallic"].default_value = 1.0
grip_m, _ = principled("Grip", (0.8, 0.05, 0.03), rough=0.4, coat=0.5)

# clamp holding the tail tip
tx = T.bend(T.Z_TOP)
to_set("drop", box("ClampJaw", (tx - 0.28, -0.22, T.Z_TOP - 0.25), (tx + 0.28, 0.22, T.Z_TOP + 0.35), dark_metal_m),
       tube("ClampRod", [(tx, 0, T.Z_TOP + 0.3), (tx, 0, T.Z_TOP + 9.0)], [0.12, 0.12], metal_m, seg=16))

# side cutters: two jaws on a pivot right of the tail, handles running out of frame
CUT_PIVOT = V((1.9, 0.0, T.Z_SNIP))
CUTTER = empty("Cutter", CUT_PIVOT)
to_set("drop", CUTTER)
JAWS = []
for sgn in (1, -1):
    jp = empty(f"JawPivot{sgn}", (0, 0, 0), CUTTER)
    jv, jf = box_vf(-1.95, 0.0, -0.09, 0.09, 0.0, 0.34)
    jv = [(x, y, (z * (0.25 + 0.75 * (x + 1.95) / 1.95)) * sgn) for x, y, z in jv]   # tapered to a sharp edge
    jaw = obj_from(f"Jaw{sgn}", jv, jf, metal_m, smooth=False)
    jaw.parent = jp
    hv, hf = box_vf(0.0, 7.0, -0.13, 0.13, 0.05, 0.42)
    hv = [(x, y, (z + 0.02 * x) * sgn) for x, y, z in hv]
    hd = obj_from(f"Handle{sgn}", hv, hf, grip_m, smooth=False)
    hd.parent = jp
    to_set("drop", jp, jaw, hd)
    JAWS.append((jp, sgn))
to_set("drop", sph("CutterBolt", (0, 0, 0), 0.2, metal_m, scale=(1, 0.8, 1)))
bpy.data.objects["CutterBolt"].parent = CUTTER

# backdrop of the polariscope: a deep blue glow far behind (refracted through the glass)
bd_m, nt_bd, out_bd = new_mat("Backdrop")
_tc = node(nt_bd, "ShaderNodeTexCoord")
_gr = node(nt_bd, "ShaderNodeTexGradient")
_gr.gradient_type = "SPHERICAL"
_mp = node(nt_bd, "ShaderNodeMapping", Scale=(0.11, 1.0, 0.075))
link(nt_bd, _tc.outputs["Object"], _mp.inputs["Vector"])
link(nt_bd, _mp.outputs[0], _gr.inputs["Vector"])
_r = ramp(nt_bd, [(0.0, (0.0, 0.0, 0.0)), (0.6, (0.02, 0.05, 0.16)), (1.0, (0.08, 0.18, 0.55))])
link(nt_bd, _gr.outputs[0], _r.inputs[0])
_em = node(nt_bd, "ShaderNodeEmission", Strength=0.4)
link(nt_bd, _r.outputs[0], _em.inputs["Color"])
link(nt_bd, _em.outputs[0], out_bd.inputs[0])
BACK = obj_from("Backdrop", [(-14, 14, -12), (14, 14, -12), (14, 14, 22), (-14, 14, 22)], [[0, 1, 2, 3]], bd_m)
BACK.location = (0, 0, 0)
# put the glow centre behind the head
BACK.data.transform(Matrix.Translation((0, 0, -3)))
BACK.location = (0, 0, 3)
to_set("drop", BACK)

# lights: two hard white rims behind, a soft key, and a cold point light riding the crack front
area("RimL", (-4.5, 5.0, 2.5), (0, 0, 1.5), 700, 2.5, (0.9, 0.95, 1.0), "drop")
area("RimR", (4.5, 5.0, 4.0), (0, 0, 2.5), 700, 2.5, (1.0, 0.95, 0.9), "drop")
area("KeyD", (-3.0, -6.0, 5.0), (0, 0, 2.0), 140, 4.0, (1.0, 1.0, 1.0), "drop")
area("CutKey", (4.0, -4.0, 9.5), (1.5, 0, 6.0), 300, 3.0, (1.0, 0.97, 0.92), "drop")
area("CutRim", (3.0, 4.0, 3.5), (1.5, 0, 6.0), 250, 2.0, (0.8, 0.9, 1.0), "drop")
fl = bpy.data.lights.new("FrontLight", "POINT")
fl.color = (0.75, 0.88, 1.0)
fl.shadow_soft_size = 0.2
FRONT_L = bpy.data.objects.new("FrontLight", fl)
col.objects.link(FRONT_L)
to_set("drop", FRONT_L)

# ---------------------------------------------------------------- the powder (glass shards)
NSH = 6500
zs_pool = np.linspace(-1.0, T.Z_SNIP - 0.02, 4000)
wts = np.array([T.radius(z) ** 2 + 0.012 for z in zs_pool])
wts /= wts.sum()
SH_Z = rng.choice(zs_pool, NSH, p=wts) + rng.uniform(-0.01, 0.01, NSH)
SH_R = np.array([T.radius(z) for z in SH_Z])
SH_TH = rng.uniform(0, 2 * np.pi, NSH)
SH_RHO = SH_R * np.sqrt(rng.uniform(0.0, 1.0, NSH)) * 0.95
SH_P0 = np.stack([np.array([T.bend(z) for z in SH_Z]) + SH_RHO * np.cos(SH_TH), SH_RHO * np.sin(SH_TH), SH_Z], 1)
SH_TR = np.array([T.front_time(z) for z in SH_Z]) + rng.uniform(0.0, 0.05, NSH)
_rad = np.stack([np.cos(SH_TH), np.sin(SH_TH), np.zeros(NSH)], 1)
SH_V = _rad * (rng.uniform(0.7, 2.6, NSH) * (0.35 + 0.9 * SH_R))[:, None] + rng.normal(0, 0.35, (NSH, 3))
SH_V[:, 1] -= 0.5 * np.abs(rng.normal(0, 0.6, NSH))        # a bit more spray toward the camera
SH_S = (0.012 + 0.032 * rng.uniform(0, 1, NSH) ** 2) * (0.6 + 0.7 * SH_R)
SH_AX = rng.normal(0, 1, (NSH, 3))
SH_AX /= np.linalg.norm(SH_AX, axis=1, keepdims=True)
SH_SPIN = rng.uniform(4, 16, NSH)
TET = np.array([(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)], float) / math.sqrt(3)
SH_BASE = TET[None, :, :] * rng.uniform(0.5, 1.5, (NSH, 4, 1))      # irregular chips
tet_f = [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]]
sh_faces = [[i + 4 * k for i in f] for k in range(NSH) for f in tet_f]
sh_m, nt_sh, out_sh = new_mat("Shard")
_at = nt_sh.nodes.new("ShaderNodeAttribute")
_at.attribute_name = "col"
_ps = node(nt_sh, "ShaderNodeBsdfPrincipled", Roughness=0.08)
_ps.inputs["Base Color"].default_value = (0.9, 0.95, 1.0, 1)
_ps.inputs["Transmission Weight"].default_value = 0.6
link(nt_sh, _at.outputs["Color"], _ps.inputs["Emission Color"])
SH_EM = _ps.inputs["Emission Strength"]
SH_EM.default_value = 1.1
link(nt_sh, _ps.outputs[0], out_sh.inputs[0])
SHARDS = Dyn("Powder", np.zeros((NSH * 4, 3)), sh_faces, sh_m, sets=("drop",), smooth=False)
_ca = SHARDS.o.data.color_attributes.new("col", "FLOAT_COLOR", "POINT")
_hue = rng.uniform(0, 1, NSH)
_cols = []
for hh in _hue:
    if hh < 0.25:
        c = (0.85, 0.92, 1.0)                                   # most of the powder: white glitter
    else:
        u = (hh - 0.25) / 0.75 * 0.72
        for (a0, c0), (a1, c1) in zip(RAINBOW, RAINBOW[1:]):
            if a0 <= u <= a1:
                f = (u - a0) / (a1 - a0)
                c = tuple(p + (q - p) * f for p, q in zip(c0, c1))
                break
    _cols += [(*c, 1.0)] * 4
_ca.data.foreach_set("color", np.array(_cols, np.float32).reshape(-1))


def shards_pose(te):
    age = te - SH_TR
    live = age > 0
    a = np.clip(age, 0, None)
    tau = 0.65
    disp = SH_V * (tau * (1 - np.exp(-a / tau)))[:, None]
    disp[:, 2] -= 0.04 * a ** 2
    pos = SH_P0 + disp
    shrink = np.clip(1 - (a - 1.6) / 1.2, 0, 1)
    pop = np.clip(a / 0.05, 0, 1)
    s = SH_S * live * shrink * pop
    ang = SH_SPIN * a
    k = SH_AX
    c, sn = np.cos(ang)[:, None, None], np.sin(ang)[:, None, None]
    v = SH_BASE
    kk = k[:, None, :]
    rot = v * c + np.cross(kk, v) * sn + kk * (np.sum(kk * v, axis=2, keepdims=True)) * (1 - c)
    verts = pos[:, None, :] + rot * s[:, None, None]
    SHARDS.set(verts)


# ================================================================= water set: molten glass drips into cold water
WX, WY, WZ = T.WATER
table_m, _ = principled("Table", (0.03, 0.03, 0.035), rough=0.6)
to_set("water", obj_from("Table", [(WX - 40, WY - 40, 0), (WX + 40, WY - 40, 0), (WX + 40, WY + 40, 0), (WX - 40, WY + 40, 0)],
                         [[0, 1, 2, 3]], table_m))
bk_m, bkp = principled("BeakerGlass", (1, 1, 1), rough=0.02)
bkp.inputs["Transmission Weight"].default_value = 1.0
bkp.inputs["IOR"].default_value = 1.5
BEAKER = lathe("Beaker", [(0.0, 0.0), (2.3, 0.0), (2.32, 0.05), (2.32, 6.2), (2.36, 6.3), (2.22, 6.3), (2.2, 6.2),
                          (2.2, 0.18), (0.0, 0.18)], bk_m, seg=96)
BEAKER.location = (WX, WY, 0)
wt_m, wtp = principled("Water", (0.82, 0.93, 1.0), rough=0.0)
wtp.inputs["Transmission Weight"].default_value = 1.0
wtp.inputs["IOR"].default_value = 1.33
WATER_O = lathe("WaterBody", [(0.0, 0.18), (2.19, 0.18), (2.19, 4.4), (0.0, 4.4)], wt_m, seg=96, smooth=False)
WATER_O.location = (WX, WY, 0)
to_set("water", BEAKER, WATER_O)
# backlight softbox behind the beaker (cool blue), floor kick
wbd_m = bd_m.copy()
wbd_m.name = "WaterBackdrop"
wbd_m.node_tree.nodes["Mapping"].inputs["Scale"].default_value = (0.085, 1.0, 0.085)
wbd_m.node_tree.nodes["Emission"].inputs["Strength"].default_value = 2.2
WBACK = obj_from("WaterBack", [(-16, 0, -12), (16, 0, -12), (16, 0, 16), (-16, 0, 16)], [[0, 1, 2, 3]], wbd_m)
WBACK.location = (WX, 10, 4.0)
WBACK.scale = (0.8, 1, 0.8)
to_set("water", WBACK)
area("WKey", (WX - 5, -6, 9), (WX, 0, 3), 260, 4.0, (1.0, 0.98, 0.95), "water")
area("WRim", (WX + 5, 4, 7), (WX, 0, 4), 500, 2.0, (0.8, 0.9, 1.0), "water")
# the molten gob (same drop shape, smaller), glowing orange, cooling in the water
hot_m, nt_h, out_h = new_mat("HotGlass")
_hg = node(nt_h, "ShaderNodeBsdfPrincipled", Roughness=0.05, IOR=1.52)
_hg.inputs["Transmission Weight"].default_value = 1.0
HEAT_V = value(nt_h, 1.0)
_hr = ramp(nt_h, [(0.0, (0.6, 0.01, 0.0)), (0.5, (1.0, 0.1, 0.0)), (1.0, (1.0, 0.36, 0.02))])
link(nt_h, HEAT_V, _hr.inputs[0])
_lw = node(nt_h, "ShaderNodeLayerWeight", Blend=0.35)
_hem = node(nt_h, "ShaderNodeEmission")
link(nt_h, _hr.outputs[0], _hem.inputs["Color"])
_hs = math_node(nt_h, "POWER", HEAT_V, 2.0)
_hs = math_node(nt_h, "MULTIPLY", _hs, 1.5)
_hs = math_node(nt_h, "MULTIPLY", _hs, math_node(nt_h, "SUBTRACT", 1.15, _lw.outputs["Facing"]))
link(nt_h, _hs, _hem.inputs["Strength"])
_ha = node(nt_h, "ShaderNodeMixShader")
link(nt_h, math_node(nt_h, "MULTIPLY", HEAT_V, 1.25, clamp=True), _ha.inputs[0])
link(nt_h, _hg.outputs[0], _ha.inputs[1])
link(nt_h, _hem.outputs[0], _ha.inputs[2])
link(nt_h, _ha.outputs[0], out_h.inputs[0])
GS = 0.55
gv, gf = drop_vf(seg=48, scale=GS)
GOB = obj_from("Gob", gv, gf, hot_m)
to_set("water", GOB)
gl_ = bpy.data.lights.new("GobLight", "POINT")
gl_.color = (1.0, 0.45, 0.12)
gl_.shadow_soft_size = 0.5
GOB_L = bpy.data.objects.new("GobLight", gl_)
GOB_L.visible_glossy = False
GOB_L.visible_transmission = False
col.objects.link(GOB_L)
to_set("water", GOB_L)
# steam bubbles rising off the hot glass
NB = 90
bub_m, bubp = principled("Bubble", (1, 1, 1), rough=0.0)
bubp.inputs["Transmission Weight"].default_value = 1.0
bubp.inputs["IOR"].default_value = 0.76
BV, BF = sphere_vf(10, 6)
BUBBLES = Dyn("Bubbles", np.zeros((NB * len(BV), 3)), [[i + k * len(BV) for i in f] for k in range(NB) for f in BF],
              bub_m, sets=("water",))
B_T0 = rng.uniform(0.0, 2.6, NB)
B_R = rng.uniform(0.04, 0.13, NB)
B_PH = rng.uniform(0, 2 * np.pi, NB)
B_ZOFF = rng.uniform(-0.4, 3.0, NB)                     # along the gob (head and tail)
B_SP = rng.uniform(1.4, 2.6, NB)
# ripple ring on the water surface where the gob went in
rp_m, RP_A, _rps = fade_emit_mat("Ripple", (0.75, 0.88, 1.0), 2.0)
RIPPLE = lathe("Ripple", [(0.92, 4.41), (1.0, 4.43), (1.08, 4.41)], rp_m, seg=64)
to_set("water", RIPPLE)


def pose_water(t):
    z = T.drip_z(t)
    h = T.glass_heat(t)
    GOB.location = (WX, WY, z)
    GOB.rotation_euler = (0, 0, 0.6 * math.sin(t * 1.3))
    HEAT_V.default_value = h
    GOB_L.location = (WX, WY - 0.9, z + 0.3)
    GOB_L.data.energy = 120 * h ** 2
    age = t - T.T_WATER
    vv = []
    for k in range(NB):
        a = age - B_T0[k] * (0.6 if k % 3 else 0.25)
        zb = z + B_ZOFF[k] * GS + max(a, 0) * B_SP[k]
        live = a > 0 and zb < 4.35 and h > 0.3
        r = B_R[k] * (1.0 if live else 0.0) * min(1.0, max(a, 0) / 0.08)
        x = WX + 0.25 * math.sin(B_PH[k] + 7 * a) + 0.18 * math.cos(B_PH[k] * 3) + T.bend(B_ZOFF[k]) * GS
        y = WY + 0.25 * math.cos(B_PH[k] + 5 * a) + 0.18 * math.sin(B_PH[k] * 2)
        vv.append(BV * r + (x, y, zb))
    BUBBLES.set(np.concatenate(vv))
    s = 0.2 + 2.2 * T.clamp(age / 1.4) ** 0.6 if age > 0 else 0.01
    RIPPLE.scale = (s, s, 1)
    RIPPLE.location = (WX, WY, 0)
    RP_A.default_value = 0.0 if age < 0 else 0.6 * math.exp(-age / 0.7)


# ================================================================= section set: the drop cut in half
SX, SY, SZ = T.SECTION
sec_glass_m, SEC_K = glass_mat("SectionGlass", 0.9)
hv_, hf_ = drop_vf(seg=48, a0=0.0, a1=math.pi, closed=False)
SEC_SHELL = obj_from("SectionShell", hv_, hf_, sec_glass_m)
SEC_SHELL.location = (SX, SY, SZ)
# cut face (y = 0), with each vertex knowing how far it is toward the surface (rel = 0 centre, 1 surface)
NXC = 41
fv, ff, rel = [], [], []
for i, z in enumerate(ZS_PROF):
    r = T.radius(z)
    cx = T.bend(z)
    for j in range(NXC):
        u = -1 + 2 * j / (NXC - 1)
        fv.append((cx + r * u, 0.0, z))
        rel.append(abs(u))
for i in range(len(ZS_PROF) - 1):
    for j in range(NXC - 1):
        a = i * NXC + j
        ff.append([a, a + NXC, a + NXC + 1, a + 1])
sec_m, nt_s, out_s = new_mat("SectionFace")
_ra = nt_s.nodes.new("ShaderNodeAttribute")
_ra.attribute_name = "rel"
SKIN_V = value(nt_s, 0.0)
_thr = math_node(nt_s, "SUBTRACT", 1.0, SKIN_V)
_e = math_node(nt_s, "SUBTRACT", _ra.outputs["Fac"], _thr)
_e = math_node(nt_s, "MULTIPLY", _e, 40.0, clamp=True)
_mix = nt_s.nodes.new("ShaderNodeMix")
_mix.data_type = "RGBA"
link(nt_s, _e, _mix.inputs["Factor"])
_mix.inputs[6].default_value = (1.0, 0.22, 0.03, 1)                 # hot, pulled inside
_mix.inputs[7].default_value = (0.05, 0.45, 1.0, 1)                 # cool, squeezing skin
_sp = node(nt_s, "ShaderNodeBsdfPrincipled", Roughness=0.35)
link(nt_s, _mix.outputs[2], _sp.inputs["Base Color"])
link(nt_s, _mix.outputs[2], _sp.inputs["Emission Color"])
# the hot inside glows a little brighter toward the centre
_glow = math_node(nt_s, "SUBTRACT", 1.6, _ra.outputs["Fac"])
link(nt_s, math_node(nt_s, "MULTIPLY", _glow, 1.5), _sp.inputs["Emission Strength"])
link(nt_s, _sp.outputs[0], out_s.inputs[0])
SEC_FACE = obj_from("SectionFace", fv, ff, sec_m, smooth=False)
_rl = SEC_FACE.data.attributes.new("rel", "FLOAT", "POINT")
_rl.data.foreach_set("value", np.array(rel, np.float32))
SEC_FACE.location = (SX, SY - 0.003, SZ)
to_set("section", SEC_SHELL, SEC_FACE)
# squeeze arrows around the outline, pointing in
ar_m, AR_S = emit_mat("Arrow", (0.05, 0.45, 1.0), 3.0)
ARR_Z = [-0.8, -0.45, 0.0, 0.45, 0.9, 1.5, 2.2, 3.1]
ARROWS = []
for z in ARR_Z:
    for side in (-1, 1):
        if z <= -0.95:
            continue
        r = T.radius(z)
        dz = (T.radius(z + 0.01) - T.radius(z - 0.01)) / 0.02
        n = V((side * 1.0, 0.0, -dz)).normalized()             # outward normal of the outline (x, z)
        if z < 0:
            n = V((side * math.sqrt(max(0.0, 1 - z * z)), 0.0, z)).normalized()
        p = V((T.bend(z) + side * r, -0.03, z))
        ARROWS.append((p, n, 0.32 + 0.35 * min(r, 1.0)))
ARR_V, ARR_F = [], []
for p, n, L in ARROWS:
    base = len(ARR_V)
    tang = V((-n.z, 0, n.x))
    tip = p + n * 0.06
    w = 0.11 * L / 0.67
    pts = [tip, tip + n * L * 0.45 + tang * w, tip + n * L * 0.45 + tang * w * 0.45, tip + n * L + tang * w * 0.45,
           tip + n * L - tang * w * 0.45, tip + n * L * 0.45 - tang * w * 0.45, tip + n * L * 0.45 - tang * w]
    ARR_V += [q[:] for q in pts]
    ARR_F.append(list(range(base, base + 7)))
ARR_V = np.array(ARR_V)
ARR_DIR = np.repeat(np.array([[n.x, n.y, n.z] for _, n, _ in ARROWS]), 7, axis=0)
ARR_TIP = np.repeat(np.array([(p + n * 0.06)[:] for p, n, _ in ARROWS]), 7, axis=0)
ARR = Dyn("Arrows", ARR_V + np.array(T.SECTION), ARR_F, ar_m, sets=("section",), smooth=False)
area("SKey", (SX - 4, -7, 5), (SX, 0, 1.5), 260, 5.0, (1.0, 1.0, 1.0), "section")
area("SRimL", (SX - 4, 4, 2), (SX, 0, 1), 400, 2.5, (0.85, 0.92, 1.0), "section")
area("SRimR", (SX + 4, 4, 4), (SX, 0, 2), 400, 2.5, (1.0, 0.92, 0.85), "section")
sb = obj_from("SecBack", [(SX - 14, 14, -12), (SX + 14, 14, -12), (SX + 14, 14, 22), (SX - 14, 14, 22)], [[0, 1, 2, 3]], bd_m)
to_set("section", sb)


def pose_section(t):
    SKIN_V.default_value = T.skin(t)
    appear, pulse = T.squeeze(t)
    off = (0.05 + 0.13 * pulse) * appear
    s = appear
    v = ARR_TIP + (ARR_V - ARR_TIP) * max(s, 1e-4) + ARR_DIR * off - ARR_DIR * (1 - s) * 0.0
    ARR.set(v + np.array(T.SECTION))
    AR_S.default_value = 3.0 * appear


# ================================================================= hammer set
HX, HY, HZ = T.HAMMER
anv_m, _ap = principled("Anvil", (0.05, 0.055, 0.06), rough=0.55)
_ap.inputs["Metallic"].default_value = 1.0
anv = box("Anvil", (HX - 9, -3.0, -2.0), (HX + 9, 3.0, 0.0), anv_m)
to_set("hammer", anv)
ham_glass_m, HAM_K = glass_mat("HammerGlass", 1.6)
HDROP = obj_from("HammerDrop", DV, DF, ham_glass_m)
HDROP.location = (HX, HY, 1.0)
HDROP.rotation_euler = (0, math.radians(-94.8), 0)
HDROP.scale = (-1, 1, 1)
to_set("hammer", HDROP)
HPIV = empty("HammerPivot", (HX + 5.2, HY, 2.6))
wood_m, _ = principled("Wood", (0.32, 0.17, 0.07), rough=0.55, coat=0.3, bump=0.1, bump_scale=30)
hh = tube("HammerHandle", [(0, 0, 0), (-4.6, 0, 0)], [0.19, 0.16], wood_m, seg=20)
hh.parent = HPIV
hhead = lathe("HammerHead", [(0.0, -0.6), (0.56, -0.6), (0.62, -0.54), (0.62, 0.54), (0.56, 0.6), (0.0, 0.6)],
              metal_m, seg=48, smooth=False)
hhead.parent = HPIV
hhead.location = (-5.2, 0, 0)
to_set("hammer", HPIV, hh, hhead)
area("HKey", (HX - 4, -7, 7), (HX, 0, 1), 400, 5.0, (1.0, 0.98, 0.95), "hammer")
area("HRim", (HX + 3, 5, 4), (HX, 0, 1.2), 600, 2.5, (0.85, 0.92, 1.0), "hammer")
area("HRim2", (HX - 4, 5, 3), (HX, 0, 1.2), 400, 2.5, (1.0, 0.9, 0.85), "hammer")
hb = obj_from("HamBack", [(HX - 14, 14, -12), (HX + 14, 14, -12), (HX + 14, 14, 22), (HX - 14, 14, 22)], [[0, 1, 2, 3]], bd_m)
to_set("hammer", hb)
imp_m, IMP_A, IMP_S = fade_emit_mat("Impact", (0.8, 0.9, 1.0), 6.0)
IMPACT = lathe("ImpactRing", [(0.9, -0.02), (1.0, 0.0), (1.1, -0.02)], imp_m, seg=64)
IMPACT.location = (HX, HY, 2.02)
to_set("hammer", IMPACT)


def pose_hammer(t):
    HPIV.rotation_euler = (0, math.radians(T.hammer_angle(t)), 0)
    f = T.flash(t)
    HAM_K["rb"].default_value = 1.6 + 6.0 * f
    u = t - T.T_HIT
    s = 0.3 + 2.4 * T.clamp(u / 0.35) ** 0.5 if u > 0 else 0.01
    IMPACT.scale = (s, s, 1)
    IMP_A.default_value = 0.0 if u < 0 else 0.8 * math.exp(-u / 0.18)


# backdrops: re-centre each mesh on its glow centre (the gradient is in object space)
for _n, _c in (("Backdrop", (0.0, 14.0, 2.0)), ("SecBack", (T.SECTION[0], 14.0, 1.5)), ("HamBack", (T.HAMMER[0], 14.0, 1.5))):
    _o = bpy.data.objects[_n]
    _w = _o.matrix_world.copy()
    _o.data.transform(_w)
    _o.matrix_world = Matrix.Identity(4)
    _o.data.transform(Matrix.Translation((-_c[0], -_c[1], -_c[2])))
    _o.location = _c


# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.clip_start = 0.02
cam_d.clip_end = 500
cam = bpy.data.objects.new("Cam", cam_d)
cam.rotation_mode = "QUATERNION"
col.objects.link(cam)
scene.camera = cam


# ================================================================= per-frame posing
def pose_drop(t):
    te = T.env_t(t)
    F = T.front_z(t)
    DROP_K["front"].default_value = F
    DROP_K["tail"].default_value = T.tail_glow(t)
    shards_pose(te if F < 50 else -99.0)
    ci = T.cutter_in(t)
    CUTTER.location = CUT_PIVOT + V((7.0 * (1 - ci), 0.0, 0.0))
    cl = T.cutter_close(t)
    for jp, sgn in JAWS:
        jp.rotation_euler = (0, math.radians(-sgn * 16 * (1 - cl)), 0)
    moving = F < 50 and F > -1.05
    if moving:
        zf = max(F, -0.9)
        FRONT_L.location = (T.bend(zf) + 0.0, -0.9, zf + 0.15)
        burst = math.exp(-max(0.0, te - T.TE_HEAD) / 0.5) if te > T.TE_HEAD else 0.6
        FRONT_L.data.energy = 25 + 160 * burst
    else:
        FRONT_L.data.energy = 0.0


def pose(t):
    st = T.shot_set(t)
    for name, objs in SETS.items():
        for o in objs:
            o.hide_render = name != st
    if st == "drop":
        pose_drop(t)
    elif st == "water":
        pose_water(t)
    elif st == "section":
        pose_section(t)
    else:
        pose_hammer(t)


def cam_shake(t):
    u = None
    if T.shot_index(t) == 3:
        u = t - T.T_HIT
    elif T.shot_index(t) in (0, len(T.SHOTS) - 1):
        u = T.env_t(t) - T.TE_HEAD
    if u is not None and 0 < u < 0.8:
        k = 0.04 * math.exp(-u / 0.2)
        return (k * math.sin(u * 61), 0, k * math.sin(u * 47))
    return (0, 0, 0)

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
c.max_bounces = 10
c.diffuse_bounces = 1
c.glossy_bounces = 4
c.transparent_max_bounces = 24
c.transmission_bounces = 8
c.caustics_reflective = False
c.caustics_refractive = False
c.blur_glossy = 1.0
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0
except Exception:
    pass

SPP = {"drop": 36, "water": 32, "section": 20, "hammer": 28}
if os.environ.get("GD_EXP"):
    exec(os.environ["GD_EXP"])

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
