"""Blender scene for "This Diamond Is Burning Into Thin Air" (Cycles, posed per frame).

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
SETS = {"fire": [], "atoms": [], "ring": [], "pencil": []}
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


def aim(o, frm, to):
    o.location = frm
    o.rotation_euler = (V(to) - V(frm)).to_track_quat("Z", "Y").to_euler()


# ================================================================= world: a dark studio
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
wr = ramp(wnt, [(0.0, (0.002, 0.002, 0.003)), (0.5, (0.006, 0.006, 0.010)), (1.0, (0.020, 0.024, 0.040))])
wnt.links.new(wsep.outputs["Z"], wr.inputs[0])
wbg = wnt.nodes.new("ShaderNodeBackground")
WORLD_S = wbg.inputs["Strength"]
WORLD_S.default_value = 1.0
wnt.links.new(wr.outputs[0], wbg.inputs["Color"])
wnt.links.new(wbg.outputs[0], wnt.nodes["World Output"].inputs[0])


# ================================================================= the diamond (round brilliant cut)
def brilliant_vf(crown=0.32, pav=0.86, table=0.56):
    pts = []
    for k in range(8):                                             # table corners
        a = 2 * math.pi * k / 8 + math.pi / 8
        pts.append((table * math.cos(a), table * math.sin(a), crown))
    for k in range(8):                                             # bezel / star points
        a = 2 * math.pi * k / 8
        pts.append((0.80 * math.cos(a), 0.80 * math.sin(a), 0.165))
    for k in range(32):                                            # girdle
        a = 2 * math.pi * k / 32
        pts.append((math.cos(a), math.sin(a), 0.015))
        pts.append((math.cos(a), math.sin(a), -0.015))
    for k in range(8):                                             # pavilion mains
        a = 2 * math.pi * k / 8 + math.pi / 8
        pts.append((0.52 * math.cos(a), 0.52 * math.sin(a), -0.40))
    pts.append((0.0, 0.0, -pav))                                   # culet
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts, edges=bm.edges)
    bm.verts.index_update()
    vv = np.array([v.co[:] for v in bm.verts])
    ff = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    return vv, ff


DIA_V, DIA_F = brilliant_vf()


def diamond_mat(name, hot=True):
    """Clear diamond (glass with dispersion) blended into white-hot emission by HEAT."""
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.0, IOR=2.42)
    p.inputs["Base Color"].default_value = (1, 1, 1, 1)
    p.inputs["Transmission Weight"].default_value = 1.0
    p.inputs["Transmission Dispersion Scale"].default_value = 3.0
    p.inputs["Transmission Dispersion Abbe Number"].default_value = 55.0
    if not hot:
        nt.links.new(p.outputs[0], out.inputs[0])
        return m, None
    temp = value(nt, 900.0)
    strength = value(nt, 0.0)
    mixv = value(nt, 0.0)
    bb = ramp(nt, [(0.0, (0.35, 0.01, 0.0)), (0.3, (1.0, 0.07, 0.0)), (0.65, (1.0, 0.22, 0.01)),
                   (1.0, (1.0, 0.42, 0.03))])
    nt.links.new(temp, bb.inputs[0])
    lw = node(nt, "ShaderNodeLayerWeight", Blend=0.35)
    core = math_node(nt, "POWER", math_node(nt, "SUBTRACT", 1.1, lw.outputs["Facing"]), 3.0)       # brighter where the facet faces us
    st = math_node(nt, "MULTIPLY", strength, core)
    # white-hot core where the facets face us, deep orange towards the silhouette
    corew = math_node(nt, "MULTIPLY", math_node(nt, "POWER", math_node(nt, "SUBTRACT", 1.0, lw.outputs["Facing"]), 3.0),
                      temp, clamp=True)
    cmix = nt.nodes.new("ShaderNodeMix")
    cmix.data_type = "RGBA"
    nt.links.new(corew, cmix.inputs["Factor"])
    nt.links.new(bb.outputs[0], cmix.inputs["A"])
    cmix.inputs["B"].default_value = (1.0, 0.82, 0.5, 1)
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(cmix.outputs["Result"], em.inputs["Color"])
    nt.links.new(st, em.inputs["Strength"])
    addg = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(p.outputs[0], addg.inputs[0])
    nt.links.new(em.outputs[0], addg.inputs[1])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(mixv, mix.inputs[0])
    nt.links.new(addg.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m, (temp, strength, mixv)


dia_hot_m, (HEAT_T, HEAT_S, HEAT_MIX) = diamond_mat("DiamondHot")
DIAMOND = obj_from("Diamond", DIA_V, DIA_F, dia_hot_m, smooth=False)
DIAMOND.location = (0, 0, T.GIRDLE_Z)
to_set("fire", DIAMOND)

hl = bpy.data.lights.new("HotGlow", "POINT")
hl.shadow_soft_size = 0.6
HOT_L = bpy.data.objects.new("HotGlow", hl)
HOT_L.location = (0, 0, T.GIRDLE_Z + 0.2)
col.objects.link(HOT_L)
to_set("fire", HOT_L)


# ---------------------------------------------------------------- dish, slate, charcoal, torch
dish_m, dnt, dout = new_mat("Dish")
dp = node(dnt, "ShaderNodeBsdfPrincipled", Roughness=0.85)
dp.inputs["Base Color"].default_value = (0.3, 0.285, 0.27, 1)
dtc = node(dnt, "ShaderNodeTexCoord")
dvl = dnt.nodes.new("ShaderNodeVectorMath")
dvl.operation = "LENGTH"
dnt.links.new(dtc.outputs["Object"], dvl.inputs[0])
dglow_r = ramp(dnt, [(0.0, (1, 1, 1)), (0.35, (0.5, 0.5, 0.5)), (0.75, (0, 0, 0))])
d_dist = math_node(dnt, "DIVIDE", dvl.outputs["Value"], 2.2)
dnt.links.new(d_dist, dglow_r.inputs[0])
DISH_GLOW = value(dnt, 0.0)
dgs = math_node(dnt, "MULTIPLY", dglow_r.outputs[0], DISH_GLOW)
dp.inputs["Emission Color"].default_value = (1.0, 0.36, 0.08, 1)
dnt.links.new(dgs, dp.inputs["Emission Strength"])
dnz = node(dnt, "ShaderNodeTexNoise", Scale=30.0, Detail=4.0)
dnt.links.new(dtc.outputs["Object"], dnz.inputs["Vector"])
dbp = node(dnt, "ShaderNodeBump", Strength=0.12, Distance=0.02)
dnt.links.new(dnz.outputs["Fac"], dbp.inputs["Height"])
dnt.links.new(dbp.outputs["Normal"], dp.inputs["Normal"])
dnt.links.new(dp.outputs[0], dout.inputs[0])
DISH = lathe("Dish", [(0.0, 0.0), (1.9, 0.0), (2.1, 0.08), (2.2, 0.40), (2.12, 0.47), (1.95, 0.45), (1.2, 0.30),
                      (0.5, 0.15), (0.0, 0.11)], dish_m, seg=96)
to_set("fire", DISH)

slate_m, sp_ = principled("Slate", (0.018, 0.018, 0.02), rough=0.32, bump=0.25, bump_scale=3.0)
SLATE = obj_from("Slate", [(-60, -60, 0), (60, -60, 0), (60, 60, 0), (-60, 60, 0)], [[0, 1, 2, 3]], slate_m)
to_set("fire", SLATE)


def lump_vf(seed, sub=4):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    bm.verts.index_update()
    vv = np.array([v.co[:] for v in bm.verts])
    ff = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    r = np.random.default_rng(seed)
    d = np.zeros(len(vv))
    for _ in range(14):
        k = r.normal(size=3)
        k *= r.uniform(1.5, 7.0) / np.linalg.norm(k)
        d += r.uniform(0.02, 0.08) * np.sin(vv @ k + r.uniform(0, 6.3))
    # a few flat cleavage planes, like broken charcoal
    for _ in range(5):
        n_ = r.normal(size=3)
        n_ /= np.linalg.norm(n_)
        cut = r.uniform(0.55, 0.8)
        proj = vv @ n_
        over = np.clip(proj - cut, 0, None)
        vv = vv - np.outer(over, n_)
    return vv * (1 + d[:, None]), ff


char_m, cnt, cout = new_mat("Charcoal")
cp_ = node(cnt, "ShaderNodeBsdfPrincipled", Roughness=0.7)
cp_.inputs["Base Color"].default_value = (0.008, 0.008, 0.008, 1)
cp_.inputs["Sheen Weight"].default_value = 0.15
ctc = node(cnt, "ShaderNodeTexCoord")
cnz = node(cnt, "ShaderNodeTexVoronoi", Scale=14.0)
cnt.links.new(ctc.outputs["Object"], cnz.inputs["Vector"])
cbp = node(cnt, "ShaderNodeBump", Strength=0.5, Distance=0.03)
cnt.links.new(cnz.outputs["Distance"], cbp.inputs["Height"])
cnt.links.new(cbp.outputs["Normal"], cp_.inputs["Normal"])
cnt.links.new(cp_.outputs[0], cout.inputs[0])
cv, cf = lump_vf(3)
CHAR = obj_from("Charcoal", cv, cf, char_m)
CHAR.location = (2.75, 0.5, 0.55)
CHAR.scale = (1.15, 0.95, 0.75)
CHAR.rotation_euler = (0.3, 0.1, 0.6)
to_set("fire", CHAR)


def flame_mat(name, c0, c1, length, strength, power=1.6):
    """Glowing gas along the object's local +Z (0..length): brightest in the middle of the silhouette,
    fading at both ends, flickering with animated 4D noise. Returns (mat, alpha socket)."""
    m, nt, out = new_mat(name)
    tc = node(nt, "ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    u = math_node(nt, "DIVIDE", sep.outputs["Z"], length)
    col_r = ramp(nt, [(0.0, c0), (1.0, c1)])
    nt.links.new(u, col_r.inputs[0])
    al_r = ramp(nt, [(0.0, (0, 0, 0)), (0.08, (1, 1, 1)), (0.55, (0.8, 0.8, 0.8)), (1.0, (0, 0, 0))])
    nt.links.new(u, al_r.inputs[0])
    lw = node(nt, "ShaderNodeLayerWeight", Blend=0.5)
    cen = math_node(nt, "POWER", math_node(nt, "SUBTRACT", 1.0, lw.outputs["Facing"]), power)
    nz = node(nt, "ShaderNodeTexNoise", Scale=2.2, Detail=3.0)
    nz.noise_dimensions = "4D"
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    w = value(nt, 0.0)
    nt.links.new(w, nz.inputs["W"])
    flick = math_node(nt, "MULTIPLY_ADD", nz.outputs["Fac"], 1.4)
    nt.nodes[-1].inputs[2].default_value = -0.2
    a = value(nt, 1.0)
    al = math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", cen, al_r.outputs[0]),
                   math_node(nt, "MULTIPLY", flick, a), clamp=True)
    em = node(nt, "ShaderNodeEmission", Strength=strength)
    nt.links.new(col_r.outputs[0], em.inputs["Color"])
    tr = node(nt, "ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(al, mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    FLAME_W.append(w)
    return m, a


FLAME_W = []

# torch: a brass nozzle aimed at the diamond, with a blue oxygen flame
D_C = V((0.0, 0.0, T.GIRDLE_Z + 0.05))
T_DIR = (D_C - V((-4.8, -1.3, 2.3))).normalized()
NOZ_TIP = D_C - T_DIR * 1.95
brass_m, _bp = principled("Brass", (0.75, 0.52, 0.22), rough=0.25)
_bp.inputs["Metallic"].default_value = 1.0
NOZZLE = tube("Nozzle", [NOZ_TIP - T_DIR * 6.0, NOZ_TIP - T_DIR * 0.4, NOZ_TIP], [0.24, 0.2, 0.13], brass_m, seg=24)
to_set("fire", NOZZLE)
tf_m, TORCH_A = flame_mat("TorchFlame", (0.45, 0.65, 1.0), (0.1, 0.2, 1.0), 1.9, 3.0, power=1.6)
TORCH = lathe("TorchFlame", [(0.06, 0.0), (0.14, 0.15), (0.2, 0.6), (0.26, 1.3), (0.2, 1.75), (0.0, 1.95)], tf_m, seg=32)
aim(TORCH, NOZ_TIP, D_C)
tc_m, TORCH_CA = flame_mat("TorchCore", (0.75, 0.88, 1.0), (0.3, 0.5, 1.0), 0.7, 6.0, power=1.4)
TORCH_CORE = lathe("TorchCore", [(0.04, 0.0), (0.08, 0.1), (0.07, 0.45), (0.0, 0.7)], tc_m, seg=24)
aim(TORCH_CORE, NOZ_TIP, D_C)
to_set("fire", TORCH, TORCH_CORE)
no_bounce([TORCH, TORCH_CORE])

# the burning envelope around the diamond (faint orange flame licking upwards)
fl_m, FLAME_A = flame_mat("BurnFlame", (1.0, 0.6, 0.2), (1.0, 0.25, 0.04), 2.1, 4.0, power=2.5)
BURN = lathe("BurnFlame", [(0.85, 0.0), (0.95, 0.3), (0.8, 0.8), (0.45, 1.4), (0.18, 1.85), (0.0, 2.1)], fl_m, seg=48)
BURN.location = (0, 0, T.GIRDLE_Z - 0.35)
to_set("fire", BURN)
no_bounce([BURN])

# sparks: short glowing streaks, a continuous spray plus a burst when the diamond flares up
spark_m, _sps = emit_mat("Spark", (1.0, 0.32, 0.03), 4.0)
NSP_C, NSP_B = 32, 50
NSP = NSP_C + NSP_B
SP_SEG = 5
SPARKS = Dyn("Sparks", np.zeros((NSP * (2 * SP_SEG + 2), 3)),
             [f for k in range(NSP) for f in tube_faces(2, SP_SEG, k * (2 * SP_SEG + 2))], spark_m, sets=("fire",))
no_bounce([SPARKS.o])
sp_dir = rng.normal(size=(NSP, 3))
sp_dir[:, 2] = np.abs(sp_dir[:, 2]) * 1.4 + 0.3
sp_dir /= np.linalg.norm(sp_dir, axis=1, keepdims=True)
sp_speed = rng.uniform(1.4, 3.6, NSP)
sp_life = rng.uniform(0.35, 0.8, NSP)
sp_period = sp_life + rng.uniform(0.1, 0.6, NSP)
sp_phase = rng.uniform(0, 3, NSP)
sp_r = rng.uniform(0.006, 0.014, NSP)


def spark_verts(te, h, burst_age):
    G = 7.0
    out = []
    for k in range(NSP):
        if k < NSP_C:
            age = (te + sp_phase[k]) % sp_period[k]
            on = h > 0.55 and age < sp_life[k]
            life = sp_life[k]
        else:
            age = burst_age
            life = sp_life[k] * 1.6
            on = burst_age is not None and 0 <= burst_age < life
        if not on:
            out.append(np.zeros((2 * SP_SEG + 2, 3)) + (0, 0, -5))
            continue
        p0 = np.array(D_C) + sp_dir[k] * 0.75
        v = sp_dir[k] * sp_speed[k] * (1.6 if k >= NSP_C else 1.0)

        def pos(a):
            return p0 + v * a + np.array([0, 0, -0.5 * G * a * a])
        a1 = age
        a0 = max(0.0, age - 0.05)
        r = sp_r[k] * (1 - age / life) * (1.0 if k >= NSP_C else T.clamp((h - 0.55) / 0.3))
        out.append(tube_verts(np.array([pos(a0), pos(a1) + 1e-4]), np.full(2, max(r, 1e-4)), SP_SEG))
    return np.concatenate(out)


# lights for the fire set
area("FireKey", (-3.5, -4.0, 6.0), (0, 0, 0.8), 45, 3.0, (1.0, 0.92, 0.85), "fire")
area("FireRim", (2.5, 5.0, 3.5), (0, 0, 0.9), 420, 2.5, (0.75, 0.85, 1.0), "fire")
for k, (x, y, z) in enumerate([(-2.0, -3.0, 4.0), (2.5, -2.5, 3.0), (0.5, 3.0, 4.5), (-3.0, 1.0, 2.0)]):
    lo = area(f"FireSparkle{k}", (x, y, z), (0, 0, T.GIRDLE_Z), 140, 0.25, (1, 1, 1), "fire")


# ================================================================= atoms: the diamond crystal lattice
AX, AY, AZ = T.ATOMS
NX, NY, NZ = 7, 7, 4
basis = np.array([(0, 0, 0), (0, .5, .5), (.5, 0, .5), (.5, .5, 0)], float)
basis = np.concatenate([basis, basis + 0.25])
pts = []
for i in range(-1, NX + 1):
    for j in range(-1, NY + 1):
        for k in range(-1, NZ + 1):
            for b in basis:
                p = np.array((i, j, k), float) + b
                if -1e-6 <= p[0] <= NX + 1e-6 and -1e-6 <= p[1] <= NY + 1e-6 and -1e-6 <= p[2] <= NZ + 1e-6:
                    pts.append(p)
pts = np.unique(np.round(np.array(pts), 4), axis=0)
pts = pts - np.array((NX / 2, NY / 2, 0.0))
# atoms that leave as CO2: top-layer atoms near the middle
top = np.where((pts[:, 2] >= NZ - 0.01) & (np.abs(pts[:, 0]) < 2.6) & (np.abs(pts[:, 1]) < 2.2))[0]
leave = rng.permutation(top)[:T.N_MOL]
leave_set = set(leave.tolist())
stay = [i for i in range(len(pts)) if i not in leave_set]
A_R, B_R = 0.115, 0.03
atom_m, ant, aout = new_mat("Atom")
ap = node(ant, "ShaderNodeBsdfPrincipled", Roughness=0.22)
ap.inputs["Base Color"].default_value = (0.07, 0.09, 0.13, 1)
ap.inputs["Coat Weight"].default_value = 0.6
atc = node(ant, "ShaderNodeTexCoord")
asep = ant.nodes.new("ShaderNodeSeparateXYZ")
ant.links.new(atc.outputs["Object"], asep.inputs[0])
ahr = ramp(ant, [(0.0, (0, 0, 0)), (0.88, (0.0, 0.0, 0.0)), (1.0, (1, 1, 1))])
ant.links.new(math_node(ant, "DIVIDE", asep.outputs["Z"], NZ), ahr.inputs[0])
ATOM_HEAT = value(ant, 0.0)
ap.inputs["Emission Color"].default_value = (1.0, 0.25, 0.03, 1)
ant.links.new(math_node(ant, "MULTIPLY", ahr.outputs[0], ATOM_HEAT), ap.inputs["Emission Strength"])
ant.links.new(ap.outputs[0], aout.inputs[0])
bond_m, bnt, bout = new_mat("Bond")
bem = node(bnt, "ShaderNodeEmission", Strength=3.0)
BOND_C = bem.inputs["Color"]
BOND_S = bem.inputs["Strength"]
BOND_C.default_value = (0.25, 0.75, 1.0, 1)
bnt.links.new(bem.outputs[0], bout.inputs[0])

ab = Builder()
for i in stay:
    ab.sphere(pts[i] + (AX, AY, AZ), (A_R,) * 3)
ATOMS_O = ab.build("Atoms", atom_m)
bb_ = Builder()
cyl_v, cyl_f = [], []
_bond_n = 0
dmax = math.sqrt(3) / 4 + 0.02
stay_pts = pts[stay]
for a_i in range(len(stay_pts)):
    d = np.linalg.norm(stay_pts - stay_pts[a_i], axis=1)
    for b_i in np.where((d > 0.1) & (d < dmax))[0]:
        if b_i <= a_i:
            continue
        p0 = stay_pts[a_i] + (AX, AY, AZ)
        p1 = stay_pts[b_i] + (AX, AY, AZ)
        vv = tube_verts(np.array([p0, p1]), np.full(2, B_R), 8)
        cyl_v.append(vv)
        cyl_f += tube_faces(2, 8, _bond_n * 18)
        _bond_n += 1
BONDS = obj_from("Bonds", np.concatenate(cyl_v), cyl_f, bond_m)
to_set("atoms", ATOMS_O, BONDS)

oxy_m, _op = principled("Oxygen", (0.85, 0.06, 0.04), rough=0.25, coat=0.6)
NL = len(leave)
LEAVE_C = Dyn("LeaveC", np.zeros((NL * len(SPH_V), 3)), [[i + k * len(SPH_V) for i in f] for k in range(NL) for f in SPH_F],
              atom_m, sets=("atoms",))
LEAVE_O = Dyn("LeaveO", np.zeros((2 * NL * len(SPH_V), 3)),
              [[i + k * len(SPH_V) for i in f] for k in range(2 * NL) for f in SPH_F], oxy_m, sets=("atoms",))
lv_t = np.sort(rng.uniform(0.0, 1.0, NL))[rng.permutation(NL)]
lv_ang = rng.uniform(0, 2 * math.pi, NL)
lv_drift = rng.normal(size=(NL, 2)) * 0.25
lv_spin = rng.uniform(-3, 3, NL)
O_R = 0.1
CO_D = 0.21


def molecule_pose(t):
    """Positions of the leaving carbons and their two oxygens at time t (S4 = shot 4)."""
    s0, s1 = T.SHOTS[4][0], T.SHOTS[4][1]
    i4 = T.shot_index(t) == 4
    cs, os_ = [], []
    for j, idx in enumerate(leave):
        home = pts[idx] + (AX, AY, AZ)
        td = T.mol_depart(j) if i4 else 1e9
        u = t - td
        ang = lv_ang[j] + lv_spin[j] * max(0.0, u)
        axis = np.array([math.cos(ang), math.sin(ang), 0.35 * math.sin(2 * ang)])
        axis /= np.linalg.norm(axis)
        if u < -0.5:                                      # waiting in the lattice, oxygens far away
            c = home
            o_a = o_b = None
        elif u < 0:                                        # oxygens swoop in
            c = home
            k = T.smoother((u + 0.5) / 0.5)
            far = np.array([0, 0, 2.6])
            o_a = home + axis * CO_D + far * (1 - k) + np.array([0.9, 0, 0]) * (1 - k)
            o_b = home - axis * CO_D + far * (1 - k) - np.array([0.9, 0, 0]) * (1 - k)
        else:                                              # the CO2 molecule lifts off and drifts away
            lift = 1.3 * u + 0.9 * u * u
            c = home + np.array([lv_drift[j][0] * u, lv_drift[j][1] * u, lift])
            o_a, o_b = c + axis * CO_D, c - axis * CO_D
        cs.append(SPH_V * A_R + c)
        for o in (o_a, o_b):
            os_.append(SPH_V * (O_R if o is not None else 0.0) + (o if o is not None else home))
    return np.concatenate(cs), np.concatenate(os_)


area("AtomKey", (AX - 4.0, AY - 6.0, AZ + 8.0), (AX, AY, AZ + 2.0), 400, 4.0, (1.0, 0.95, 0.9), "atoms")
area("AtomRim", (AX + 5.0, AY + 6.0, AZ + 6.0), (AX, AY, AZ + 2.0), 700, 4.0, (0.6, 0.8, 1.0), "atoms")


# ================================================================= ring on velvet
RX, RY, RZ = T.RING
vel_m, vnt, vout = new_mat("Velvet")
vp = node(vnt, "ShaderNodeBsdfPrincipled", Roughness=0.9)
vp.inputs["Base Color"].default_value = (0.012, 0.016, 0.06, 1)
vp.inputs["Sheen Weight"].default_value = 1.0
vp.inputs["Sheen Roughness"].default_value = 0.35
vp.inputs["Sheen Tint"].default_value = (0.45, 0.55, 1.0, 1)
vtc = node(vnt, "ShaderNodeTexCoord")
vnz = node(vnt, "ShaderNodeTexNoise", Scale=1.2, Detail=2.0)
vnt.links.new(vtc.outputs["Object"], vnz.inputs["Vector"])
vbp = node(vnt, "ShaderNodeBump", Strength=0.35, Distance=0.2)
vnt.links.new(vnz.outputs["Fac"], vbp.inputs["Height"])
vnt.links.new(vbp.outputs["Normal"], vp.inputs["Normal"])
vnt.links.new(vp.outputs[0], vout.inputs[0])
# velvet with soft folds
gv, gf = [], []
NG = 80
for j in range(NG + 1):
    for i in range(NG + 1):
        x = -12 + 24 * i / NG
        y = -12 + 24 * j / NG
        z = 0.18 * math.sin(0.5 * x + 1.3 * math.sin(0.3 * y)) * T.smoother((abs(x) - 1.5) / 3) - 0.05
        gv.append((RX + x, RY + y, RZ + z))
for j in range(NG):
    for i in range(NG):
        a = j * (NG + 1) + i
        gf.append([a, a + 1, a + NG + 2, a + NG + 1])
VELVET = obj_from("Velvet", gv, gf, vel_m)
gold_m, gp = principled("Gold", (1.0, 0.72, 0.32), rough=0.12)
gp.inputs["Metallic"].default_value = 1.0
# the band: a torus standing upright (axis along Y), slightly sunk into the velvet
tv, tf_ = [], []
MR, mr = 0.9, 0.085
NU, NV = 128, 20
for i in range(NU):
    a = 2 * math.pi * i / NU
    for j in range(NV):
        b = 2 * math.pi * j / NV
        r = MR + mr * math.cos(b)
        tv.append((RX + r * math.sin(a), RY + 1.6 * mr * math.sin(b), RZ + 0.92 + r * math.cos(a)))
for i in range(NU):
    for j in range(NV):
        tf_.append([i * NV + j, i * NV + (j + 1) % NV, ((i + 1) % NU) * NV + (j + 1) % NV, ((i + 1) % NU) * NV + j])
BAND = obj_from("Band", tv, tf_, gold_m)
RING_DS = 0.42
RING_GZ = RZ + 0.92 + MR + mr + 0.86 * RING_DS * 0.62
dia_cold_m, _ = diamond_mat("DiamondCold", hot=False)
RDIA = obj_from("RingDiamond", DIA_V, DIA_F, dia_cold_m, smooth=False)
RDIA.location = (RX, RY, RING_GZ)
RDIA.scale = (RING_DS,) * 3
prongs = []
for k in range(4):
    a = math.pi / 4 + k * math.pi / 2
    c, s = math.cos(a), math.sin(a)
    path = [(RX + 0.10 * c, RY + 0.10 * s, RZ + 0.92 + MR + 0.02),
            (RX + 0.30 * c, RY + 0.30 * s, RING_GZ - 0.18),
            (RX + RING_DS * 1.02 * c, RY + RING_DS * 1.02 * s, RING_GZ + 0.02),
            (RX + RING_DS * 0.9 * c, RY + RING_DS * 0.9 * s, RING_GZ + 0.09)]
    prongs.append(tube(f"Prong{k}", path, [0.05, 0.042, 0.036, 0.03], gold_m, seg=10))
to_set("ring", VELVET, BAND, RDIA, *prongs)
RING_KEY = area("RingKey", (RX - 3.0, RY - 5.0, RZ + 6.0), (RX, RY, RZ + 1.4), 380, 3.0, (1.0, 0.96, 0.9), "ring")
area("RingRim", (RX + 3.5, RY + 4.0, RZ + 3.0), (RX, RY, RZ + 1.6), 500, 2.0, (0.7, 0.8, 1.0), "ring")
RING_SPARK = []
for k, (x, y, z) in enumerate([(-1.5, -3.0, 4.5), (2.0, -2.0, 4.0), (0.0, 2.5, 5.0), (-2.5, 1.0, 3.5), (1.0, -3.5, 2.5)]):
    RING_SPARK.append(area(f"RingSparkle{k}", (RX + x, RY + y, RZ + z), (RX, RY, RING_GZ), 160, 0.18, (1, 1, 1), "ring"))
def softbox(name, loc, target, w, h_, strength, set_):
    m_, _s = emit_mat(name, (1, 1, 1), strength)
    o = obj_from(name, [(-w, -h_, 0), (w, -h_, 0), (w, h_, 0), (-w, h_, 0)], [[0, 1, 2, 3]], m_)
    aim(o, loc, target)
    o.visible_camera = False
    o.visible_diffuse = False
    to_set(set_, o)
    return o


for k, (x, y, z) in enumerate([(-2.5, -3.0, 3.5), (2.8, -2.2, 3.0), (0.0, 3.0, 4.0), (-3.0, 1.5, 2.2), (0.5, -1.0, 5.0)]):
    softbox(f"RingBox{k}", (RX + x, RY + y, RING_GZ + z), (RX, RY, RING_GZ), 0.6, 1.2, 12.0, "ring")
    softbox(f"FireBox{k}", (x, y, T.GIRDLE_Z + z), (0, 0, T.GIRDLE_Z), 0.6, 1.2, 5.0, "fire")
sund = bpy.data.lights.new("TimeSun", "SPOT")
sund.energy = 0.0
sund.spot_size = math.radians(40)
sund.spot_blend = 0.6
sund.shadow_soft_size = 0.3
sund.color = (1.0, 0.85, 0.6)
TIME_SUN = bpy.data.objects.new("TimeSun", sund)
col.objects.link(TIME_SUN)
to_set("ring", TIME_SUN)


# ================================================================= pencil on paper
PX, PY, PZ = T.PENCIL
paper_m, pnt, pout = new_mat("Paper")
pp = node(pnt, "ShaderNodeBsdfPrincipled", Roughness=0.8)
pp.inputs["Base Color"].default_value = (0.86, 0.85, 0.82, 1)
ptc = node(pnt, "ShaderNodeTexCoord")
pnz = node(pnt, "ShaderNodeTexNoise", Scale=60.0, Detail=6.0)
pnt.links.new(ptc.outputs["Object"], pnz.inputs["Vector"])
pbp = node(pnt, "ShaderNodeBump", Strength=0.08, Distance=0.01)
pnt.links.new(pnz.outputs["Fac"], pbp.inputs["Height"])
pnt.links.new(pbp.outputs["Normal"], pp.inputs["Normal"])
pnt.links.new(pp.outputs[0], pout.inputs[0])
PAPER = obj_from("Paper", [(PX - 30, PY - 30, PZ), (PX + 30, PY - 30, PZ), (PX + 30, PY + 30, PZ), (PX - 30, PY + 30, PZ)],
                 [[0, 1, 2, 3]], paper_m)
paint_m, pap = principled("PencilPaint", (0.95, 0.62, 0.05), rough=0.3, coat=0.8)
wood_m, _wp = principled("Wood", (0.78, 0.56, 0.34), rough=0.7, bump=0.3, bump_scale=40.0)
lead_m, lp = principled("Graphite", (0.05, 0.05, 0.055), rough=0.38)
lp.inputs["Metallic"].default_value = 0.6
PEN_L = 10.0
hexv, hexf = [], []
for z in (1.0, PEN_L):
    for k in range(6):
        a = 2 * math.pi * k / 6
        hexv.append((0.32 * math.cos(a), 0.32 * math.sin(a), z))
for k in range(6):
    hexf.append([k, (k + 1) % 6, 6 + (k + 1) % 6, 6 + k])
hexf.append(list(range(6, 12))[::-1])
P_BODY = obj_from("PencilBody", hexv, hexf, paint_m, smooth=False)
P_WOOD = lathe("PencilWood", [(0.09, 0.28), (0.2, 0.6), (0.31, 1.0)], wood_m, seg=36)
P_LEAD = lathe("PencilLead", [(0.0, 0.0), (0.035, 0.05), (0.092, 0.3)], lead_m, seg=24)
PEN_PARTS = (P_BODY, P_WOOD, P_LEAD)
PEN_DIR = V((-0.55, 0.62, 0.56)).normalized()             # from the tip up along the pencil
# the line it draws: a loose wave on the paper
NLINE = 160
line_x = np.linspace(-2.2, 2.4, NLINE)
line_y = 0.32 * np.sin(line_x * 2.1) + 0.12 * np.sin(line_x * 5.3)
LINE_W = 0.055
line_m, lnp = principled("LineGraphite", (0.04, 0.04, 0.045), rough=0.42)
lnp.inputs["Metallic"].default_value = 0.5
LINE = Dyn("PencilLine", np.zeros((2 * NLINE, 3)), [[2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2] for i in range(NLINE - 1)],
           line_m, sets=("pencil",))
to_set("pencil", PAPER, *PEN_PARTS)
area("PenKey", (PX - 4.0, PY - 3.0, PZ + 7.0), (PX, PY, PZ), 1000, 5.0, (1.0, 0.96, 0.9), "pencil")
area("PenFill", (PX + 5.0, PY - 6.0, PZ + 3.0), (PX, PY, PZ), 160, 4.0, (0.8, 0.88, 1.0), "pencil")


def pencil_tip(t):
    u = T.pencil_u(t)
    k = 0.15 + 0.75 * u
    n = k * (NLINE - 1)
    i = int(n)
    f = n - i
    j = min(i + 1, NLINE - 1)
    return k, np.array([line_x[i] * (1 - f) + line_x[j] * f, line_y[i] * (1 - f) + line_y[j] * f])


def pose_pencil(t):
    k, tip = pencil_tip(t)
    tip3 = V((PX + tip[0], PY + tip[1], PZ))
    rot = PEN_DIR.to_track_quat("Z", "Y").to_euler()
    for o in PEN_PARTS:
        o.location = tip3
        o.rotation_euler = rot
    n = max(2, int(k * (NLINE - 1)) + 1)
    xs = np.append(line_x[:n - 1], tip[0])
    ys = np.append(line_y[:n - 1], tip[1])
    pts2 = np.stack([xs, ys], 1)
    d = np.gradient(pts2, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    w = LINE_W * np.minimum(1.0, np.linspace(0.3, 1.0, len(xs)) * 3)
    v = np.zeros((2 * NLINE, 3))
    full = np.zeros((NLINE, 2)) + tip
    full[:len(xs)] = pts2
    nfull = np.zeros((NLINE, 2))
    nfull[:len(xs)] = nrm * w[:, None]
    v[0::2, :2] = full + nfull
    v[1::2, :2] = full - nfull
    v[:, 0] += PX
    v[:, 1] += PY
    v[:, 2] = PZ + 0.004
    LINE.set(v)


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
def pose_fire(t, te, i):
    h = T.heat(t)
    s = T.diamond_scale(t)
    DIAMOND.scale = (s, s, s)
    DIAMOND.location = (0, 0, T.GIRDLE_Z - 0.86 * (1 - s) * 0.9)
    DIAMOND.rotation_euler = (0, 0, 0.15 + 0.04 * te)
    HEAT_T.default_value = h
    HEAT_S.default_value = HEAT_K * (1.2 * h + 6.0 * h ** 2.5)
    HEAT_MIX.default_value = T.clamp((h - 0.1) / 0.45) ** 0.8
    HOT_L.data.energy = 450 * h ** 2
    HOT_L.data.color = (1.0, 0.55 + 0.25 * h, 0.25 + 0.2 * h)
    DISH_GLOW.default_value = 2.5 * h ** 2
    tch = T.torch(t)
    TORCH_A.default_value = 0.35 * tch
    TORCH_CA.default_value = 0.6 * tch
    TORCH.hide_render = TORCH_CORE.hide_render = tch <= 0
    FLAME_A.default_value = 0.16 * T.clamp((h - 0.7) / 0.3)
    BURN.hide_render = True
    BURN.scale = (s, s, s * (1 + 0.06 * math.sin(te * 9)))
    for w in FLAME_W:
        w.default_value = 2.2 * te
    burst = None
    if i == 3 and t >= T.bursts()[0]:
        burst = t - T.bursts()[0]
    elif i in (0, len(T.SHOTS) - 1) and te >= -0.15:
        burst = te + 0.15
    SPARKS.set(spark_verts(te, h, burst))
    SPARKS.o.hide_render = False
    CHAR.hide_render = i != 2


def pose_atoms(t, i):
    hot = i == 4
    ATOM_HEAT.default_value = 2.5 if hot else 0.0
    BOND_C.default_value = (1.0, 0.3, 0.05, 1) if hot else (0.15, 0.6, 1.0, 1)
    BOND_S.default_value = 0.9 if hot else 1.1
    c, o = molecule_pose(t)
    LEAVE_C.set(c)
    LEAVE_O.set(o)


def pose_ring(t, i):
    RDIA.rotation_euler = (0, 0, 0.2 + 0.25 * t)
    if i == 7:
        u = t - T.SHOTS[7][0]
        a = 2 * math.pi * u / T.DAY
        p = V((RX + 6.0 * math.cos(a), RY - 3.0 + 6.0 * math.sin(a) * 0.4, RZ + 3.5 + 2.5 * math.sin(a)))
        aim(TIME_SUN, p, (RX, RY, RZ + 1.4))
        TIME_SUN.rotation_euler = (V((RX, RY, RZ + 1.4)) - p).to_track_quat("-Z", "Y").to_euler()
        TIME_SUN.data.energy = 9000 * T.clamp(0.5 + 0.5 * math.sin(a)) ** 1.5
        RING_KEY.data.energy = 90
    else:
        TIME_SUN.data.energy = 0.0
        RING_KEY.data.energy = 380


def pose(t):
    st = T.shot_set(t)
    i = T.shot_index(t)
    te = T.env_t(t)
    for name, objs in SETS.items():
        for o in objs:
            o.hide_render = name != st
    if st == "fire":
        pose_fire(t, te, i)
    elif st == "atoms":
        pose_atoms(t, i)
    elif st == "ring":
        pose_ring(t, i)
    else:
        pose_pencil(t)


def cam_shake(t):
    i = T.shot_index(t)
    te = T.env_t(t)
    u = None
    if i == 3:
        u = t - T.T_BURNS
    elif i in (0, len(T.SHOTS) - 1):
        u = te + 0.15
    if u is not None and 0 < u < 0.8:
        k = 0.05 * math.exp(-u / 0.18)
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
HEAT_K = float(os.environ.get("HEAT_K", "1.0"))
SPP = {"fire": 28, "atoms": 14, "ring": 36, "pencil": 14}
if os.environ.get("DF_EXP"):
    exec(os.environ["DF_EXP"])

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
