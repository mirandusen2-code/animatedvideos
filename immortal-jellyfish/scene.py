"""Blender scene for "This Jellyfish Can Live Forever" (procedural, Cycles, immediate-mode posing per frame).

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



SETS = {"ocean": [], "cells": []}
WATER = (0.012, 0.055, 0.085)
rng = random.Random(7)


def fog(mat, density=0.09, color=WATER):
    """Fake underwater haze: blend the surface towards the water colour with camera distance."""
    nt = mat.node_tree
    out = nt.nodes["Material Output"]
    src = out.inputs[0].links[0].from_socket
    cd = nt.nodes.new("ShaderNodeCameraData")
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = -density
    nt.links.new(cd.outputs["View Distance"], mul.inputs[0])
    ex = nt.nodes.new("ShaderNodeMath")
    ex.operation = "EXPONENT"
    nt.links.new(mul.outputs[0], ex.inputs[0])
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(ex.outputs[0], inv.inputs[1])
    em = node(nt, "ShaderNodeEmission", Color=(*color, 1), Strength=1.0)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(inv.outputs[0], mix.inputs[0])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return mat


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
    def __init__(self, name, verts, faces, mat, sets=("ocean",), smooth=True):
        self.o = obj_from(name, verts, faces, mat, smooth)
        self.n = len(verts)
        for s in sets:
            SETS[s].append(self.o)

    def set(self, verts):
        v = np.asarray(verts, np.float32).reshape(-1)
        self.o.data.vertices.foreach_set("co", v)
        self.o.data.update()


# ================================================================= world: open water
world = bpy.data.worlds.new("Water")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
for n_ in list(wnt.nodes):
    if n_.type != "OUTPUT_WORLD":
        wnt.nodes.remove(n_)
wtc = wnt.nodes.new("ShaderNodeTexCoord")
wsep = wnt.nodes.new("ShaderNodeSeparateXYZ")
wnt.links.new(wtc.outputs["Generated"], wsep.inputs[0])
wr = ramp(wnt, [(0.0, (0.001, 0.006, 0.012)), (0.45, (0.006, 0.03, 0.05)), (0.62, (0.02, 0.09, 0.13)),
                (1.0, (0.08, 0.26, 0.34))])
wmr = wnt.nodes.new("ShaderNodeMapRange")
wmr.inputs["From Min"].default_value = -1.0
wmr.inputs["From Max"].default_value = 1.0
wnt.links.new(wsep.outputs["Z"], wmr.inputs["Value"])
wnt.links.new(wmr.outputs["Result"], wr.inputs[0])
wbg = wnt.nodes.new("ShaderNodeBackground")
wbg.inputs["Strength"].default_value = 1.0
wnt.links.new(wr.outputs[0], wbg.inputs["Color"])
wnt.links.new(wbg.outputs[0], wnt.nodes["World Output"].inputs[0])

sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy, sun_d.color, sun_d.angle = 2.6, (0.7, 0.9, 1.0), 0.12
sun = bpy.data.objects.new("Sun", sun_d)
sun.rotation_euler = (math.radians(14), math.radians(-8), 0)
col.objects.link(sun)
SETS["ocean"].append(sun)

# ---------------------------------------------------------------- sea floor with moving caustics
floor_me = bpy.data.meshes.new("Floor")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=60, y_segments=60, size=12)
for v_ in bm.verts:
    x_, y_ = v_.co.x, v_.co.y
    v_.co.z = 0.05 * math.sin(x_ * 1.3) * math.sin(y_ * 1.1) + 0.03 * math.sin(x_ * 3.1 + y_ * 2.3) \
        + (0.25 * max(0.0, y_ - 2.5) ** 1.2 if y_ > 2.5 else 0.0)
bm.to_mesh(floor_me)
bm.free()
floor_me.shade_smooth()
floor = bpy.data.objects.new("Floor", floor_me)
col.objects.link(floor)
SETS["ocean"].append(floor)
fm, fnt, fout = new_mat("Sand")
fp = node(fnt, "ShaderNodeBsdfPrincipled", Roughness=0.9)
fp.inputs["Specular IOR Level"].default_value = 0.1
ftc = node(fnt, "ShaderNodeTexCoord")
fnz = node(fnt, "ShaderNodeTexNoise", Scale=1.6, Detail=2.0)
fnt.links.new(ftc.outputs["Object"], fnz.inputs["Vector"])
frp = ramp(fnt, [(0.35, (0.10, 0.10, 0.085)), (0.65, (0.22, 0.20, 0.16))])
fnt.links.new(fnz.outputs["Fac"], frp.inputs[0])
fvo = fnt.nodes.new("ShaderNodeTexVoronoi")
fvo.voronoi_dimensions = "3D"
fvo.feature = "DISTANCE_TO_EDGE"
fvo.inputs["Scale"].default_value = 1.9
fdn = node(fnt, "ShaderNodeTexNoise", Scale=0.8, Detail=0.0)
fnt.links.new(ftc.outputs["Object"], fdn.inputs["Vector"])
fdm = fnt.nodes.new("ShaderNodeVectorMath")
fdm.operation = "MULTIPLY_ADD"
fdm.inputs[1].default_value = (0.6, 0.6, 0.6)
fnt.links.new(fdn.outputs["Color"], fdm.inputs[0])
fnt.links.new(ftc.outputs["Object"], fdm.inputs[2])
fcz = fnt.nodes.new("ShaderNodeCombineXYZ")          # caustics drift: animated z offset (cheaper than 4D)
fva = fnt.nodes.new("ShaderNodeVectorMath")
fva.operation = "ADD"
fnt.links.new(fdm.outputs[0], fva.inputs[0])
fnt.links.new(fcz.outputs[0], fva.inputs[1])
fnt.links.new(fva.outputs[0], fvo.inputs["Vector"])
CAUSTIC_W = fcz.inputs["Z"]

fcr = ramp(fnt, [(0.0, (1.0, 1.0, 1.0)), (0.05, (0.0, 0.0, 0.0))])
fnt.links.new(fvo.outputs["Distance"], fcr.inputs[0])
fadd = fnt.nodes.new("ShaderNodeMix")
fadd.data_type = "RGBA"
fadd.blend_type = "ADD"
fadd.inputs["Factor"].default_value = 0.16
fnt.links.new(frp.outputs[0], fadd.inputs["A"])
fnt.links.new(fcr.outputs[0], fadd.inputs["B"])
fnt.links.new(fadd.outputs["Result"], fp.inputs["Base Color"])
fnz2 = node(fnt, "ShaderNodeTexNoise", Scale=40.0, Detail=1.0)
fnt.links.new(ftc.outputs["Object"], fnz2.inputs["Vector"])
fbp = node(fnt, "ShaderNodeBump", Strength=0.25, Distance=0.02)
fnt.links.new(fnz2.outputs["Fac"], fbp.inputs["Height"])
fnt.links.new(fbp.outputs["Normal"], fp.inputs["Normal"])
fnt.links.new(fp.outputs[0], fout.inputs[0])
floor.data.materials.append(fog(fm, 0.22))

rock_m, _ = principled("Rock", (0.10, 0.11, 0.10), rough=0.8, bump=0.6, bump_scale=6.0)
fog(rock_m, 0.16)
moss_m, _ = principled("Algae", (0.08, 0.20, 0.10), rough=0.7, bump=0.4, bump_scale=10.0)
fog(moss_m, 0.16)
rb = Builder()
mb = Builder()
for i in range(40):
    a_ = rng.uniform(0, 2 * math.pi)
    d_ = rng.uniform(0.7, 5.5)
    x_, y_ = d_ * math.cos(a_) + 0.15, d_ * math.sin(a_) + 1.25
    s_ = rng.uniform(0.06, 0.32) * (0.6 + 0.2 * d_)
    (mb if rng.random() < 0.25 else rb).sphere((x_, y_, 0.02), (s_ * rng.uniform(0.9, 1.6), s_, s_ * 0.6),
                                               rot=(0, 0, rng.uniform(0, 3)))
for b_, n_, m_ in ((rb, "Rocks", rock_m), (mb, "AlgaeRocks", moss_m)):
    if b_.v:
        o_ = b_.build(n_, m_)
        SETS["ocean"].append(o_)

weed_m, _ = principled("Weed", (0.10, 0.32, 0.14), rough=0.5, emit=(0.05, 0.25, 0.1), emit_s=0.15)
fog(weed_m, 0.16)
WEEDS = []
for i in range(14):
    a_ = rng.uniform(0, 2 * math.pi)
    d_ = rng.uniform(1.2, 4.5)
    base_ = (d_ * math.cos(a_) + 0.15, d_ * math.sin(a_) + 1.4, 0.0)
    h_ = rng.uniform(0.6, 1.6)
    n_pts = 10
    pts = [(base_[0], base_[1], h_ * k / (n_pts - 1)) for k in range(n_pts)]
    rad = [0.035 * (1 - 0.7 * k / (n_pts - 1)) for k in range(n_pts)]
    dy = Dyn(f"weed{i}", tube_verts(pts, rad, 6), tube_faces(n_pts, 6), weed_m)
    WEEDS.append((dy, base_, h_, rng.uniform(0, 6), n_pts, rad))


def pose_weeds(t):
    for dy, base_, h_, ph, n_pts, rad in WEEDS:
        pts = []
        for k in range(n_pts):
            u = k / (n_pts - 1)
            sw = 0.12 * u * u * math.sin(t * 1.1 + ph + u * 1.5)
            pts.append((base_[0] + sw, base_[1] + 0.5 * sw, h_ * u))
        dy.set(tube_verts(pts, rad, 6))


# ---------------------------------------------------------------- light shafts + marine snow
ray_m, RAY_A, _ = fade_emit_mat("Rays", (0.55, 0.85, 1.0), 1.0)
soften(ray_m)
RAY_A.default_value = 0.06
for i in range(7):
    x_ = rng.uniform(-3.0, 3.0)
    y_ = rng.uniform(1.5, 6.0)
    r_ = rng.uniform(0.25, 0.7)
    o_ = tube(f"ray{i}", [(x_ + 1.6, y_ + 0.4, 9.0), (x_, y_, -0.5)], [r_ * 1.3, r_], ray_m, seg=24)
    o_.visible_shadow = False
    no_bounce([o_])
    SETS["ocean"].append(o_)

snow_m, _ = emit_mat("Snow", (0.75, 0.9, 1.0), 1.2)
sb = Builder()
SNOW_VF = sphere_vf(6, 4)
for i in range(520):
    p_ = (rng.uniform(-3, 3), rng.uniform(-2.5, 5.0), rng.uniform(0.0, 4.0))
    s_ = rng.uniform(0.003, 0.009)
    sb.sphere(p_, (s_, s_, s_), vf=SNOW_VF)
snow = sb.build("Snow", snow_m)
snow.visible_shadow = False
no_bounce([snow])
SETS["ocean"].append(snow)


# ================================================================= the jellyfish (Turritopsis dohrnii)
NS, NR = 64, 22                     # bell segments / rings per surface
R_BELL, H_BELL = 0.40, 0.46
NT, NPT = 44, 16                    # tentacles / points per tentacle
CENTER = np.array([0.0, 0.0, 0.15])  # collapse centre (local)
BLOB_R = 0.14
TH_MAX = 1.72


def bell_faces():
    nrings = 2 * NR
    f = []
    for i in range(nrings - 1):
        for k in range(NS):
            f.append([i * NS + k, i * NS + (k + 1) % NS, (i + 1) * NS + (k + 1) % NS, (i + 1) * NS + k])
    a0, a1 = nrings * NS, nrings * NS + 1
    for k in range(NS):
        f.append([(k + 1) % NS, k, a0])
        f.append([(nrings - 1) * NS + k, (nrings - 1) * NS + (k + 1) % NS, a1])
    return f


ANG = np.linspace(0, 2 * np.pi, NS, endpoint=False)
RAGGED = np.array([0.5 + 0.5 * math.sin(3 * a + 1) * math.sin(7 * a) for a in ANG])


def profile(s, p, ag):
    th = 0.04 + s * (TH_MAX - 0.04)
    r = R_BELL * np.sin(th) * (1 - 0.24 * p * s ** 1.5)
    z = H_BELL * np.cos(th) * (1 + 0.10 * p) * (1 - 0.12 * ag)
    return r, z


def bell_verts(p, ag, m):
    rings = []
    ss = np.linspace(0, 1, NR)
    for s in ss:                                       # outer surface, apex -> margin
        r, z = profile(s, p, ag)
        rr = r * (1 - 0.07 * ag * RAGGED * s ** 3)
        rings.append(np.stack([rr * np.cos(ANG), rr * np.sin(ANG), np.full(NS, z)], 1))
    for s in ss[::-1]:                                 # inner surface, margin -> apex
        r, z = profile(s, p, ag)
        rr = r * 0.86 * (1 - 0.07 * ag * RAGGED * s ** 3)
        rings.append(np.stack([rr * np.cos(ANG), rr * np.sin(ANG), np.full(NS, z * 0.80 - 0.035)], 1))
    v = np.concatenate(rings)
    _, z0 = profile(0, p, ag)
    v = np.concatenate([v, [[0, 0, z0 + 0.004], [0, 0, z0 * 0.80 - 0.035]]])
    return collapse(v, m)


def collapse(v, m, r=BLOB_R):
    if m <= 0:
        return v
    d = v - CENTER
    n = np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    tgt = CENTER + d / n * r * (1 + 0.08 * np.sin(5 * d[:, :1] / n + 3 * d[:, 1:2] / n))
    return v + (tgt - v) * m


def canal_paths(p, ag):
    out = []
    ss = np.linspace(0.05, 0.98, 12)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        pts = []
        for s in ss:
            r, z = profile(s, p, ag)
            pts.append((r * 0.93 * math.cos(a), r * 0.93 * math.sin(a), z * 0.9 - 0.017))
        out.append(np.array(pts))
    r, z = profile(0.985, p, ag)
    ring = [(r * 0.93 * math.cos(a), r * 0.93 * math.sin(a), z * 0.9 - 0.017)
            for a in np.linspace(0, 2 * math.pi, 49)]
    out.append(np.array(ring))
    return out


TORN = {i for i in range(NT) if i % 6 in (1, 2)}
T_PHASE = [rng.uniform(0, 6.28) for _ in range(NT)]
T_LEN = [rng.uniform(0.85, 1.15) for _ in range(NT)]


def tentacle_paths(t, p, ag, hu, m, length=0.95):
    out = []
    r0, z0 = profile(0.99, p, ag)
    for i in range(NT):
        a = 2 * math.pi * (i + 0.5) / NT
        Lt = length * T_LEN[i] * (1 - 0.45 * ag) * (1 - m) * ((1 - 0.65 * hu) if i in TORN else 1.0)
        Lt = max(Lt, 0.004)
        pts = []
        for k in range(NPT):
            u = k / (NPT - 1)
            flare = (0.30 * (1 - p) + 0.06) * u ** 0.8 - 0.12 * p * u
            da = 0.07 * u * math.sin(1.7 * t + 3.2 * u + T_PHASE[i])
            rr = r0 * 0.97 * (1 + flare) + 0.03 * u * math.sin(2.3 * t + 2 * u + T_PHASE[i] * 1.7)
            pts.append((rr * math.cos(a + da), rr * math.sin(a + da), z0 - 0.01 - Lt * u))
        out.append(np.array(pts))
    return out


T_RAD = np.array([0.0052 * (1 - 0.65 * k / (NPT - 1)) + 0.0012 for k in range(NPT)])


class Jelly:
    def __init__(self, name):
        self.bell_m, self.bell_s = xray_mat(f"{name}_bellm", (0.70, 0.90, 1.0), 2.2, power=1.6, base=0.04)
        self.gut_m, self.gut_p = principled(f"{name}_gutm", (0.85, 0.08, 0.04), rough=0.35, coat=0.6,
                                            emit=(1.0, 0.12, 0.05), emit_s=1.4, bump=0.15, bump_scale=20)
        self.ten_m, self.ten_a, self.ten_s = fade_emit_mat(f"{name}_tenm", (1.0, 0.93, 0.86), 1.4)
        self.ten_a.default_value = 0.85
        self.bell = Dyn(f"{name}_bell", bell_verts(0, 0, 0), bell_faces(), self.bell_m)
        cp = canal_paths(0, 0)
        cv, cf = [], []
        for pts in cp:
            cf += tube_faces(len(pts), 6, sum(len(x) for x in cv))
            cv.append(tube_verts(pts, np.full(len(pts), 0.011), 6))
        self.canals = Dyn(f"{name}_canals", np.concatenate(cv), cf, self.gut_m)
        gb = Builder()
        for k in range(4):                                    # four-lobed stomach (manubrium)
            a = k * math.pi / 2 + math.pi / 4
            gb.sphere((0.045 * math.cos(a), 0.045 * math.sin(a), 0.06), (0.05, 0.05, 0.09))
        gb.sphere((0, 0, 0.13), (0.07, 0.07, 0.07))
        gb.sphere((0, 0, -0.02), (0.035, 0.035, 0.05))
        self.gut = gb.build(f"{name}_gut", self.gut_m)
        SETS["ocean"].append(self.gut)
        tp = tentacle_paths(0, 0, 0, 0, 0)
        tv, tf = [], []
        for pts in tp:
            tf += tube_faces(NPT, 5, sum(len(x) for x in tv))
            tv.append(tube_verts(pts, T_RAD, 5, ref=(0, 0, 1)))
        self.tents = Dyn(f"{name}_tents", np.concatenate(tv), tf, self.ten_m)
        for o in (self.bell.o, self.tents.o):
            o.visible_shadow = False
        self.objs = [self.bell.o, self.canals.o, self.gut, self.tents.o]

    def pose(self, t, loc, scale=1.0, p=0.0, ag=0.0, hu=0.0, m=0.0, glow=0.0, tilt=(0, 0, 0), squash=1.0):
        self.bell.set(bell_verts(p, ag, m))
        cv = [collapse(tube_verts(pts, np.full(len(pts), 0.011 * (1 - 0.3 * m)), 6), m, BLOB_R * 0.9)
              for pts in canal_paths(p, ag)]
        self.canals.set(np.concatenate(cv))
        tv = [collapse(tube_verts(pts, T_RAD * (1 - 0.8 * m), 5, ref=(0, 0, 1)), m, BLOB_R * 0.95)
              for pts in tentacle_paths(t, p, ag, hu, m)]
        self.tents.set(np.concatenate(tv))
        gs = 1 + 0.3 * m
        for o in self.objs:
            o.location = loc
            o.rotation_euler = tilt
            o.scale = (scale, scale, scale * squash)
        self.gut.scale = (scale * gs, scale * gs, scale * gs * 0.9 * squash)
        self.gut.location = (loc[0], loc[1], loc[2] + scale * 0.15 * m * 0.0)
        # colours: vivid when young, pale when old, glowing when renewed
        young = 1 - ag
        self.bell_s.default_value = (0.9 + 1.3 * young) * (1 + 1.5 * glow)
        self.gut_p.inputs["Emission Strength"].default_value = (0.35 + 1.05 * young + 0.9 * m * (1 - young)) * (1 + 2 * glow)
        self.gut_p.inputs["Base Color"].default_value = (0.85 * (0.6 + 0.4 * young), 0.08 + 0.12 * ag, 0.04 + 0.1 * ag, 1)
        self.ten_s.default_value = (0.5 + 0.9 * young) * (1 + glow)
        self.ten_a.default_value = 0.85 * (1 - 0.3 * ag)

    def show(self, on):
        for o in self.objs:
            o.hide_render = not on
        if on and self.tents.o.scale.x < 0:
            pass


HERO_J = Jelly("hero")
BUD_J = Jelly("bud")


# ================================================================= polyp colony (the "baby" stage)
poly_m, poly_p = principled("Polyp", (0.95, 0.62, 0.52), rough=0.4, coat=0.5, emit=(1.0, 0.5, 0.4), emit_s=0.35)
hyd_m, _ = principled("Hydranth", (0.9, 0.18, 0.08), rough=0.35, coat=0.6, emit=(1.0, 0.2, 0.08), emit_s=0.9)
crown_m, CROWN_A, _ = fade_emit_mat("Crown", (1.0, 0.92, 0.85), 1.3)
FX, FY, _FZ = T.FLOOR_SPOT
STOLONS = [(math.radians(a), L_) for a, L_ in ((20, 0.55), (150, 0.45), (260, 0.5))]
NSP = 12


def stolon_paths(g):
    out = []
    for a, L_ in STOLONS:
        pts = []
        for k in range(NSP):
            u = k / (NSP - 1) * max(g, 0.02)
            w = 0.06 * math.sin(u * 6 + a)
            pts.append((FX + L_ * u * math.cos(a) - w * math.sin(a), FY + L_ * u * math.sin(a) + w * math.cos(a),
                        0.035 + 0.01 * math.sin(u * 9)))
        out.append(np.array(pts))
    return out


def stalk_path(g, t):
    pts = []
    for k in range(14):
        u = k / 13
        h = T.POLYP_H * g * u
        sw = 0.02 * u * math.sin(t * 1.3)
        pts.append((FX + 0.03 * math.sin(u * 3) + sw, FY + 0.02 * math.sin(u * 2), 0.06 + h))
    return np.array(pts)


def stolon_all(g):
    return np.concatenate([tube_verts(p_, np.full(NSP, 0.016 * (0.3 + 0.7 * min(1, g * 3))), 6)
                           for p_ in stolon_paths(g)])


stol_faces = []
for i in range(3):
    stol_faces += tube_faces(NSP, 6, i * (NSP * 6 + 2))
STOL = Dyn("Stolons", stolon_all(0.5), stol_faces, poly_m)
STALK = Dyn("Stalk", tube_verts(stalk_path(0.5, 0), np.full(14, 0.02), 8), tube_faces(14, 8), poly_m)
HYD = sph("Hydranth", (0, 0, 0), 1.0, hyd_m, u=24, v=14)
SETS["ocean"].append(HYD)
NCR, NCP = 14, 7


def crown_paths(top, open_, g):
    out = []
    for i in range(NCR):
        a = 2 * math.pi * i / NCR
        pts = []
        for k in range(NCP):
            u = k / (NCP - 1)
            el = math.radians(85 - 70 * open_) - 0.5 * u * open_
            Lc = 0.24 * g
            pts.append((top[0] + 0.05 * math.cos(a) + Lc * u * math.cos(el) * math.cos(a),
                        top[1] + 0.05 * math.sin(a) + Lc * u * math.cos(el) * math.sin(a),
                        top[2] + Lc * u * math.sin(el) - 0.02 * u * u * open_))
        out.append(np.array(pts))
    return out


crown_faces = []
for i in range(NCR):
    crown_faces += tube_faces(NCP, 5, i * (NCP * 5 + 2))
CROWN_RAD = np.array([0.0065 * (1 - 0.6 * k / (NCP - 1)) + 0.001 for k in range(NCP)])
CROWN = Dyn("Crown", np.concatenate([tube_verts(p_, CROWN_RAD, 5, ref=(0, 0, 1)) for p_ in crown_paths((0, 0, 0.5), 0, 1)]),
            crown_faces, crown_m)
CROWN.o.visible_shadow = False
POLYP_OBJS = [STOL.o, STALK.o, HYD, CROWN.o]


def pose_polyp(t):
    g = T.polyp(t)
    STOL.set(stolon_all(T.stolon(t)))
    sp = stalk_path(g, t)
    STALK.set(tube_verts(sp, np.full(14, 0.026 * (0.5 + 0.5 * g)), 8))
    top = sp[-1]
    HYD.location = (top[0], top[1], top[2] + 0.03 * g)
    HYD.scale = (0.06 * g + 0.001, 0.06 * g + 0.001, 0.10 * g + 0.001)
    CROWN.set(np.concatenate([tube_verts(p_, CROWN_RAD * max(g, 0.05), 5, ref=(0, 0, 1))
                              for p_ in crown_paths((top[0], top[1], top[2] + 0.06 * g), T.crown(t), g)]))
    return sp


# ================================================================= the fish (for the loop line)
fish_m, _ = principled("Fish", (0.42, 0.50, 0.55), rough=0.3, coat=0.7)
fm2 = fish_m.node_tree
_fp = next(n_ for n_ in fm2.nodes if n_.type == "BSDF_PRINCIPLED")
_ftc = node(fm2, "ShaderNodeTexCoord")
_fsx = fm2.nodes.new("ShaderNodeSeparateXYZ")
fm2.links.new(_ftc.outputs["Object"], _fsx.inputs[0])
_fmr = node(fm2, "ShaderNodeMapRange", **{"From Min": -0.05, "From Max": 0.12})
fm2.links.new(_fsx.outputs["Z"], _fmr.inputs["Value"])
_frp = ramp(fm2, [(0.0, (0.75, 0.78, 0.78)), (0.6, (0.30, 0.42, 0.50)), (1.0, (0.10, 0.18, 0.25))])
fm2.links.new(_fmr.outputs["Result"], _frp.inputs[0])
fm2.links.new(_frp.outputs[0], _fp.inputs["Base Color"])
_fp.inputs["Metallic"].default_value = 0.35
fog(fish_m, 0.12)
fin_m, _ = principled("Fin", (0.55, 0.65, 0.72), rough=0.4, emit=(0.4, 0.6, 0.7), emit_s=0.1)
fog(fin_m, 0.12)
eye_w, _ = principled("FishEye", (0.9, 0.85, 0.6), rough=0.05, coat=1.0)
eye_b, _ = principled("FishPupil", (0.0, 0.0, 0.0), rough=0.05, coat=1.0)
fish_root = empty("FishRoot", (3, 3, 2))
fb = Builder()
fb.sphere((0, 0, 0), (0.42, 0.11, 0.16))
fb.sphere((0.22, 0, -0.01), (0.2, 0.1, 0.13))
fbody = fb.build("FishBody", fish_m)
fbody.parent = fish_root
fin_b = Builder()
fin_b.sphere((-0.02, 0, 0.17), (0.18, 0.012, 0.07), rot=(0, 0.25, 0))
fin_b.sphere((0.05, 0, -0.16), (0.1, 0.01, 0.04), rot=(0, -0.3, 0))
for sy in (1, -1):
    fin_b.sphere((0.2, sy * 0.1, -0.06), (0.09, 0.008, 0.035), rot=(0.4 * sy, 0.5, 0.5 * sy))
fins = fin_b.build("FishFins", fin_m)
fins.parent = fish_root
tail_p = empty("FishTailP", (-0.38, 0, 0), fish_root)
tb = Builder()
tb.sphere((-0.14, 0, 0.07), (0.15, 0.01, 0.06), rot=(0, -0.55, 0))
tb.sphere((-0.14, 0, -0.07), (0.15, 0.01, 0.06), rot=(0, 0.55, 0))
tail = tb.build("FishTail", fin_m)
tail.parent = tail_p
jaw_p = empty("FishJawP", (0.34, 0, -0.03), fish_root)
jb = Builder()
jb.sphere((0.04, 0, -0.01), (0.08, 0.07, 0.025))
jaw = jb.build("FishJaw", fish_m)
jaw.parent = jaw_p
eyes = []
for sy in (1, -1):
    e1 = sph(f"feye{sy}", (0.3, sy * 0.075, 0.04), 0.032, eye_w, u=20, v=12)
    e2 = sph(f"fpup{sy}", (0.305, sy * 0.098, 0.042), 0.016, eye_b, u=16, v=10)
    e1.parent = e2.parent = fish_root
    eyes += [e1, e2]
FISH_OBJS = [fbody, fins, tail, jaw] + eyes
SETS["ocean"].extend(FISH_OBJS)


# ================================================================= CELLS set: old cells become new ones
C0 = V(T.CELLS)
cell_m, cnt, cout = new_mat("Cell")
c_attr = cnt.nodes.new("ShaderNodeAttribute")
c_attr.attribute_name = "renew"
c_ramp = ramp(cnt, [(0.0, (0.55, 0.32, 0.18)), (1.0, (0.15, 0.8, 1.0))])
cnt.links.new(c_attr.outputs["Fac"], c_ramp.inputs[0])
c_str = cnt.nodes.new("ShaderNodeMapRange")
c_str.inputs["To Min"].default_value = 0.6
c_str.inputs["To Max"].default_value = 1.5
cnt.links.new(c_attr.outputs["Fac"], c_str.inputs["Value"])
c_em = cnt.nodes.new("ShaderNodeEmission")
cnt.links.new(c_ramp.outputs[0], c_em.inputs["Color"])
cnt.links.new(c_str.outputs["Result"], c_em.inputs["Strength"])
c_tr = cnt.nodes.new("ShaderNodeBsdfTransparent")
c_lw = node(cnt, "ShaderNodeLayerWeight", Blend=0.5)
c_pw = cnt.nodes.new("ShaderNodeMath")
c_pw.operation = "POWER"
c_pw.inputs[1].default_value = 1.4
cnt.links.new(c_lw.outputs["Facing"], c_pw.inputs[0])
c_ad = cnt.nodes.new("ShaderNodeMath")
c_ad.operation = "ADD"
c_ad.use_clamp = True
c_ad.inputs[1].default_value = 0.12
cnt.links.new(c_pw.outputs[0], c_ad.inputs[0])
c_mix = cnt.nodes.new("ShaderNodeMixShader")
cnt.links.new(c_ad.outputs[0], c_mix.inputs[0])
cnt.links.new(c_tr.outputs[0], c_mix.inputs[1])
cnt.links.new(c_em.outputs[0], c_mix.inputs[2])
cnt.links.new(c_mix.outputs[0], cout.inputs[0])

nuc_m, nnt, nout = new_mat("Nucleus")
n_attr = nnt.nodes.new("ShaderNodeAttribute")
n_attr.attribute_name = "renew"
n_ramp = ramp(nnt, [(0.0, (0.45, 0.2, 0.1)), (1.0, (0.45, 1.0, 1.0))])
nnt.links.new(n_attr.outputs["Fac"], n_ramp.inputs[0])
n_str = nnt.nodes.new("ShaderNodeMapRange")
n_str.inputs["To Min"].default_value = 0.4
n_str.inputs["To Max"].default_value = 2.2
nnt.links.new(n_attr.outputs["Fac"], n_str.inputs["Value"])
n_em = nnt.nodes.new("ShaderNodeEmission")
nnt.links.new(n_ramp.outputs[0], n_em.inputs["Color"])
nnt.links.new(n_str.outputs["Result"], n_em.inputs["Strength"])
nnt.links.new(n_em.outputs[0], nout.inputs[0])

CELL_VF = sphere_vf(20, 12)
NUC_VF = sphere_vf(12, 8)
CELL_LIST = []
for layer, (yy, rr, nx, nz) in enumerate(((0.0, 0.105, 8, 15), (0.9, 0.16, 7, 11))):
    for j in range(nz):
        for i in range(nx):
            x_ = (i - (nx - 1) / 2 + (0.5 if j % 2 else 0)) * rr * 1.92 + rng.uniform(-0.01, 0.01)
            z_ = (j - (nz - 1) / 2) * rr * 1.68 + rng.uniform(-0.01, 0.01)
            CELL_LIST.append((x_, yy + rng.uniform(-0.03, 0.03), z_, rr * rng.uniform(0.93, 1.0), layer,
                              rng.uniform(0, 6.28)))
MAXD = max(math.hypot(c[0], c[2]) for c in CELL_LIST if c[4] == 0)


def cell_values(t):
    pr = T.renew(t)
    vals = []
    for x_, y_, z_, r_, layer, ph in CELL_LIST:
        d = math.hypot(x_, z_) / MAXD
        v = T.clamp((pr * 1.5 - d * 0.75 + 0.05 * math.sin(ph * 3)) / 0.18)
        vals.append(v)
    return vals


def cell_mesh(t, nucleus=False):
    vf = NUC_VF if nucleus else CELL_VF
    vv, _ff = vf
    out, cols = [], []
    for (x_, y_, z_, r_, layer, ph), v in zip(CELL_LIST, cell_values(t)):
        pop = 1 + 0.18 * math.sin(math.pi * v) + 0.02 * math.sin(t * 2 + ph)
        sc = np.array([r_, r_ * 0.75, r_ * 0.92]) * pop * (0.38 if nucleus else 1.0)
        out.append(vv * sc + np.array([x_ + C0.x, y_ + C0.y, z_ + C0.z]))
        cols.append(np.repeat([[v, v, v, 1.0]], len(vv), 0))
    return np.concatenate(out), np.concatenate(cols)


def cell_faces(nucleus=False):
    vv, ff = NUC_VF if nucleus else CELL_VF
    f = []
    for k in range(len(CELL_LIST)):
        f += [[i + k * len(vv) for i in fc] for fc in ff]
    return f


CELLS_D, NUC_D = [], []
for nuc, mat_ in ((False, cell_m), (True, nuc_m)):
    v_, c_ = cell_mesh(0, nuc)
    d_ = Dyn("Nuclei" if nuc else "Cells", v_, cell_faces(nuc), mat_, sets=("cells",))
    d_.o.data.color_attributes.new("renew", "FLOAT_COLOR", "POINT")
    (NUC_D if nuc else CELLS_D).append(d_)


def pose_cells(t):
    for d_, nuc in ((CELLS_D[0], False), (NUC_D[0], True)):
        v_, c_ = cell_mesh(t, nuc)
        d_.set(v_)
        d_.o.data.color_attributes["renew"].data.foreach_set("color", c_.astype(np.float32).reshape(-1))
        d_.o.data.update()


# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_width = 36
cam_d.dof.use_dof = True
cam = bpy.data.objects.new("Cam", cam_d)
cam.rotation_mode = "QUATERNION"
col.objects.link(cam)
scene.camera = cam


# ================================================================= per-frame posing
def blob_center_local(scale):
    return V(CENTER) * scale


def main_state(t):
    """Where the hero jellyfish is and what it is doing at time t."""
    s7 = T.SHOTS[7][0]
    if T.shot_index(t) == len(T.SHOTS) - 1:
        t = T.env_t(t)                             # last shot: same young swimmer as the opening (loop)
    elif t >= s7:                                    # the grown-up jellyfish (new life)
        shrink, glow, _n = T.cycle(t)
        bob = 0.03 * math.sin(t * 1.4)
        p = T.pulse(t % 1.05 + 0.0) if shrink < 0.05 else 0.0
        ph = ((t + 0.95) / 1.05) % 1.0
        p = math.sin(math.pi * T.clamp(ph / 0.35)) if ph < 0.35 else 0.0
        loc = (T.HERO[0], T.HERO[1], T.HERO[2] + bob)
        return dict(loc=loc, p=p * (1 - shrink), ag=0.0, hu=0.0, m=0.92 * shrink, glow=glow, squash=1.0)
    m = T.melt(t)
    sk = T.sink(t)
    hero_z = T.HERO[2] + 0.04 * math.sin(t * 1.3)
    land = (T.FLOOR_SPOT[0], T.FLOOR_SPOT[1], 0.11 - CENTER[2])
    x = T.lerp(T.HERO[0], land[0], sk)
    y = T.lerp(T.HERO[1], land[1], sk)
    z = T.lerp(hero_z, land[2], sk ** 1.3)
    squash = 1 - 0.3 * T.smoother((t - T.T_FLOOR + 0.1) / 0.3)
    return dict(loc=(x, y, z), p=T.pulse(t), ag=T.age(t) * (1 - 0.6 * m), hu=T.hurt(t), m=m, glow=0.0,
                squash=squash)


def pose(t):
    st = T.shot_set(t)
    for name, objs in SETS.items():
        for o in objs:
            o.hide_render = name != st
    te = T.env_t(t)
    CAUSTIC_W.default_value = te * 0.35
    snow.location = (0.02 * math.sin(te * 0.3), 0.0, -0.025 * te)
    if st == "cells":
        pose_cells(t)
        return
    pose_weeds(te)
    s = main_state(t)
    HERO_J.pose(te, s["loc"], 1.0, s["p"], s["ag"], s["hu"], s["m"], s["glow"],
                tilt=(0.06 * math.sin(te * 0.7), 0.05 * math.sin(te * 0.9), 0), squash=s["squash"])
    # polyp colony + bud only in the floor shots
    i = T.shot_index(t)
    floor_time = 4 <= i <= 6
    for o in POLYP_OBJS:
        o.hide_render = not floor_time
    sp = pose_polyp(t) if floor_time else None
    bud_on = i == 6 and T.bud(t) > 0.01
    for o in BUD_J.objs:
        o.hide_render = not bud_on
    if bud_on:
        b = T.bud(t)
        attach = sp[9]
        if not T.released(t):
            loc = (attach[0] + 0.07 * b, attach[1] - 0.02, attach[2] - 0.02)
            sc = 0.22 * b
            tilt = (0, 1.2 * (1 - b), 0)
            pb = 0.4 * math.sin(t * 9) ** 2 * b
        else:
            u = T.swim_up(t)
            loc = (attach[0] + 0.07 + 0.08 * T.ease_out(u / 0.8), attach[1] - 0.02,
                   attach[2] - 0.02 + 0.85 * T.ease_out(u / 1.1))
            sc = 0.22 + 0.12 * T.ease_out(u / 0.8)
            tilt = (0, 0.0, 0)
            ph = (u / 0.42) % 1.0
            pb = math.sin(math.pi * T.clamp(ph / 0.35)) if ph < 0.35 else 0.0
        BUD_J.pose(t, loc, sc, pb, 0.0, 0.0, 0.0, 0.3, tilt=tilt)
    # fish only in the last shot
    fon = i == 8
    for o in FISH_OBJS:
        o.hide_render = not fon
    if fon:
        pos = V(T.fish_pos(t))
        d = V(T.fish_pos(t + 0.04)) - V(T.fish_pos(t - 0.04))
        if d.length < 1e-4:
            d = V(T.FISH_PA) - V(T.FISH_P0)
        fish_root.location = pos
        fish_root.rotation_euler = (0, 0.05, math.atan2(d.y, d.x) + 0.12 * math.sin(t * 6))
        fish_root.scale = (1.3, 1.3, 1.3)
        tail_p.rotation_euler = (0, 0, 0.5 * math.sin(t * 9))
        jaw_p.rotation_euler = (0, 0.55 * T.fish_mouth(t), 0)


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
c.max_bounces = 6
c.diffuse_bounces = 2
c.glossy_bounces = 2
c.transparent_max_bounces = 24
c.transmission_bounces = 2
c.caustics_reflective = False
c.caustics_refractive = False
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.3
except Exception:
    pass
SPP = {"ocean": 8, "cells": 8}
if os.environ.get("JF_EXP"):                       # performance experiments
    exec(os.environ["JF_EXP"])
for f in FRAMES:
    t = f / T.FPS
    path = os.path.join(OUT, f"f_{f:04d}.png")
    if os.path.exists(path):
        continue
    pose(t)
    loc, tgt, lens, fstop, focus = T.camera(t)
    cam.location = loc
    cam.rotation_quaternion = (V(tgt) - V(loc)).to_track_quat("-Z", "Y")
    cam_d.lens = lens
    cam_d.dof.aperture_fstop = fstop
    s = main_state(t)
    fp_ = {"hero": V(s["loc"]) + V((0, 0, 0.1)), "blob": V(s["loc"]) + V(CENTER),
           "polyp": V((FX, FY, 0.3)), "cells": C0, "baby": V(BUD_J.bell.o.location)}[focus]
    cam_d.dof.focus_distance = (V(loc) - fp_).length
    scene.frame_set(f)
    c.samples = max(4, int(SPP[T.shot_set(t)] * QUALITY))
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"rendered {f} ({T.shot_set(t)})", flush=True)
print("done")
