"""Blender scene for "This Beetle Shoots Boiling Spray Out of Its Butt" (procedural, Cycles).

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


def skin_mat(name, base, dark, belly=None, wart=0.5, scale=14.0, rough=0.5, coat=0.25):
    """Toad skin: blotchy colour, warts (voronoi bump), lighter belly (object Z)."""
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=rough)
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Coat Roughness"].default_value = 0.3
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=2.2, Detail=4.0)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    rp = ramp(nt, [(0.38, dark), (0.62, base)])
    nt.links.new(nz.outputs["Fac"], rp.inputs[0])
    col_out = rp.outputs[0]
    if belly:
        sx = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sx.inputs[0])
        mr = node(nt, "ShaderNodeMapRange", **{"From Min": 0.55, "From Max": 0.8})
        nt.links.new(sx.outputs["Z"], mr.inputs["Value"])
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        nt.links.new(mr.outputs["Result"], mx.inputs["Factor"])
        mx.inputs["A"].default_value = (*belly, 1)
        nt.links.new(col_out, mx.inputs["B"])
        col_out = mx.outputs["Result"]
    nt.links.new(col_out, p.inputs["Base Color"])
    vo = node(nt, "ShaderNodeTexVoronoi", Scale=scale)
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    iv = nt.nodes.new("ShaderNodeMath")
    iv.operation = "SUBTRACT"
    iv.inputs[0].default_value = 1.0
    nt.links.new(vo.outputs["Distance"], iv.inputs[1])
    bp = node(nt, "ShaderNodeBump", Strength=wart, Distance=0.04)
    nt.links.new(iv.outputs[0], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


def eye_mat(name, iris, pupil_w=0.55, pupil_h=0.2):
    """Glossy eye with a horizontal pupil on the local +X side."""
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.08)
    p.inputs["Coat Weight"].default_value = 1.0
    p.inputs["Coat Roughness"].default_value = 0.02
    tc = node(nt, "ShaderNodeTexCoord")
    sx = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sx.inputs[0])

    def absdiv(sock, d):
        a = nt.nodes.new("ShaderNodeMath")
        a.operation = "ABSOLUTE"
        nt.links.new(sock, a.inputs[0])
        b = nt.nodes.new("ShaderNodeMath")
        b.operation = "DIVIDE"
        b.inputs[1].default_value = d
        nt.links.new(a.outputs[0], b.inputs[0])
        return b.outputs[0]
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    nt.links.new(absdiv(sx.outputs["Y"], pupil_w), mx.inputs[0])
    nt.links.new(absdiv(sx.outputs["Z"], pupil_h), mx.inputs[1])
    front = nt.nodes.new("ShaderNodeMath")
    front.operation = "LESS_THAN"
    front.inputs[1].default_value = 0.0
    nt.links.new(sx.outputs["X"], front.inputs[0])
    mx2 = nt.nodes.new("ShaderNodeMath")
    mx2.operation = "ADD"
    nt.links.new(mx.outputs[0], mx2.inputs[0])
    nt.links.new(front.outputs[0], mx2.inputs[1])
    nz = node(nt, "ShaderNodeTexNoise", Scale=6.0, Detail=3.0)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ir = ramp(nt, [(0.3, iris), (0.7, tuple(c * 0.55 for c in iris))])
    nt.links.new(nz.outputs["Fac"], ir.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    pm = ramp(nt, [(0.95, (0, 0, 0)), (1.0, (1, 1, 1))])
    nt.links.new(mx2.outputs[0], pm.inputs[0])
    nt.links.new(pm.outputs[0], mix.inputs["Factor"])
    mix.inputs["A"].default_value = (0.005, 0.004, 0.003, 1)
    nt.links.new(ir.outputs[0], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], p.inputs["Base Color"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


SETS = {k: [] for k in ("ground", "lab", "xray")}

# ================================================================= world: dusky forest floor
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wn = world.node_tree
bgw = wn.nodes["Background"]
tcw = node(wn, "ShaderNodeTexCoord")
sxw = wn.nodes.new("ShaderNodeSeparateXYZ")
wn.links.new(tcw.outputs["Generated"], sxw.inputs[0])
mrw = node(wn, "ShaderNodeMapRange", **{"From Min": -0.2, "From Max": 0.9})
wn.links.new(sxw.outputs["Z"], mrw.inputs["Value"])
rw = ramp(wn, [(0.0, (0.004, 0.006, 0.005)), (0.5, (0.012, 0.03, 0.024)), (1.0, (0.05, 0.10, 0.09))])
wn.links.new(mrw.outputs["Result"], rw.inputs[0])
wn.links.new(rw.outputs[0], bgw.inputs[0])
bgw.inputs[1].default_value = 1.0
WORLD_STRENGTH = bgw.inputs[1]

# ================================================================= materials
M_ORANGE = pmat("BeetleOrange", (0.85, 0.42, 0.04), rough=0.3, coat=0.9, bump=0.06, bump_scale=30.0)
M_ELYTRA = spotted_mat("Elytra", (0.008, 0.008, 0.012), (0.95, 0.62, 0.05), scale=4.5, thr=0.16, bump=0.05)
M_BLACK = pmat("BeetleBlack", (0.01, 0.01, 0.012), rough=0.25, coat=1.0, bump=0.0)
M_LEGB = pmat("BeetleLeg", (0.8, 0.45, 0.06), rough=0.35, coat=0.6, bump=0.0)
M_ANT = pmat("Ant", (0.05, 0.012, 0.008), rough=0.3, coat=0.8, bump=0.03)
M_ANTRED = pmat("AntRed", (0.25, 0.04, 0.015), rough=0.3, coat=0.8, bump=0.03)
M_TOAD = skin_mat("ToadSkin", (0.085, 0.06, 0.022), (0.022, 0.016, 0.007), belly=(0.22, 0.17, 0.10))
M_TOADLEG = skin_mat("ToadLeg", (0.08, 0.055, 0.02), (0.022, 0.016, 0.007), wart=0.35)
M_GLAND = skin_mat("ToadGland", (0.13, 0.08, 0.03), (0.05, 0.03, 0.012), wart=0.8, scale=24.0)
M_TEYE = eye_mat("ToadEye", (0.85, 0.52, 0.08))
M_MOUTH = pmat("MouthInside", (0.45, 0.06, 0.06), rough=0.25, coat=1.0, bump=0.0)
M_TONGUE = pmat("Tongue", (0.85, 0.30, 0.30), rough=0.2, coat=1.0, bump=0.05)
M_SOIL, nt_so, out_so = new_mat("Soil")
pso = node(nt_so, "ShaderNodeBsdfPrincipled", Roughness=0.95)
tso = node(nt_so, "ShaderNodeTexCoord")
nso = node(nt_so, "ShaderNodeTexNoise", Scale=1.6, Detail=8.0)
nt_so.links.new(tso.outputs["Object"], nso.inputs["Vector"])
rso = ramp(nt_so, [(0.35, (0.03, 0.02, 0.012)), (0.65, (0.10, 0.07, 0.04))])
nt_so.links.new(nso.outputs["Fac"], rso.inputs[0])
nt_so.links.new(rso.outputs[0], pso.inputs["Base Color"])
nbs = node(nt_so, "ShaderNodeTexNoise", Scale=22.0, Detail=6.0)
nt_so.links.new(tso.outputs["Object"], nbs.inputs["Vector"])
bso = node(nt_so, "ShaderNodeBump", Strength=0.5, Distance=0.05)
nt_so.links.new(nbs.outputs["Fac"], bso.inputs["Height"])
nt_so.links.new(bso.outputs["Normal"], pso.inputs["Normal"])
nt_so.links.new(pso.outputs[0], out_so.inputs[0])
LEAF_MATS = [pmat(f"Leaf{i}", c, rough=0.6, coat=0.1, bump=0.08, bump_scale=9.0) for i, c in enumerate(
    [(0.16, 0.07, 0.02), (0.24, 0.11, 0.025), (0.10, 0.05, 0.015), (0.28, 0.09, 0.02), (0.20, 0.13, 0.04)])]
for _m in LEAF_MATS:
    _p = next(n for n in _m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    _p.inputs["Coat Weight"].default_value = 0.0
    _p.inputs["Specular IOR Level"].default_value = 0.12
    _p.inputs["Roughness"].default_value = 0.85
M_MOSS = pmat("Moss", (0.03, 0.10, 0.015), rough=0.9, coat=0.0, bump=0.4, bump_scale=40.0)
M_BARK = pmat("Bark", (0.05, 0.032, 0.018), rough=0.85, coat=0.0, bump=0.5, bump_scale=6.0)
M_STONE = pmat("Stone", (0.16, 0.15, 0.13), rough=0.6, coat=0.2, bump=0.25, bump_scale=12.0)
M_FERN = pmat("Fern", (0.02, 0.10, 0.02), rough=0.5, coat=0.2, bump=0.0)


# ================================================================= hero: bombardier beetle rig
# local frame: +X forward (head), Z up, ground at z = 0. Length ~1.0.
TIP = V((-0.42, 0, 0.13))          # nozzle at the end of the abdomen


def make_beetle(name, mats, sets=()):
    """mats: dict body/elytra/black/leg -> material (the x-ray versions swap them)."""
    root = empty(name, (0, 0, 0))
    P = {"root": root, "legs": [], "ants": []}
    objs = []

    def add(o, parent=root):
        o.parent = parent
        objs.append(o)
        return o
    add(sph(f"{name}_head", (0.36, 0, 0.15), 1.0, mats["body"], u=32, v=16, scale=(0.11, 0.095, 0.075)))
    for sy in (1, -1):
        add(sph(f"{name}_eye{sy}", (0.41, sy * 0.075, 0.17), 0.028, mats["black"], u=16, v=8))
        add(tube(f"{name}_mand{sy}", [(0.44, sy * 0.04, 0.12), (0.51, sy * 0.035, 0.11), (0.53, sy * 0.008, 0.105)],
                 [0.014, 0.01, 0.005], mats["black"], seg=8))
    add(sph(f"{name}_pron", (0.20, 0, 0.165), 1.0, mats["body"], u=32, v=16, scale=(0.095, 0.115, 0.075)))
    for sy in (1, -1):
        add(sph(f"{name}_ely{sy}", (-0.12, sy * 0.068, 0.185), 1.0, mats["elytra"], u=40, v=20,
                scale=(0.28, 0.078, 0.085)))
    add(sph(f"{name}_belly", (-0.08, 0, 0.12), 1.0, mats["black"], u=24, v=12, scale=(0.30, 0.12, 0.06)))
    tip = empty(f"{name}_tipp", (-0.33, 0, 0.14), root)
    objs.append(tip)
    add(sph(f"{name}_tip", (-0.06, 0, -0.01), 1.0, mats["body"], u=20, v=10, scale=(0.06, 0.05, 0.035)), tip)
    P["tip"] = tip
    for sy in (1, -1):
        piv = empty(f"{name}_antp{sy}", (0.44, sy * 0.05, 0.19), root)
        objs.append(piv)
        add(tube(f"{name}_ant{sy}", [(0, 0, 0), (0.12, sy * 0.08, 0.08), (0.26, sy * 0.17, 0.11), (0.40, sy * 0.26, 0.09)],
                 [0.011, 0.009, 0.008, 0.006], mats["leg"], seg=8), piv)
        P["ants"].append((piv, sy))
    for i, x in enumerate((0.24, 0.10, -0.04)):
        for sy in (1, -1):
            piv = empty(f"{name}_hip{i}{sy}", (x, sy * 0.07, 0.11), root)
            objs.append(piv)
            fx = (0.10, 0.0, -0.10)[i]
            add(tube(f"{name}_leg{i}{sy}", [(0, 0, 0), (fx * 0.6, sy * 0.13, 0.04), (fx * 1.1, sy * 0.24, -0.04),
                                            (fx * 1.5, sy * 0.30, -0.11)], [0.016, 0.013, 0.010, 0.007], mats["leg"], seg=8), piv)
            P["legs"].append((piv, i, sy))
    allobjs = [root] + objs
    for st in sets:
        SETS[st].extend(allobjs)
    P["all"] = allobjs
    return P


def pose_beetle(P, t, phase, wiggle=0.0, curl=0.0):
    """phase: walk cycle (radians). wiggle: fast leg kicking (on its back)."""
    for piv, i, sy in P["legs"]:
        grp = (i + (0 if sy > 0 else 1)) % 2                       # tripod gait
        ph = phase + grp * math.pi
        swing = 0.35 * math.sin(ph) + wiggle * 0.5 * math.sin(t * 24 + i * 1.7 + sy)
        lift = 0.18 * max(0.0, math.cos(ph)) + wiggle * 0.4 * math.sin(t * 19 + i + sy * 2)
        key(piv, "rotation_euler", (-sy * lift, 0, sy * swing))
    for k, (piv, sy) in enumerate(P["ants"]):
        key(piv, "rotation_euler", (0.1 * math.sin(t * 3.1 + k * 2), 0.12 * math.sin(t * 2.3 + k) - 0.05,
                                   0.15 * math.sin(t * 1.7 + k * 1.3)))
    key(P["tip"], "rotation_euler", (0, -curl, 0))


def make_ant(name, sets):
    root = empty(name, (0, 0, 0))
    objs = []

    def add(o, parent=root):
        o.parent = parent
        objs.append(o)
        return o
    add(sph(f"{name}_head", (0.19, 0, 0.11), 1.0, M_ANT, u=24, v=12, scale=(0.07, 0.065, 0.06)))
    add(sph(f"{name}_thx", (0.04, 0, 0.10), 1.0, M_ANTRED, u=24, v=12, scale=(0.09, 0.04, 0.045)))
    add(sph(f"{name}_gas", (-0.16, 0, 0.11), 1.0, M_ANT, u=24, v=12, scale=(0.12, 0.08, 0.075)))
    for sy in (1, -1):
        add(tube(f"{name}_mand{sy}", [(0.24, sy * 0.03, 0.09), (0.29, sy * 0.02, 0.08), (0.30, 0, 0.08)],
                 [0.012, 0.008, 0.004], M_ANT, seg=6))
        add(tube(f"{name}_ant{sy}", [(0.22, sy * 0.03, 0.15), (0.28, sy * 0.08, 0.24), (0.38, sy * 0.12, 0.22)],
                 [0.008, 0.006, 0.004], M_ANT, seg=6))
    legs = []
    for i, x in enumerate((0.08, 0.04, 0.0)):
        for sy in (1, -1):
            piv = empty(f"{name}_hip{i}{sy}", (x, sy * 0.03, 0.08), root)
            objs.append(piv)
            fx = (0.12, 0.0, -0.12)[i]
            add(tube(f"{name}_leg{i}{sy}", [(0, 0, 0), (fx * 0.5, sy * 0.1, 0.05), (fx, sy * 0.2, -0.08)],
                     [0.01, 0.008, 0.005], M_ANTRED, seg=6), piv)
            legs.append((piv, i, sy))
    allobjs = [root] + objs
    for st in sets:
        SETS[st].extend(allobjs)
    return {"root": root, "legs": legs, "all": allobjs}


def pose_ant(A, phase, flail=0.0, t=0.0):
    for piv, i, sy in A["legs"]:
        grp = (i + (0 if sy > 0 else 1)) % 2
        ph = phase + grp * math.pi
        key(piv, "rotation_euler", (-sy * (0.2 * max(0, math.cos(ph)) + flail * 0.5 * math.sin(t * 30 + i)), 0,
                                   sy * (0.45 * math.sin(ph) + flail * 0.6 * math.sin(t * 27 + i * 2 + sy))))


# ================================================================= toad rig
# local frame: +X forward (snout), Z up, ground at z = 0. Length ~3.8, height ~1.9.
def make_toad(name, mats, sets):
    root = empty(name, (0, 0, 0))
    body = empty(f"{name}_body", (0, 0, 0), root)           # squash/heave pivot
    P = {"root": root, "body": body}
    objs = [body]

    def add(o, parent=body):
        o.parent = parent
        objs.append(o)
        return o
    add(sph(f"{name}_torso", (0, 0, 1.0), 1.0, mats["skin"], u=64, v=32, scale=(1.55, 1.2, 0.95)))
    add(sph(f"{name}_head", (1.25, 0, 1.17), 1.0, mats["skin"], u=64, v=32, scale=(0.95, 1.0, 0.42)))
    add(sph(f"{name}_snout", (1.85, 0, 1.06), 1.0, mats["skin"], u=48, v=24, scale=(0.45, 0.72, 0.28)))
    for sy in (1, -1):
        add(sph(f"{name}_gland{sy}", (0.7, sy * 0.62, 1.55), 1.0, mats["gland"], u=32, v=16, scale=(0.45, 0.22, 0.2),
                rot=(0, 0, sy * 0.25)))
        add(sph(f"{name}_brow{sy}", (1.5, sy * 0.5, 1.48), 1.0, mats["skin"], u=32, v=16, scale=(0.32, 0.26, 0.18)))
    eyes = []
    for sy in (1, -1):
        piv = empty(f"{name}_eyep{sy}", (1.55, sy * 0.5, 1.5), body)
        objs.append(piv)
        o = add(sph(f"{name}_eye{sy}", (0, 0, 0), 0.24, mats["eye"], u=40, v=20), piv)
        o.rotation_euler = (0, 0, sy * 0.6)
        eyes.append(piv)
    P["eyes"] = eyes
    # mouth: a dark interior + a hinged lower jaw
    add(sph(f"{name}_mouthin", (1.6, 0, 0.82), 1.0, mats["mouth"], u=40, v=20, scale=(0.62, 0.62, 0.12)))
    jaw = empty(f"{name}_jawp", (0.85, 0, 0.82), body)
    objs.append(jaw)
    add(sph(f"{name}_jaw", (0.70, 0, -0.08), 1.0, mats["skin"], u=48, v=24, scale=(0.74, 0.68, 0.18)), jaw)
    P["jaw"] = jaw
    throat = add(sph(f"{name}_throat", (1.2, 0, 0.62), 1.0, mats["skin"], u=32, v=16, scale=(0.55, 0.6, 0.25)))
    P["throat"] = throat
    # legs: front arms + folded hind legs
    for sy in (1, -1):
        add(tube(f"{name}_arm{sy}", [(1.2, sy * 0.75, 0.75), (1.4, sy * 1.0, 0.4), (1.55, sy * 1.05, 0.08)],
                 [0.2, 0.15, 0.12], mats["leg"], seg=16))
        for k in range(4):
            a = -0.9 + 0.55 * k
            add(sph(f"{name}_fing{sy}{k}", (1.6 + 0.2 * math.cos(a), sy * (1.05 + 0.2 * math.sin(a)), 0.04), 1.0, mats["leg"],
                    u=16, v=8, scale=(0.14, 0.06, 0.04), rot=(0, 0, a)))
        add(sph(f"{name}_thigh{sy}", (-0.8, sy * 1.0, 0.55), 1.0, mats["leg"], u=40, v=20, scale=(0.8, 0.38, 0.45),
                rot=(0, -0.3, sy * 0.4)))
        add(tube(f"{name}_shin{sy}", [(-0.2, sy * 1.25, 0.4), (-1.0, sy * 1.35, 0.2), (-0.4, sy * 1.45, 0.06)],
                 [0.2, 0.15, 0.12], mats["leg"], seg=16))
        add(sph(f"{name}_foot{sy}", (0.0, sy * 1.45, 0.04), 1.0, mats["leg"], u=24, v=8, scale=(0.4, 0.15, 0.05)))
    allobjs = [root] + objs
    for st in sets:
        SETS[st].extend(allobjs)
    P["all"] = allobjs
    return P


def pose_toad(P, t, eyes=1.0, mouth=0.0, gulp=0.0, heave=0.0, breathe=True):
    for piv in P["eyes"]:
        key(piv, "scale", (1.0, 1.0, max(0.12, eyes)))
    key(P["jaw"], "rotation_euler", (0, 0.62 * mouth, 0))
    b = 0.03 * math.sin(t * 2.2) if breathe else 0.0
    # throat is a radius-1 sphere (base scale 1, as in all approved toad frames); the gulp is a subtle swell
    key(P["throat"], "scale", (1 + 0.04 * gulp, 1 + 0.05 * gulp + b * 2, 1 + 0.10 * gulp + b * 3))
    key(P["body"], "scale", (1 - 0.05 * heave, 1 + 0.06 * heave + b * 0.3, 1 + 0.10 * heave + b * 0.5))
    key(P["body"], "rotation_euler", (0, -0.12 * heave - 0.08 * mouth, 0))


# ================================================================= GROUND set
G0 = V(T.GROUND)
ground = bpy.data.meshes.new("Ground")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=2, y_segments=2, size=30)
bm.to_mesh(ground)
bm.free()
ground_o = bpy.data.objects.new("Ground", ground)
ground_o.data.materials.append(M_SOIL)
col.objects.link(ground_o)
SETS["ground"].append(ground_o)
# leaf litter (flat, slightly cupped ellipsoids), kept clear of the action lane
lrnd = random.Random(4)
leaf_b = {i: Builder() for i in range(len(LEAF_MATS))}
LEAF_VF = sphere_vf(16, 6)
for k in range(260):
    x, y = lrnd.uniform(-6, 9), lrnd.uniform(-3.5, 9)
    if -2.5 < x < 6.2 and -0.9 < y < 1.2:
        continue
    s = lrnd.uniform(0.25, 0.6)
    leaf_b[k % len(LEAF_MATS)].sphere((x, y, 0.012 + 0.01 * lrnd.random()), (s, s * 0.45, 0.012),
                                      rot=(lrnd.uniform(-0.08, 0.08), lrnd.uniform(-0.08, 0.08), lrnd.uniform(0, math.pi)),
                                      vf=LEAF_VF)
for i, b in leaf_b.items():
    SETS["ground"].append(b.build(f"Leaves{i}", LEAF_MATS[i]))
# a few small leaves inside the lane (flat, under the walkers)
for k in range(14):
    x, y = lrnd.uniform(-2.4, 1.4), lrnd.uniform(-0.8, 1.1)
    s = lrnd.uniform(0.15, 0.3)
    o = sph(f"LaneLeaf{k}", (x, y, 0.004), 1.0, LEAF_MATS[k % len(LEAF_MATS)], u=16, v=6, scale=(s, s * 0.45, 0.004),
            rot=(0, 0, lrnd.uniform(0, math.pi)))
    SETS["ground"].append(o)
# pebbles + moss mounds
pb = Builder()
for k in range(40):
    x, y = lrnd.uniform(-5, 8), lrnd.uniform(-2.5, 7)
    if -2.5 < x < 6.2 and -1.0 < y < 1.4:
        continue
    s = lrnd.uniform(0.06, 0.22)
    pb.sphere((x, y, s * 0.3), (s, s * lrnd.uniform(0.7, 1.0), s * 0.6), rot=(0, 0, lrnd.uniform(0, 3)))
SETS["ground"].append(pb.build("Pebbles", M_STONE))
mb = Builder()
for k in range(30):
    x, y = lrnd.uniform(-6, 9), lrnd.uniform(2.0, 9)
    s = lrnd.uniform(0.3, 0.9)
    mb.sphere((x, y, 0.0), (s, s, s * 0.35))
SETS["ground"].append(mb.build("Moss", M_MOSS))
# fallen log + fern fronds behind (depth layers, out of focus)
log = tube("Log", [(-7, 4.2, 0.55), (0, 4.6, 0.6), (9, 5.2, 0.55)], [0.75, 0.8, 0.7], M_BARK, seg=32)
SETS["ground"].append(log)
fb = []
for k in range(26):
    x0, y0 = lrnd.uniform(-6, 9), lrnd.uniform(2.6, 6.5)
    h = lrnd.uniform(1.2, 2.8)
    lean = lrnd.uniform(-0.6, 0.6)
    pts = [(x0, y0, 0), (x0 + lean * 0.3, y0 - 0.2, h * 0.5), (x0 + lean, y0 - 0.6, h), (x0 + lean * 1.6, y0 - 1.1, h * 0.85)]
    fb.append(tube(f"Fern{k}", pts, [0.05, 0.04, 0.03, 0.01], M_FERN, seg=6))
    for j in range(7):
        u = 0.25 + 0.1 * j
        p = V(pts[1]).lerp(V(pts[2]), min(1, u)) if u < 1 else V(pts[2])
        for sy in (1, -1):
            o = sph(f"Pinna{k}{j}{sy}", p + V((sy * 0.2, 0, -0.03)), 1.0, M_FERN, u=12, v=6,
                    scale=(0.28 - 0.025 * j, 0.06, 0.012), rot=(0, sy * 0.4, 0))
            fb.append(o)
SETS["ground"] += fb

# lights (sunset key through the canopy, cool rim, soft fill)
sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy, sun_d.color, sun_d.angle = 2.2, (1.0, 0.78, 0.52), math.radians(4)
sun = bpy.data.objects.new("Sun", sun_d)
sun.rotation_euler = (math.radians(58), 0, math.radians(-35))
col.objects.link(sun)
SETS["ground"].append(sun)
area("GroundRim", G0 + V((1.0, 5.5, 3.0)), G0 + V((1.0, 0, 0.5)), 1800, 5.0, (0.45, 0.75, 1.0), "ground")
area("GroundFill", G0 + V((-2.0, -6.0, 2.5)), G0 + V((0.5, 0, 0.4)), 380, 6.0, (0.85, 0.9, 1.0), "ground")

BEETLE_MATS = {"body": M_ORANGE, "elytra": M_ELYTRA, "black": M_BLACK, "leg": M_LEGB}
beetle = make_beetle("Beetle", BEETLE_MATS, sets=("ground",))
ant = make_ant("Ant", sets=("ground",))
TOAD_MATS = {"skin": M_TOAD, "gland": M_GLAND, "eye": M_TEYE, "mouth": M_MOUTH, "leg": M_TOADLEG}
toad = make_toad("Toad", TOAD_MATS, sets=("ground",))
TOAD_LOC = G0 + V((4.0, 0, 0))
toad["root"].location = TOAD_LOC
toad["root"].rotation_euler = (0, 0, math.pi)
MOUTH_W = TOAD_LOC + V((-2.05, 0, 0.82))          # world point at the toad's lips
tongue_o = tube("Tongue", [(0, 0, 0), (0.5, 0, 0.02), (1.0, 0, 0)], [0.06, 0.05, 0.07], M_TONGUE, seg=12)
tongue_tip = sph("TongueTip", (1.0, 0, 0), 0.09, M_TONGUE, u=24, v=12)
tongue_tip.parent = tongue_o
SETS["ground"] += [tongue_o, tongue_tip]


# ---------------------------------------------------------------- spray puffs (hot, pulsing jet)
def make_puffs(name, n, sets, color=(1.0, 0.86, 0.62), strength=1.8):
    out = []
    for k in range(n):
        m, a, s = fade_emit_mat(f"{name}{k}", color, strength)
        soften(m)
        o = sph(f"{name}{k}", (0, 0, 0), 1.0, m, u=24, v=12)
        no_bounce([o])
        SETS[sets].append(o)
        out.append((o, a))
    return out


PUFF_N = 36
PUFF_LIFE = 0.55
ground_puffs = make_puffs("Puff", PUFF_N, "ground")
NOZ_M, NOZ_A, NOZ_S = fade_emit_mat("Nozzle", (1.0, 0.75, 0.4), 18.0)
soften(NOZ_M)
nozzle = sph("NozzleFlash", (0, 0, 0), 1.0, NOZ_M, u=24, v=12)
no_bounce([nozzle])
SETS["ground"].append(nozzle)
spray_l = bpy.data.lights.new("SprayLight", "POINT")
spray_l.color, spray_l.shadow_soft_size = (1.0, 0.8, 0.5), 0.05
spray_lo = bpy.data.objects.new("SprayLight", spray_l)
col.objects.link(spray_lo)
SETS["ground"].append(spray_lo)
prnd = random.Random(12)
PUFF_JIT = [(prnd.uniform(-1, 1), prnd.uniform(-1, 1), prnd.uniform(0.7, 1.3)) for _ in range(400)]


def pose_puffs(puffs, f, origin, direction, strength_at, active, reach=1.6, size=0.42):
    """Each pool slot k shows the puff emitted at the last frame fe = k (mod n)."""
    d = direction.normalized()
    side = d.cross(V((0, 0, 1))).normalized()
    up = side.cross(d).normalized()
    n2 = len(puffs) // 2
    for k, (o, a) in enumerate(puffs):
        half = k // n2                                   # two puffs per frame (second one half a frame later)
        kk = k % n2
        fe = f - ((f - kk) % n2)
        age = (f - fe) / T.FPS + 0.5 * half / T.FPS
        s = strength_at(fe / T.FPS) if active else 0.0
        jx, jy, js = PUFF_JIT[(fe * 2 + half) % 400]
        if s <= 0.01 or age > PUFF_LIFE:
            key(o, "hide_render", True)
            key_socket(a, 0.0)
            continue
        dist = reach * (1 - math.exp(-age * 5.0)) * (0.6 + 0.4 * s)
        spread = dist
        p = origin + d * dist + side * (jx * 0.22 * spread) + up * (jy * 0.16 * spread + 0.25 * age * age)
        r = (0.02 + size * (age / PUFF_LIFE) ** 0.7) * js * (0.5 + 0.5 * s)
        key(o, "location", p)
        key(o, "scale", (r * 1.25, r, r))
        key(o, "rotation_euler", d.to_track_quat("X", "Z").to_euler())
        key(o, "hide_render", False)
        key_socket(a, 0.42 * s * (1 - age / PUFF_LIFE) ** 1.6)


# ================================================================= LAB set: x-ray of the beetle's chemical gun
B0 = V(T.LAB)
XR_BODY, XR_BODY_S = xray_mat("XrBody", (0.25, 0.75, 1.0), 1.6, power=2.6, base=0.0)
XR_ELY, _ = xray_mat("XrEly", (0.35, 0.8, 1.0), 1.4, power=2.6, base=0.0)
XR_LEG, _ = xray_mat("XrLeg", (0.3, 0.7, 1.0), 2.5, power=1.0, base=0.15)
lab_beetle = make_beetle("LabBeetle", {"body": XR_BODY, "elytra": XR_ELY, "black": XR_BODY, "leg": XR_LEG}, sets=("lab",))
lab_beetle["root"].location = B0
for o in lab_beetle["all"]:
    if o.type == "MESH":
        no_bounce([o])
RES_A_M, RES_A_A, RES_A_S = fade_emit_mat("ResA", (0.05, 0.3, 1.0), 6.0)
RES_B_M, RES_B_A, RES_B_S = fade_emit_mat("ResB", (0.1, 1.0, 0.2), 6.0)
soften(RES_A_M)
soften(RES_B_M)
RES_A_C = B0 + V((-0.06, 0.0, 0.215))
RES_B_C = B0 + V((-0.19, 0.0, 0.145))
CHAMBER_C = B0 + V((-0.34, 0, 0.14))
res_a = sph("ResA", RES_A_C, 1.0, RES_A_M, u=32, v=16, scale=(0.09, 0.05, 0.04))
res_b = sph("ResB", RES_B_C, 1.0, RES_B_M, u=32, v=16, scale=(0.09, 0.05, 0.04))
CH_M, CH_A, CH_S = fade_emit_mat("Chamber", (1.0, 0.55, 0.15), 6.0)
soften(CH_M)
chamber_o = sph("Chamber", CHAMBER_C, 1.0, CH_M, u=32, v=16)
no_bounce([res_a, res_b, chamber_o])
SETS["lab"] += [res_a, res_b, chamber_o]
# ducts (thin glowing tubes) from each reservoir to the chamber
M_DUCT, _ = emit_mat("Duct", (0.4, 0.75, 1.0), 1.2)
for nm, c in (("DuctA", RES_A_C), ("DuctB", RES_B_C)):
    o = tube(nm, [c + V((-0.09, 0, 0)), (c + CHAMBER_C) / 2 + V((0, 0, 0.01)), CHAMBER_C + V((0.03, 0, 0))],
             [0.007, 0.006, 0.006], M_DUCT, seg=8)
    no_bounce([o])
    SETS["lab"].append(o)
# flowing droplets (blue + green) travelling down the ducts
drops = []
for k in range(12):
    src = RES_A_C if k % 2 == 0 else RES_B_C
    mat = emit_mat(f"Drop{k}", (0.3, 0.6, 1.0) if k % 2 == 0 else (0.3, 1.0, 0.45), 8.0)[0]
    o = sph(f"Drop{k}", src, 0.014, mat, u=12, v=6)
    no_bounce([o])
    SETS["lab"].append(o)
    drops.append((o, src, (k // 2) / 6.0))
lab_puffs = make_puffs("LabPuff", PUFF_N, "lab", color=(1.0, 0.75, 0.45), strength=3.0)
lab_l = bpy.data.lights.new("LabLight", "POINT")
lab_l.color, lab_l.shadow_soft_size = (1.0, 0.6, 0.3), 0.05
lab_lo = bpy.data.objects.new("LabLight", lab_l)
lab_lo.location = CHAMBER_C
col.objects.link(lab_lo)
SETS["lab"].append(lab_lo)
# faint blueprint grid floor
M_GRID, nt_gr, out_gr = new_mat("Grid")
tgr = node(nt_gr, "ShaderNodeTexCoord")
bri = node(nt_gr, "ShaderNodeTexBrick", Scale=2.0, **{"Mortar Size": 0.008})
bri.offset = 0.0
bri.squash = 1.0
nt_gr.links.new(tgr.outputs["Object"], bri.inputs["Vector"])
bri.inputs["Color1"].default_value = (0.0, 0.0, 0.0, 1)
bri.inputs["Color2"].default_value = (0.0, 0.0, 0.0, 1)
bri.inputs["Mortar"].default_value = (1, 1, 1, 1)
bri.inputs["Brick Width"].default_value = 0.25
bri.inputs["Row Height"].default_value = 0.25
gem = node(nt_gr, "ShaderNodeEmission", Color=(0.1, 0.35, 0.6, 1), Strength=0.12)
gtr = node(nt_gr, "ShaderNodeBsdfTransparent")
gmx = nt_gr.nodes.new("ShaderNodeMixShader")
nt_gr.links.new(bri.outputs["Color"], gmx.inputs[0])
nt_gr.links.new(gtr.outputs[0], gmx.inputs[1])
nt_gr.links.new(gem.outputs[0], gmx.inputs[2])
nt_gr.links.new(gmx.outputs[0], out_gr.inputs[0])
gridm = bpy.data.meshes.new("LabGrid")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=2, y_segments=2, size=6)
bm.to_mesh(gridm)
bm.free()
grid_o = bpy.data.objects.new("LabGrid", gridm)
grid_o.location = B0 + V((0, 0, -0.005))
grid_o.data.materials.append(M_GRID)
col.objects.link(grid_o)
no_bounce([grid_o])
SETS["lab"].append(grid_o)

# ================================================================= XRAY set: inside the toad
X0 = V(T.XRAY)
XT_SKIN, _ = xray_mat("XtSkin", (0.25, 0.65, 1.0), 1.6, power=1.5, base=0.0)
XT_EYE, _ = xray_mat("XtEye", (0.5, 0.85, 1.0), 2.5, power=1.0, base=0.1)
XT_LEG, _ = xray_mat("XtLeg", (0.25, 0.6, 1.0), 1.4, power=1.5, base=0.0)
xtoad = make_toad("XToad", {"skin": XT_SKIN, "gland": XT_SKIN, "eye": XT_EYE, "mouth": XT_SKIN, "leg": XT_LEG},
                  sets=("xray",))
XTOAD_LOC = X0 + V((4.0, 0, 0))
xtoad["root"].location = XTOAD_LOC
xtoad["root"].rotation_euler = (0, 0, math.pi)
for o in xtoad["all"]:
    if o.type == "MESH":
        no_bounce([o])
# skeleton hints (spine + skull), stomach, the glowing beetle inside
M_BONE, _ = xray_mat("Bone", (0.85, 0.95, 1.0), 1.2, power=1.0, base=0.25)
STOMACH_M, STOMACH_A, STOMACH_S = fade_emit_mat("Stomach", (1.0, 0.4, 0.3), 2.5)
soften(STOMACH_M)
stomach = sph("Stomach", (0.15, 0, 0.85), 1.0, STOMACH_M, u=40, v=20, scale=(0.75, 0.55, 0.45))
stomach.parent = xtoad["body"]
no_bounce([stomach])
SETS["xray"] += [stomach]
M_INB, _ = emit_mat("InsideBeetle", (1.0, 0.6, 0.12), 6.0)
M_INB2, _ = emit_mat("InsideBeetle2", (0.5, 0.25, 0.05), 2.0)
in_beetle = make_beetle("InBeetle", {"body": M_INB, "elytra": M_INB2, "black": M_INB2, "leg": M_INB}, sets=("xray",))
in_beetle["root"].parent = xtoad["body"]
in_beetle["root"].location = (0.15, 0, 0.72)
in_beetle["root"].rotation_euler = (0.3, 0.2, 2.6)
in_beetle["root"].scale = (0.9,) * 3
BOOM_M, BOOM_A, BOOM_S = fade_emit_mat("Boom", (1.0, 0.85, 0.55), 20.0)
soften(BOOM_M)
boom_o = sph("Boom", (0.0, 0, 0.0), 1.0, BOOM_M, u=32, v=16)
boom_o.parent = in_beetle["tip"]
no_bounce([boom_o])
SETS["xray"].append(boom_o)
boom_l = bpy.data.lights.new("BoomLight", "POINT")
boom_l.color, boom_l.shadow_soft_size = (1.0, 0.7, 0.4), 0.1
boom_lo = bpy.data.objects.new("BoomLight", boom_l)
boom_lo.location = XTOAD_LOC + V((-0.15, 0, 0.75))
col.objects.link(boom_lo)
SETS["xray"].append(boom_lo)
xgrid = grid_o.copy()
xgrid.location = X0 + V((0, 0, -0.005))
xgrid.scale = (2.0, 2.0, 1.0)
col.objects.link(xgrid)
SETS["xray"].append(xgrid)

# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.sensor_width = 36
cam_d.clip_start = 0.01
cam_d.clip_end = 500
cam_d.dof.use_dof = True
cam = bpy.data.objects.new("Cam", cam_d)
cam.rotation_mode = "QUATERNION"
col.objects.link(cam)
scene.camera = cam

# ================================================================= keyframes
CUR = [0]


def key(o, path, value=None):
    if value is not None:
        setattr(o, path, value)
    o.keyframe_insert(path, frame=CUR[0])


def key_socket(sock, value):
    sock.default_value = value
    sock.keyframe_insert("default_value", frame=CUR[0])


WALK_SPEED = 0.2
WALK2 = T.T_REVEAL - 0.3                         # walking again when the toad shot starts
STRIDE = 0.11


def beetle_state(t):
    """(location, heading, roll, walked distance, wiggle, visible) of the ground beetle."""
    if t < T.T_TONGUE:
        if t < T.L["temp"][0]:
            walked = WALK_SPEED * (min(t, T.T_SPRAY1) + max(0.0, t - (T.T_SPRAY1 + 0.95)))
            x = -0.3 + walked
        else:
            walked = WALK_SPEED * max(0.0, t - WALK2)
            x = 0.12 + walked
        return G0 + V((x, 0.05, 0)), 0.0, 0.0, walked, 0.0, True
    if t < T.T_EJECT:                                   # on the tongue, then inside the toad
        start = G0 + V((0.12 + WALK_SPEED * (T.T_TONGUE - WALK2), 0.05, 0))
        u = T.smoother((t - T.T_TONGUE) / 0.22)
        p = start.lerp(MOUTH_W + V((0.1, 0, 0.05)), u)
        p.z += 0.06 * math.sin(math.pi * u)
        return p, 0.0, 0.0, 0.0, 1.0, t < T.T_TONGUE + 0.22
    tau = T.eject(t)                                    # thrown back up: arc, land on its back, flip, walk
    land = G0 + V((0.75, 0.6, 0.0))
    if tau < 0.45:
        u = tau / 0.45
        p = (MOUTH_W + V((0.05, 0, 0.05))).lerp(land + V((0, 0, 0.3)), u)
        p.z += 0.9 * math.sin(math.pi * u) * (1 - u * 0.3)
        return p, 0.4, math.pi * min(1, u * 1.1), 0.0, 1.0, True
    fl = T.flip(t)
    hop = 0.18 * math.sin(math.pi * fl)
    walk_t = max(0.0, t - (T.T_ALIVE + 0.45))
    heading = 0.4 + (math.pi - 0.15 - 0.4) * T.smoother(walk_t / 0.8)
    walked = WALK_SPEED * 1.3 * max(0.0, walk_t - 0.3)
    p = land + V((math.cos(heading), math.sin(heading), 0)) * walked
    p.z = hop + 0.3 * (1 - fl)
    return p, heading, math.pi * (1 - fl), walked + walk_t * 0.15, (1 - fl), True


def ant_state(t):
    tau = T.ant_hit(t)
    if tau < 0:
        x = -0.95 - 1.05 * (-tau) / 1.0
        return G0 + V((x, 0.08, 0)), 0.0, (0, 0, 0), x * 12, 0.0
    if tau < 1.0:
        dr = 1.4 * (1 - math.exp(-3.5 * tau))
        z = max(0.0, 0.45 * math.sin(math.pi * min(1, tau / 0.55)))
        spin = 9.0 * (1 - math.exp(-3 * tau))
        return G0 + V((-0.95 - dr, 0.08 - 0.25 * tau, z)), 0.0, (0.4 * spin, spin, 0), 0.0, 1.0 - tau
    x = -2.35 - 1.6 * (tau - 1.0)
    return G0 + V((x, -0.17 - 0.2 * (tau - 1.0), 0)), math.pi + 0.2, (0, 0, 0), -x * 14, 0.0


prev_q = None
for f in range(T.NFRAMES):
    t = f / T.FPS
    CUR[0] = f
    st = T.shot_set(t)
    si = T.shot_index(t)
    for name, objs in SETS.items():
        for o in objs:
            key(o, "hide_render", name != st)
    key_socket(WORLD_STRENGTH, 1.0 if st == "ground" else 0.35)
    # ---- ground: beetle
    bl, bh, broll, walked, wig, bvis = beetle_state(t)
    key(beetle["root"], "location", bl)
    key(beetle["root"], "rotation_euler", (broll, 0, bh))
    sp = T.spray(t)
    pose_beetle(beetle, t, walked / STRIDE * 2 * math.pi, wiggle=wig, curl=0.25 * min(1, sp * 3))
    if st == "ground" and not bvis:
        for o in beetle["all"]:
            key(o, "hide_render", True)
    # spray from the nozzle (beetle faces +X while spraying)
    tip_w = bl + V((TIP.x - 0.03, 0, TIP.z + 0.02))
    ddir = V((-1.0, 0.0, 0.08))
    pose_puffs(ground_puffs, f, tip_w, ddir, T.spray, st == "ground")
    nf = sp * (0.75 + 0.25 * PUFF_JIT[f % 400][2] / 1.3)
    key(nozzle, "location", tip_w + V((-0.04, 0, 0)))
    key(nozzle, "scale", (max(1e-3, 0.03 + 0.07 * nf),) * 3)
    key_socket(NOZ_A, min(1.0, nf * 1.3))
    key(nozzle, "hide_render", st != "ground" or nf <= 0.01)
    key(spray_lo, "location", tip_w + V((-0.15, 0, 0.05)))
    spray_l.energy = 60.0 * nf
    spray_l.keyframe_insert("energy", frame=f)
    # ---- ground: ant
    al, ah, arot, aph, afl = ant_state(t)
    key(ant["root"], "location", al)
    key(ant["root"], "rotation_euler", (arot[0], arot[1], ah))
    pose_ant(ant, aph, flail=afl, t=t)
    if st == "ground" and (si > 1):
        for o in ant["all"]:
            key(o, "hide_render", True)
    # ---- ground: toad (only from the twist on)
    pose_toad(toad, t, eyes=T.toad_eyes(t), mouth=T.mouth(t), gulp=T.gulp(t), heave=T.retch(t))
    if st == "ground" and si < 4:
        for o in toad["all"]:
            key(o, "hide_render", True)
    tg = T.tongue(t)
    target = G0 + V((0.12 + WALK_SPEED * (T.T_TONGUE - WALK2) + 0.15, 0.05, 0.12))
    if T.T_TONGUE <= t < T.T_TONGUE + 0.25:          # the tongue stays stuck to the beetle while pulling back
        target = bl + V((0.12, 0, 0.14))
        tg = 1.0 if (target - MOUTH_W).length > 0.05 else 0.0
    dvec = target - MOUTH_W
    key(tongue_o, "location", MOUTH_W)
    key(tongue_o, "rotation_euler", dvec.to_track_quat("X", "Z").to_euler())
    key(tongue_o, "scale", (max(1e-3, dvec.length * tg), 1.0, 1.0))
    key(tongue_tip, "scale", (1.0 / max(1e-3, dvec.length * tg) if tg > 0.01 else 1.0, 1.0, 1.0))
    key(tongue_o, "hide_render", st != "ground" or tg <= 0.01)
    key(tongue_tip, "hide_render", st != "ground" or tg <= 0.01)
    # ---- lab
    pose_beetle(lab_beetle, t, 0.0, curl=0.2)
    c = T.chem(t)
    key_socket(RES_A_A, c)
    key_socket(RES_B_A, c)
    key_socket(RES_A_S, 2.0 + 5.0 * c * (1 - 0.4 * T.flow(t)))
    key_socket(RES_B_S, 2.0 + 5.0 * c * (1 - 0.4 * T.flow(t)))
    ch = T.chamber(t)
    key(chamber_o, "scale", (max(1e-3, 0.03 + 0.05 * ch),) * 3)
    key_socket(CH_A, min(1.0, ch * 1.4))
    key_socket(CH_S, 4.0 + 26.0 * ch)
    key(chamber_o, "hide_render", st != "lab" or ch <= 0.01)
    lab_l.energy = 25.0 * ch
    lab_l.keyframe_insert("energy", frame=f)
    fl_ = T.flow(t)
    for o, src, ph in drops:
        active = T.T_MIX <= t < T.T_BOOM + 3.5
        u = ((t - T.T_MIX) * 1.6 + ph) % 1.0
        a = src + V((-0.09, 0, 0))
        mid = (src + CHAMBER_C) / 2 + V((0, 0, 0.01))
        p = a.lerp(mid, u * 2) if u < 0.5 else mid.lerp(CHAMBER_C, (u - 0.5) * 2)
        key(o, "location", p)
        key(o, "hide_render", st != "lab" or not active)
    lab_tip = B0 + V((TIP.x - 0.03, 0, TIP.z + 0.02))
    pose_puffs(lab_puffs, f, lab_tip, V((-1.0, 0, 0.12)), T.lab_jet, st == "lab", reach=1.1, size=0.22)
    # ---- xray toad
    fp_ = T.fire_pulses(t)
    pose_toad(xtoad, t, eyes=1.0, gulp=0.0, heave=0.35 * fp_)
    pose_beetle(in_beetle, t, 0.0, wiggle=0.6, curl=0.2)
    key(boom_o, "scale", (max(1e-3, 0.04 + 0.35 * fp_),) * 3)
    key_socket(BOOM_A, min(1.0, fp_ * 1.4))
    key(boom_o, "hide_render", st != "xray" or fp_ <= 0.01)
    key_socket(STOMACH_S, 2.5 + 8.0 * fp_)
    boom_l.energy = 120.0 * fp_
    boom_l.keyframe_insert("energy", frame=f)
    # ---- camera
    loc, tgt, lens, fstop, focus, roll = T.camera(t)
    q = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y") @ Quaternion((0, 0, 1), math.radians(roll))
    if prev_q is not None and prev_q.dot(q) < 0:
        q.negate()
    prev_q = q.copy()
    key(cam, "location", loc)
    key(cam, "rotation_quaternion", q)
    cam_d.lens = lens
    cam_d.keyframe_insert("lens", frame=f)
    cam_d.dof.aperture_fstop = fstop
    cam_d.dof.keyframe_insert("aperture_fstop", frame=f)
    fp = {"beetle": bl + V((0, 0, 0.15)), "tip": tip_w, "lab": B0 + V((-0.1, 0, 0.17)),
          "chamber": CHAMBER_C, "toadeye": TOAD_LOC + V((-1.55, -0.5, 1.5)), "mouth": MOUTH_W + V((0.3, 0, 0)),
          "stomach": XTOAD_LOC + V((-0.15, 0, 0.85)), "landed": bl + V((0, 0, 0.1)),
          "walker": bl + V((0, 0, 0.15))}[focus]
    cam_d.dof.focus_distance = (Vector(loc) - fp).length
    cam_d.dof.keyframe_insert("focus_distance", frame=f)

for idb in (list(bpy.data.objects) + list(bpy.data.materials) + list(bpy.data.cameras) + list(bpy.data.worlds)
            + list(bpy.data.lights)):
    for owner in [idb] + ([idb.node_tree] if getattr(idb, "node_tree", None) else []):
        ad = getattr(owner, "animation_data", None)
        if ad and ad.action:
            for fc in getattr(ad.action, "fcurves", []):
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT" if fc.data_path == "hide_render" else "LINEAR"

# ================================================================= render
r = scene.render
r.engine = "CYCLES"
r.resolution_x, r.resolution_y = RES
r.resolution_percentage = 100
r.image_settings.file_format = "PNG"
r.use_motion_blur = False              # clean, sharp frames (lesson learned)
r.use_persistent_data = False
c = scene.cycles
c.device = "CPU"
c.use_adaptive_sampling = True
c.adaptive_threshold = 0.08
c.use_denoising = True
c.max_bounces = 4
c.diffuse_bounces = 2
c.glossy_bounces = 2
c.transparent_max_bounces = 12
c.transmission_bounces = 2
c.caustics_reflective = False
c.caustics_refractive = False
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.3
except Exception:
    pass
SPP = {"ground": 11, "lab": 10, "xray": 10}
for f in FRAMES:
    t = f / T.FPS
    scene.frame_set(f)
    c.samples = max(4, int(SPP[T.shot_set(t)] * QUALITY))
    path = os.path.join(OUT, f"f_{f:04d}.png")
    if not os.path.exists(path):
        r.filepath = path
        bpy.ops.render.render(write_still=True)
        print(f"rendered {f} ({T.shot_set(t)})", flush=True)
print("done")
