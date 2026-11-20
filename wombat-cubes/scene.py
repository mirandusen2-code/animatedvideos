"""Blender scene for "Wombats Poop Cubes" (procedural, Cycles, immediate-mode posing per frame).

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
    def __init__(self, name, verts, faces, mat, sets=("field",), smooth=True):
        self.o = obj_from(name, verts, faces, mat, smooth)
        self.n = len(verts)
        for s in sets:
            SETS[s].append(self.o)

    def set(self, verts):
        v = np.asarray(verts, np.float32).reshape(-1)
        self.o.data.vertices.foreach_set("co", v)
        self.o.data.update()


# ================================================================= world: open water


# ================================================================= sets
SETS = {"field": [], "gut": []}
rng = random.Random(7)
HAZE = (0.055, 0.06, 0.12)          # night air colour for distance haze


def fog(mat, density=0.05, color=HAZE):
    """Distance haze: blend the surface towards the air colour with camera distance."""
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


def to_set(name, *objs):
    for o in objs:
        SETS[name].append(o)
    return objs[0] if len(objs) == 1 else objs


# ================================================================= world: dusk sky with stars
world = bpy.data.worlds.new("Sky")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
for n_ in list(wnt.nodes):
    if n_.type != "OUTPUT_WORLD":
        wnt.nodes.remove(n_)
wtc = wnt.nodes.new("ShaderNodeTexCoord")
wsep = wnt.nodes.new("ShaderNodeSeparateXYZ")
wnt.links.new(wtc.outputs["Generated"], wsep.inputs[0])
wmr = wnt.nodes.new("ShaderNodeMapRange")
wmr.inputs["From Min"].default_value = -0.2
wmr.inputs["From Max"].default_value = 1.0
wnt.links.new(wsep.outputs["Z"], wmr.inputs["Value"])
wr = ramp(wnt, [(0.0, (0.30, 0.17, 0.26)), (0.17, (0.20, 0.14, 0.30)), (0.35, (0.07, 0.07, 0.20)),
                (1.0, (0.010, 0.016, 0.055))])
wnt.links.new(wmr.outputs["Result"], wr.inputs[0])
wvo = wnt.nodes.new("ShaderNodeTexVoronoi")
wvo.inputs["Scale"].default_value = 260.0
wvo.inputs["Randomness"].default_value = 1.0
wnt.links.new(wtc.outputs["Generated"], wvo.inputs["Vector"])
wsr = ramp(wnt, [(0.0, (1.0, 1.0, 1.0)), (0.035, (0.0, 0.0, 0.0))])
wnt.links.new(wvo.outputs["Distance"], wsr.inputs[0])
wsm = wnt.nodes.new("ShaderNodeMath")                     # stars only where the voronoi cell is "bright" and high up
wsm.operation = "MULTIPLY"
wnt.links.new(wsr.outputs[0], wsm.inputs[0])
wnt.links.new(wvo.outputs["Color"], wsm.inputs[1])
wsh = wnt.nodes.new("ShaderNodeMath")
wsh.operation = "GREATER_THAN"
wsh.inputs[1].default_value = 0.45
wnt.links.new(wsm.outputs[0], wsh.inputs[0])
whz = wnt.nodes.new("ShaderNodeMapRange")
whz.inputs["From Min"].default_value = 0.08
whz.inputs["From Max"].default_value = 0.4
wnt.links.new(wsep.outputs["Z"], whz.inputs["Value"])
wst = wnt.nodes.new("ShaderNodeMath")
wst.operation = "MULTIPLY"
wnt.links.new(wsh.outputs[0], wst.inputs[0])
wnt.links.new(whz.outputs["Result"], wst.inputs[1])
wad = wnt.nodes.new("ShaderNodeMix")
wad.data_type = "RGBA"
wad.blend_type = "ADD"
wnt.links.new(wst.outputs[0], wad.inputs["Factor"])
wnt.links.new(wr.outputs[0], wad.inputs["A"])
wad.inputs["B"].default_value = (0.9, 0.95, 1.0, 1)
wbg = wnt.nodes.new("ShaderNodeBackground")
wbg.inputs["Strength"].default_value = 1.6
wnt.links.new(wad.outputs["Result"], wbg.inputs["Color"])
wnt.links.new(wbg.outputs[0], wnt.nodes["World Output"].inputs[0])
WORLD_S = wbg.inputs["Strength"]

MOON_DIR0 = V((-0.55, 0.75, 0.42)).normalized()     # moon up-left behind the wombat in the opening
moon_d = bpy.data.lights.new("MoonLight", "SUN")
moon_d.energy, moon_d.color, moon_d.angle = 4.0, (0.72, 0.82, 1.0), 0.04
moon_l = bpy.data.objects.new("MoonLight", moon_d)
col.objects.link(moon_l)
fill_d = bpy.data.lights.new("Fill", "SUN")
fill_d.energy, fill_d.color, fill_d.angle = 1.3, (1.0, 0.78, 0.66), 0.6
fill_l = bpy.data.objects.new("Fill", fill_d)
fill_l.rotation_euler = (V((0.3, -1.0, 0.35))).to_track_quat("Z", "Y").to_euler()
col.objects.link(fill_l)
moon_m, _ = emit_mat("Moon", (1.0, 0.97, 0.88), 6.0)
MOON = sph("Moon", (0, 0, 0), 1.0, moon_m, u=32, v=16)
MOON.visible_shadow = False
no_bounce([MOON])
to_set("field", moon_l, fill_l, MOON)


def set_moon(d, cam_loc):
    d = V(d).normalized()
    moon_l.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    MOON.location = V(cam_loc) + d * 60.0
    MOON.scale = (1.6, 1.6, 1.6)


# ================================================================= ground
def line_dist(x, y):
    """Distance to the bare paths: the opening walking line, the time-lapse route and the rock clearing."""
    px, py, _ = T.WALK_P0
    dx, dy, _ = T.WALK_D
    s = (x - px) * dx + (y - py) * dy
    d1 = abs(-(x - px) * dy + (y - py) * dx) if -4 < s < 6 else 9.0
    d2 = 9.0
    for k in range(41):
        qx, qy, _ = T.night_path(k / 40)
        d2 = min(d2, math.hypot(x - qx, y - qy))
    d3 = math.hypot(x - T.ROCK[0] - 0.3, y - T.ROCK[1]) - 0.45
    return min(d1, d2, d3)


G_C = (-2.5, -3.5)
ground_me = bpy.data.meshes.new("Ground")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=180, y_segments=180, size=22)


def ground_z(x, y):
    return 0.035 * math.sin(x * 1.1 + 0.4) * math.sin(y * 0.9) + 0.02 * math.sin(x * 2.7 + y * 1.9) \
        + (0.18 * max(0.0, y - 5.0) ** 1.15 if y > 5.0 else 0.0)


for v_ in bm.verts:
    x_, y_ = v_.co.x + G_C[0], v_.co.y + G_C[1]
    v_.co.x, v_.co.y = x_, y_
    v_.co.z = ground_z(x_, y_) * T.smoother((line_dist(x_, y_) - 0.5) / 1.0)
bm.to_mesh(ground_me)
bm.free()
ground_me.shade_smooth()
GROUND = bpy.data.objects.new("Ground", ground_me)
col.objects.link(GROUND)
to_set("field", GROUND)

gm, gnt, gout = new_mat("Ground")
gp = node(gnt, "ShaderNodeBsdfPrincipled", Roughness=0.95)
gp.inputs["Specular IOR Level"].default_value = 0.15
gtc = node(gnt, "ShaderNodeTexCoord")
gnz = node(gnt, "ShaderNodeTexNoise", Scale=0.9, Detail=3.0)
gnt.links.new(gtc.outputs["Object"], gnz.inputs["Vector"])
grp = ramp(gnt, [(0.38, (0.075, 0.058, 0.042)), (0.55, (0.13, 0.115, 0.07)), (0.7, (0.10, 0.11, 0.05))])
gnt.links.new(gnz.outputs["Fac"], grp.inputs[0])
gn2 = node(gnt, "ShaderNodeTexNoise", Scale=9.0, Detail=4.0)
gnt.links.new(gtc.outputs["Object"], gn2.inputs["Vector"])
gmx = gnt.nodes.new("ShaderNodeMix")
gmx.data_type = "RGBA"
gmx.blend_type = "MULTIPLY"
gmx.inputs["Factor"].default_value = 0.55
gnt.links.new(grp.outputs[0], gmx.inputs["A"])
gr2 = ramp(gnt, [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.25, 1.2, 1.1))])
gnt.links.new(gn2.outputs["Fac"], gr2.inputs[0])
gnt.links.new(gr2.outputs[0], gmx.inputs["B"])
gnt.links.new(gmx.outputs["Result"], gp.inputs["Base Color"])
gn3 = node(gnt, "ShaderNodeTexNoise", Scale=60.0, Detail=2.0)
gnt.links.new(gtc.outputs["Object"], gn3.inputs["Vector"])
gbp = node(gnt, "ShaderNodeBump", Strength=0.5, Distance=0.01)
gnt.links.new(gn3.outputs["Fac"], gbp.inputs["Height"])
gnt.links.new(gbp.outputs["Normal"], gp.inputs["Normal"])
gnt.links.new(gp.outputs[0], gout.inputs[0])
GROUND.data.materials.append(fog(gm, 0.045))


# ---------------------------------------------------------------- grass, pebbles, bushes, trees
grass_m, _ = principled("Grass", (0.17, 0.17, 0.075), rough=0.7)
grass_nt = grass_m.node_tree
gb = Builder()
blade_v = []
blade_f = []


def blade(x, y, h, w, lean, rot):
    o = len(blade_v)
    ca, sa = math.cos(rot), math.sin(rot)
    lx, ly = math.cos(lean[0]) * lean[1], math.sin(lean[0]) * lean[1]
    pts = []
    for k, (u, ww) in enumerate(((0, 1.0), (0.5, 0.7), (1.0, 0.0))):
        cx_ = x + lx * u * u
        cy_ = y + ly * u * u
        cz_ = h * u
        pts.append((cx_ - ca * w * ww, cy_ - sa * w * ww, cz_))
        pts.append((cx_ + ca * w * ww, cy_ + sa * w * ww, cz_))
    blade_v.extend(pts)
    blade_f.extend([[o, o + 1, o + 3, o + 2], [o + 2, o + 3, o + 5, o + 4]])


def tuft(x, y, n, hmax):
    for _ in range(n):
        bx, by = x + rng.gauss(0, 0.03), y + rng.gauss(0, 0.03)
        blade(bx, by, rng.uniform(0.4, 1.0) * hmax, rng.uniform(0.004, 0.007),
              (rng.uniform(0, 6.28), rng.uniform(0.0, 0.35) * hmax), rng.uniform(0, 6.28))


AREAS = [((-1.2, 3.8), (-1.4, 4.5), 1300),     # around the opening walking line (x range, y range, tufts)
         ((-9.0, -2.0), (-12.5, -6.0), 1500)]   # time-lapse meadow + rock
for (x0, x1), (y0, y1), ntf in AREAS:
    for _ in range(ntf):
        x_, y_ = rng.uniform(x0, x1), rng.uniform(y0, y1)
        d = line_dist(x_, y_)
        if d < 0.22:
            continue
        hmax = 0.07 + 0.22 * min(1.0, (d - 0.22) / 0.8) * rng.uniform(0.6, 1.0)
        tuft(x_, y_ + 0, rng.randint(5, 11), hmax)
GRASS = obj_from("Grass", blade_v, blade_f, fog(grass_m, 0.045), smooth=False)
to_set("field", GRASS)

peb_m, _ = principled("Pebble", (0.16, 0.15, 0.14), rough=0.8, bump=0.3, bump_scale=30)
fog(peb_m, 0.045)
pb = Builder()
for _ in range(500):
    x_, y_ = rng.uniform(-1.5, 4.0), rng.uniform(-1.6, 4.5)
    if rng.random() < 0.5:
        x_, y_ = rng.uniform(-9.0, -2.0), rng.uniform(-12.5, -6.0)
    if line_dist(x_, y_) < 0.1 and math.hypot(x_ - T.CUBE0[0], y_ - T.CUBE0[1]) < 0.35:
        continue
    s_ = rng.uniform(0.006, 0.02)
    pb.sphere((x_, y_, 0.0), (s_ * rng.uniform(1, 1.6), s_, s_ * 0.6), rot=(0, 0, rng.uniform(0, 3)))
to_set("field", pb.build("Pebbles", peb_m))

bush_m, _ = principled("Bush", (0.05, 0.06, 0.03), rough=0.8, bump=0.8, bump_scale=8)
fog(bush_m, 0.045)
bb = Builder()
bush_spots = [(rng.uniform(-6, 7), rng.uniform(3.5, 9)) for _ in range(18)] + \
             [(rng.uniform(-12, -1), rng.uniform(-15.5, -12.8)) for _ in range(12)] + \
             [(rng.uniform(-12.5, -9.5), rng.uniform(-12, -5)) for _ in range(6)]
for bx, by in bush_spots:
    for _ in range(rng.randint(3, 6)):
        r_ = rng.uniform(0.18, 0.45)
        bb.sphere((bx + rng.uniform(-0.4, 0.4), by + rng.uniform(-0.3, 0.3), r_ * 0.6), (r_ * 1.2, r_, r_ * 0.85))
to_set("field", bb.build("Bushes", bush_m))



# ================================================================= the rock (S5/S6)
rock_m, _ = principled("Rock", (0.085, 0.082, 0.078), rough=0.8, bump=0.9, bump_scale=9)
fog(rock_m, 0.045)
RX, RY, _ = T.ROCK


def rock_top_z(x, y):
    """Height of the flat-ish stone top (slopes gently down towards +x)."""
    u = (x - RX + 0.05) / 0.37
    return T.ROCK_TOP - 0.05 * max(0.0, u) ** 2 - 0.02 * ((y - RY) / 0.4) ** 2


rv, rf = sphere_vf(48, 24)
rv = rv.copy()
for i, (x_, y_, z_) in enumerate(rv):
    n_ = 1 + 0.06 * math.sin(5 * x_ + 2 * y_) + 0.04 * math.sin(9 * y_ + 1)
    X, Y = RX + 0.38 * x_ * n_, RY + 0.32 * y_ * n_
    if z_ > 0:
        Z = rock_top_z(X, Y) * min(1.0, (z_ / 0.45) ** 0.35)
    else:
        Z = 0.06 * z_
    rv[i] = (X, Y, Z)
ROCK_O = obj_from("Rock", rv, rf, rock_m)
to_set("field", ROCK_O)


# ================================================================= poop cubes
poop_m, poop_nt, poop_out = new_mat("Poop")
pp = node(poop_nt, "ShaderNodeBsdfPrincipled", Roughness=0.7)
pp.inputs["Specular IOR Level"].default_value = 0.35
ptc = node(poop_nt, "ShaderNodeTexCoord")
pnz = node(poop_nt, "ShaderNodeTexNoise", Scale=70.0, Detail=6.0)
poop_nt.links.new(ptc.outputs["Object"], pnz.inputs["Vector"])
prp = ramp(poop_nt, [(0.35, (0.10, 0.065, 0.035)), (0.65, (0.24, 0.16, 0.09))])
poop_nt.links.new(pnz.outputs["Fac"], prp.inputs[0])
poop_nt.links.new(prp.outputs[0], pp.inputs["Base Color"])
pvo = poop_nt.nodes.new("ShaderNodeTexVoronoi")      # fibrous plant bits
pvo.inputs["Scale"].default_value = 140.0
poop_nt.links.new(ptc.outputs["Object"], pvo.inputs["Vector"])
pbp = node(poop_nt, "ShaderNodeBump", Strength=0.45, Distance=0.004)
pad = poop_nt.nodes.new("ShaderNodeMath")
pad.operation = "ADD"
poop_nt.links.new(pnz.outputs["Fac"], pad.inputs[0])
poop_nt.links.new(pvo.outputs["Distance"], pad.inputs[1])
poop_nt.links.new(pad.outputs[0], pbp.inputs["Height"])
poop_nt.links.new(pbp.outputs["Normal"], pp.inputs["Normal"])
poop_nt.links.new(pp.outputs[0], poop_out.inputs[0])
fog(poop_m, 0.045)


def rounded_cube_vf(size, bevel=0.18, seg=3):
    bm_ = bmesh.new()
    bmesh.ops.create_cube(bm_, size=1.0)
    bmesh.ops.bevel(bm_, geom=list(bm_.edges) + list(bm_.verts), offset=bevel * 0.5, segments=seg,
                    affect="EDGES", profile=0.5)
    vv_ = np.array([v.co[:] for v in bm_.verts]) * size
    ff_ = [[v.index for v in f.verts] for f in bm_.faces]
    bm_.free()
    # a little irregularity so they look made, not machined
    vv_ = vv_ * (1 + 0.03 * np.sin(vv_ @ np.array([90.0, 70.0, 50.0])))[:, None]
    return vv_, ff_


CUBE_V, CUBE_F = rounded_cube_vf(T.CUBE)
cube_me = obj_from("CubeMesh", CUBE_V, CUBE_F, poop_m).data
bpy.data.objects.remove(bpy.data.objects["CubeMesh"])


def cube_obj(name):
    o = bpy.data.objects.new(name, cube_me)
    col.objects.link(o)
    SETS["field"].append(o)
    return o


CUBE0 = cube_obj("Cube0")
TRAIL = [cube_obj(f"Trail{k}") for k in range(T.N_TRAIL)]
ROCK_CUBES = [cube_obj(f"RockCube{k}") for k in range(len(T.ROCK_DROPS))]
BALL_R = T.CUBE * 0.62
BALL = sph("Ball", (0, 0, 0), BALL_R, poop_m, u=32, v=16)
to_set("field", BALL)

# glow highlights on the hook cube (S1): top face on "FLAT", edges + corner sparks on "CORNERS"
face_m, FACE_A, _ = fade_emit_mat("FaceGlow", (1.0, 0.72, 0.28), 2.2)
edge_m, EDGE_A, _ = fade_emit_mat("EdgeGlow", (1.0, 0.62, 0.18), 4.0)
spark_m, SPARK_A, _ = fade_emit_mat("Spark", (1.0, 0.95, 0.8), 14.0)
h_ = T.CUBE / 2 * 1.02
fb = Builder()
fb.add(np.array([[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0]], float) * [h_ * 0.86, h_ * 0.86, 0], [[0, 1, 2, 3]],
       Matrix.Translation((0, 0, h_ + 0.0008)))
FACE = fb.build("FaceGlow", face_m, smooth=False)
eb = Builder()
cyl_v, cyl_f = tube_verts([(0, 0, -1), (0, 0, 1)], [1, 1], 8), tube_faces(2, 8)
corners = [(sx * h_, sy * h_, sz * h_) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
for a_ in corners:
    for b_ in corners:
        if a_ < b_ and sum(1 for p, q in zip(a_, b_) if p != q) == 1:
            m_ = V([(p + q) / 2 for p, q in zip(a_, b_)])
            d_ = V(b_) - V(a_)
            rot_ = d_.to_track_quat("Z", "Y").to_matrix().to_4x4()
            eb.add(cyl_v, cyl_f, Matrix.Translation(m_) @ rot_ @ Matrix.Diagonal((0.0006, 0.0006, d_.length / 2 * 0.86, 1)))
EDGES = eb.build("EdgeGlow", edge_m)
sb_ = Builder()
for c_ in corners:
    if c_[2] > 0 or c_[1] < 0:
        sb_.sphere(c_, (0.0035, 0.0035, 0.0035))
        sb_.sphere(c_, (0.011, 0.0011, 0.0011))
        sb_.sphere(c_, (0.0011, 0.011, 0.0011))
        sb_.sphere(c_, (0.0011, 0.0011, 0.011))
SPARKS = sb_.build("Sparks", spark_m)
for o_ in (FACE, EDGES, SPARKS):
    o_.parent = CUBE0
    o_.visible_shadow = False
    no_bounce([o_])
    to_set("field", o_)

# scent ring on "TURF"
ring_m, RING_A, _ = fade_emit_mat("ScentRing", (0.55, 1.0, 0.55), 3.0)
soften(ring_m)
rgv = []
rgf = []
NR = 96
for k in range(NR):
    a_ = 2 * math.pi * k / NR
    for j, (rr, zz) in enumerate(((0.97, 0.0), (1.0, 0.012), (1.03, 0.0))):
        rgv.append((rr * math.cos(a_), rr * math.sin(a_), zz))
for k in range(NR):
    k2 = (k + 1) % NR
    for j in range(2):
        rgf.append([k * 3 + j, k2 * 3 + j, k2 * 3 + j + 1, k * 3 + j + 1])
RINGS = []
for k in range(2):
    o_ = obj_from(f"ScentRing{k}", rgv, rgf, ring_m)
    o_.visible_shadow = False
    no_bounce([o_])
    to_set("field", o_)
    RINGS.append(o_)


# ================================================================= the wombat
fur_m, fur_nt, fur_out = new_mat("Fur")
fp = node(fur_nt, "ShaderNodeBsdfPrincipled", Roughness=0.85)
fp.inputs["Specular IOR Level"].default_value = 0.2
fp.inputs["Sheen Weight"].default_value = 1.0
fp.inputs["Sheen Roughness"].default_value = 0.35
fp.inputs["Sheen Tint"].default_value = (0.95, 0.88, 0.8, 1)
ftc = node(fur_nt, "ShaderNodeTexCoord")
fnz = node(fur_nt, "ShaderNodeTexNoise", Scale=4.0, Detail=3.0)
fur_nt.links.new(ftc.outputs["Object"], fnz.inputs["Vector"])
frp = ramp(fur_nt, [(0.35, (0.10, 0.085, 0.07)), (0.65, (0.20, 0.16, 0.125))])
fur_nt.links.new(fnz.outputs["Fac"], frp.inputs[0])
fsep = fur_nt.nodes.new("ShaderNodeSeparateXYZ")          # darker legs and belly
fur_nt.links.new(ftc.outputs["Object"], fsep.inputs[0])
fzr = fur_nt.nodes.new("ShaderNodeMapRange")
fzr.inputs["From Min"].default_value = 0.05
fzr.inputs["From Max"].default_value = 0.30
fzr.inputs["To Min"].default_value = 0.55
fzr.inputs["To Max"].default_value = 1.0
fur_nt.links.new(fsep.outputs["Z"], fzr.inputs["Value"])
fmul = fur_nt.nodes.new("ShaderNodeVectorMath")
fmul.operation = "SCALE"
fur_nt.links.new(frp.outputs[0], fmul.inputs[0])
fur_nt.links.new(fzr.outputs["Result"], fmul.inputs["Scale"])
fur_nt.links.new(fmul.outputs[0], fp.inputs["Base Color"])
# fur strands: stretched noise along the body gives a combed look in the bump
fmap = fur_nt.nodes.new("ShaderNodeMapping")
fmap.inputs["Scale"].default_value = (90.0, 260.0, 260.0)
fur_nt.links.new(ftc.outputs["Object"], fmap.inputs["Vector"])
fnz2 = node(fur_nt, "ShaderNodeTexNoise", Detail=4.0)
fnz2.inputs["Scale"].default_value = 1.0
fur_nt.links.new(fmap.outputs[0], fnz2.inputs["Vector"])
fbp = node(fur_nt, "ShaderNodeBump", Strength=0.55, Distance=0.004)
fur_nt.links.new(fnz2.outputs["Fac"], fbp.inputs["Height"])
fur_nt.links.new(fbp.outputs["Normal"], fp.inputs["Normal"])
# x-ray mix
xem = node(fur_nt, "ShaderNodeEmission", Color=(0.45, 0.8, 1.0, 1), Strength=2.2)
xtr = node(fur_nt, "ShaderNodeBsdfTransparent")
xlw = node(fur_nt, "ShaderNodeLayerWeight", Blend=0.45)
xpw = fur_nt.nodes.new("ShaderNodeMath")
xpw.operation = "POWER"
xpw.inputs[1].default_value = 1.6
fur_nt.links.new(xlw.outputs["Facing"], xpw.inputs[0])
xmix = fur_nt.nodes.new("ShaderNodeMixShader")
fur_nt.links.new(xpw.outputs[0], xmix.inputs[0])
fur_nt.links.new(xtr.outputs[0], xmix.inputs[1])
fur_nt.links.new(xem.outputs[0], xmix.inputs[2])
xval = node(fur_nt, "ShaderNodeValue")
xval.outputs[0].default_value = 0.0
XRAY = xval.outputs[0]
fmix = fur_nt.nodes.new("ShaderNodeMixShader")
fur_nt.links.new(xval.outputs[0], fmix.inputs[0])
fur_nt.links.new(fp.outputs[0], fmix.inputs[1])
fur_nt.links.new(xmix.outputs[0], fmix.inputs[2])
fur_nt.links.new(fmix.outputs[0], fur_out.inputs[0])
fog(fur_m, 0.045)

W_ROOT = empty("WombatRoot", (0, 0, 0))
W_BOB = empty("WombatBob", (0, 0, 0), W_ROOT)
import wombat_mesh  # noqa: E402
(_bv, _bf), (_lv, _lf), EYE_P, NOSE_P = wombat_mesh.build()
W_BODY = obj_from("WombatBody", _bv, _bf.tolist(), fur_m)
W_BODY.parent = W_BOB
HIPS = [V((0.20, 0.135, 0.205)), V((0.20, -0.135, 0.205)), V((-0.27, 0.15, 0.205)), V((-0.27, -0.15, 0.205))]
LEG_PH = [0.0, 0.5, 0.5, 0.0]
eye_m, _ = principled("Eye", (0.01, 0.008, 0.006), rough=0.08, coat=1.0)
nose_m, _ = principled("Nose", (0.05, 0.045, 0.045), rough=0.45, bump=0.4, bump_scale=60)
claw_m, _ = principled("Claw", (0.55, 0.5, 0.42), rough=0.4)
LEGS = []
for i_, hp in enumerate(HIPS):
    lo = obj_from(f"Leg{i_}", _lv, _lf.tolist(), fur_m)
    lo.parent = W_ROOT
    lo.location = hp
    cb = Builder()
    for k in (-1, 0, 1):
        cb.sphere((0.115, k * 0.024, -0.205), (0.026, 0.008, 0.007), rot=(0, 0.3, k * 0.25))
    co_ = cb.build(f"Claws{i_}", claw_m)
    co_.parent = lo
    LEGS.append((lo, co_))

# ---- fur: short hair curves grown on the body and legs (geometry nodes), combed back and down
hair_m, hair_nt, hair_out = new_mat("Hair")
hp_ = node(hair_nt, "ShaderNodeBsdfPrincipled", Roughness=0.55)
hp_.inputs["Specular IOR Level"].default_value = 0.25
hp_.inputs["Sheen Weight"].default_value = 0.6
htc = node(hair_nt, "ShaderNodeTexCoord")
hnz = node(hair_nt, "ShaderNodeTexNoise", Scale=4.0, Detail=3.0)
hair_nt.links.new(htc.outputs["Object"], hnz.inputs["Vector"])
hrand = ramp(hair_nt, [(0.3, (0.075, 0.062, 0.05)), (0.7, (0.17, 0.14, 0.11))])
hair_nt.links.new(hnz.outputs["Fac"], hrand.inputs[0])
htip_a = hair_nt.nodes.new("ShaderNodeAttribute")
htip_a.attribute_name = "tip"
htip = hair_nt.nodes.new("ShaderNodeMix")
htip.data_type = "RGBA"
hpow = hair_nt.nodes.new("ShaderNodeMath")
hpow.operation = "POWER"
hpow.inputs[1].default_value = 2.0
hair_nt.links.new(htip_a.outputs["Fac"], hpow.inputs[0])
hair_nt.links.new(hpow.outputs[0], htip.inputs["Factor"])
hair_nt.links.new(hrand.outputs[0], htip.inputs["A"])
htip.inputs["B"].default_value = (0.36, 0.31, 0.26, 1)
hair_nt.links.new(htip.outputs[2], hp_.inputs["Base Color"])
hair_nt.links.new(hp_.outputs[0], hair_out.inputs[0])
fog(hair_m, 0.045)

def fur_modifier(obj, density, length):
    ng = bpy.data.node_groups.new(f"Fur_{obj.name}", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N = ng.nodes
    gi = N.new("NodeGroupInput")
    go = N.new("NodeGroupOutput")
    dist = N.new("GeometryNodeDistributePointsOnFaces")
    dist.inputs["Density"].default_value = density
    dist.inputs["Seed"].default_value = 3
    ng.links.new(gi.outputs[0], dist.inputs["Mesh"])
    line = N.new("GeometryNodeCurvePrimitiveLine")
    line.inputs["Start"].default_value = (0, 0, 0)
    line.inputs["End"].default_value = (0, 0, 1)
    res = N.new("GeometryNodeResampleCurve")
    res.inputs["Count"].default_value = 3
    ng.links.new(line.outputs[0], res.inputs["Curve"])
    comb = N.new("ShaderNodeVectorMath")
    comb.operation = "ADD"
    ng.links.new(dist.outputs["Normal"], comb.inputs[0])
    comb.inputs[1].default_value = (-1.1, 0.0, -0.45)
    align = N.new("FunctionNodeAlignRotationToVector")
    align.axis = "Z"
    ng.links.new(comb.outputs[0], align.inputs["Vector"])
    rnd = N.new("FunctionNodeRandomValue")
    rnd.data_type = "FLOAT"
    rnd.inputs["Min"].default_value = 0.6 * length
    rnd.inputs["Max"].default_value = length
    sc = N.new("ShaderNodeCombineXYZ")
    ng.links.new(rnd.outputs["Value"], sc.inputs["Z"])
    sc.inputs["X"].default_value = 1.0
    sc.inputs["Y"].default_value = 1.0
    inst = N.new("GeometryNodeInstanceOnPoints")
    ng.links.new(dist.outputs["Points"], inst.inputs["Points"])
    ng.links.new(res.outputs[0], inst.inputs["Instance"])
    ng.links.new(align.outputs[0], inst.inputs["Rotation"])
    ng.links.new(sc.outputs[0], inst.inputs["Scale"])
    real = N.new("GeometryNodeRealizeInstances")
    ng.links.new(inst.outputs[0], real.inputs[0])
    sp = N.new("GeometryNodeSplineParameter")
    store = N.new("GeometryNodeStoreNamedAttribute")
    store.data_type = "FLOAT"
    store.domain = "POINT"
    store.inputs["Name"].default_value = "tip"
    ng.links.new(real.outputs[0], store.inputs["Geometry"])
    ng.links.new(sp.outputs["Factor"], store.inputs["Value"])
    taper = N.new("ShaderNodeMath")
    taper.operation = "MULTIPLY_ADD"
    ng.links.new(sp.outputs["Factor"], taper.inputs[0])
    taper.inputs[1].default_value = -0.0012
    taper.inputs[2].default_value = 0.0014
    prof = N.new("GeometryNodeCurvePrimitiveCircle")
    prof.inputs["Resolution"].default_value = 3
    prof.inputs["Radius"].default_value = 1.0
    c2m = N.new("GeometryNodeCurveToMesh")
    ng.links.new(store.outputs[0], c2m.inputs["Curve"])
    ng.links.new(prof.outputs[0], c2m.inputs["Profile Curve"])
    ng.links.new(taper.outputs[0], c2m.inputs["Scale"])
    sm = N.new("GeometryNodeSetMaterial")
    sm.inputs["Material"].default_value = hair_m
    ng.links.new(c2m.outputs[0], sm.inputs["Geometry"])
    ssm = N.new("GeometryNodeSetShadeSmooth")
    ng.links.new(sm.outputs[0], ssm.inputs["Geometry"])
    join = N.new("GeometryNodeJoinGeometry")
    ng.links.new(ssm.outputs[0], join.inputs[0])
    ng.links.new(gi.outputs[0], join.inputs[0])
    ng.links.new(join.outputs[0], go.inputs[0])
    obj.data.materials.append(hair_m)
    m = obj.modifiers.new("Fur", "NODES")
    m.node_group = ng
    return m


FUR_MODS = [fur_modifier(W_BODY, 42000, 0.024)] + [fur_modifier(lo, 30000, 0.014) for lo, _c in LEGS]

EYES = []
for e_ in EYE_P:
    eo = sph("Eye", tuple(e_ - np.array([0.010, 0.008 * np.sign(e_[1]), 0])), 0.025, eye_m, u=24, v=12)
    eo.parent = W_BOB
    EYES.append(eo)
NOSE = sph("Nose", tuple(NOSE_P - np.array([0.012, 0, 0.0])), 1.0, nose_m, u=32, v=16, scale=(0.042, 0.088, 0.058))
NOSE.parent = W_BOB
W_HEAD = W_BOB

# gut, only visible in the x-ray
gut_m, GUT_S = emit_mat("GutGlow", (1.0, 0.45, 0.16), 0.0)
gpts = []
for k in range(90):
    s_ = k / 89
    a_ = 4.5 * 2 * math.pi * s_
    gpts.append((0.14 - 0.32 * s_ + 0.035 * math.sin(a_), 0.10 * math.cos(a_), 0.265 + 0.065 * math.sin(a_)))
colon = [gpts[-1], (-0.24, 0.06, 0.25), (-0.31, 0.0, 0.23), (-0.38, 0.0, 0.22), (-0.43, 0.0, 0.215)]
GUT_TUBE = tube("SmallIntestine", gpts, [0.02] * len(gpts), gut_m, seg=10)
COLON = tube("Colon", colon, [0.024, 0.03, 0.034, 0.034, 0.028], gut_m, seg=14)
inner_m, _ = emit_mat("InnerCube", (0.55, 0.25, 0.08), 3.0)
ic = Builder()
ic.add(CUBE_V * 0.6, CUBE_F, Matrix.Translation((-0.385, 0.0, 0.22)))
INNER_CUBE = ic.build("InnerCube", inner_m)
for o_ in (GUT_TUBE, COLON, INNER_CUBE):
    o_.parent = W_BOB
    o_.visible_shadow = False
    no_bounce([o_])

W_OBJS = [W_BODY, NOSE, *EYES, *[o for pair in LEGS for o in pair]]
GUT_OBJS = [GUT_TUBE, COLON, INNER_CUBE]
to_set("field", *W_OBJS, *GUT_OBJS)


def pose_wombat(pos, heading, phase, moving, t, xray=0.0):
    """Immediate-mode pose: legs swing with the walk phase, the body waddles and bobs."""
    W_ROOT.location = (pos[0], pos[1], 0.0)
    W_ROOT.rotation_euler = (0, 0, heading)
    p2 = 2 * math.pi * phase
    mv = 1.0 if moving else 0.0
    breathe = 0.006 * math.sin(t * 2.4)
    bob_z = mv * 0.012 * math.cos(2 * p2) + breathe
    roll = mv * 0.05 * math.sin(p2)
    yaw = mv * 0.035 * math.sin(p2)
    W_BOB.location = (0, 0, bob_z)
    W_BOB.rotation_euler = (roll, 0, yaw)
    for i_, (lo, _c) in enumerate(LEGS):
        ph = 2 * math.pi * (phase + LEG_PH[i_])
        lo.rotation_euler = (0, -mv * 0.42 * math.sin(ph), 0)
        lo.location = HIPS[i_] + V((0, 0, mv * max(0.0, 0.03 * math.cos(ph))))
    XRAY.default_value = xray
    for fm_ in FUR_MODS:
        fm_.show_render = xray < 0.5
    GUT_S.default_value = 3.5 * xray
    for o_ in GUT_OBJS:
        o_.hide_render = xray < 0.01


def wombat_state(t):
    """Where the wombat is and what it does at time t: pos, heading, phase, moving, xray, visible."""
    i = T.shot_index(t)
    if i in (0, 1, 2, len(T.SHOTS) - 1):
        te = T.env_t(t)
        xr = T.smoother((t - T.T_GUT + 0.12) / 0.3) if i == 2 else 0.0
        return T.walk_pos(te), T.WALK_A, T.WALK_V * te / T.STRIDE, True, xr, True
    if i == 5:
        t0, t1 = T.SHOTS[5][0], T.SHOTS[5][1]
        u = T.clamp((t - t0 + 0.05) / (t1 - t0 + 0.1))
        p = T.night_path(u)
        q = T.night_path(min(1.0, u + 0.01))
        p0_ = T.night_path(max(0.0, u - 0.01))
        hd = math.atan2(q[1] - p0_[1], q[0] - p0_[0])
        # arc length so far -> leg phase (the time-lapse makes the legs run fast)
        s_ = sum(math.dist(T.night_path(k / 60 * u), T.night_path((k + 1) / 60 * u)) for k in range(60))
        return p, hd, s_ / T.STRIDE, True, 0.0, True
    if i in (6, 7):
        base = (RX + 0.46, RY + 0.02, 0.0)
        tl = T.T_TURF - 0.1
        if t < tl:
            return base, 0.0, 0.0, False, 0.0, True
        d = 0.33 * (t - tl)
        return (base[0] + d, base[1], 0.0), 0.0, d / T.STRIDE, True, 0.0, True
    return (0, 0, 0), 0.0, 0.0, False, 0.0, False


def rump_point(pos, heading):
    return V((pos[0] - math.cos(heading) * T.REAR, pos[1] - math.sin(heading) * T.REAR, 0.22))


# ================================================================= gut set: x-ray close-up of the end of the intestine
GX, GY, GZ = T.GUT
XE = 3.0                    # the tube ends (opens) here, local x
TUBE_X0 = -5.0
R_WALL = 0.5
A_POOP = 0.40               # half-width of the poop log
PITCH = 0.95                # piece spacing along the log
SIDE = 2 * A_POOP           # cube edge once pinched off
LOG_V = 0.30                # log speed (m/s)
NX, NA = 150, 72

back_m, _ = emit_mat("XrayBackdrop", (0.006, 0.014, 0.035), 1.0)
bd = sph("Backdrop", (GX, GY, GZ), 25.0, back_m, u=32, v=16)
to_set("gut", bd)
for nm, loc, tgt, en, sz, colr in (("GutKey", (2.0, -3.0, 4.0), (1.0, 0, 0), 900, 3.0, (1.0, 0.92, 0.85)),
                                   ("GutRim", (-2.0, 3.0, 2.5), (0.5, 0, 0), 500, 3.0, (0.6, 0.8, 1.0))):
    l_ = bpy.data.lights.new(nm, "AREA")
    l_.energy, l_.size, l_.color = en, sz, colr
    o_ = bpy.data.objects.new(nm, l_)
    o_.location = (GX + loc[0], GY + loc[1], GZ + loc[2])
    o_.rotation_euler = (V(o_.location) - V((GX + tgt[0], GY, GZ))).to_track_quat("Z", "Y").to_euler()
    col.objects.link(o_)
    to_set("gut", o_)

# wall material: transparent x-ray tube; stiff bands red, stretchy bands blue (revealed on their words)
wall_m, wnt_, wout = new_mat("GutWall")
w_attr = wnt_.nodes.new("ShaderNodeAttribute")
w_attr.attribute_name = "band"
w_rs = node(wnt_, "ShaderNodeValue")
w_rt = node(wnt_, "ShaderNodeValue")
REVEAL_STIFF, REVEAL_STRETCH = w_rs.outputs[0], w_rt.outputs[0]
w_rev = wnt_.nodes.new("ShaderNodeMix")             # reveal = mix(stiff reveal, stretchy reveal, band)
w_rev.data_type = "FLOAT"
wnt_.links.new(w_attr.outputs["Fac"], w_rev.inputs["Factor"])
wnt_.links.new(w_rs.outputs[0], w_rev.inputs["A"])
wnt_.links.new(w_rt.outputs[0], w_rev.inputs["B"])
w_bc = wnt_.nodes.new("ShaderNodeMix")
w_bc.data_type = "RGBA"
wnt_.links.new(w_attr.outputs["Fac"], w_bc.inputs["Factor"])
w_bc.inputs["A"].default_value = (1.0, 0.22, 0.12, 1)      # stiff
w_bc.inputs["B"].default_value = (0.15, 0.72, 1.0, 1)      # stretchy
w_col = wnt_.nodes.new("ShaderNodeMix")
w_col.data_type = "RGBA"
wnt_.links.new(w_rev.outputs[0], w_col.inputs["Factor"])
w_col.inputs["A"].default_value = (0.75, 0.42, 0.45, 1)    # neutral pink tissue
wnt_.links.new(w_bc.outputs[2], w_col.inputs["B"])
w_tc = node(wnt_, "ShaderNodeTexCoord")
w_wave = wnt_.nodes.new("ShaderNodeTexWave")               # muscle rings
w_wave.wave_type = "BANDS"
w_wave.bands_direction = "X"
w_wave.inputs["Scale"].default_value = 2.2
w_wave.inputs["Distortion"].default_value = 2.0
w_wave.inputs["Detail"].default_value = 2.0
wnt_.links.new(w_tc.outputs["Object"], w_wave.inputs["Vector"])
w_wr = ramp(wnt_, [(0.0, (0.65, 0.65, 0.65)), (1.0, (1.0, 1.0, 1.0))])
wnt_.links.new(w_wave.outputs["Fac"], w_wr.inputs[0])
w_cm = wnt_.nodes.new("ShaderNodeMix")
w_cm.data_type = "RGBA"
w_cm.blend_type = "MULTIPLY"
w_cm.inputs["Factor"].default_value = 1.0
wnt_.links.new(w_col.outputs[2], w_cm.inputs["A"])
wnt_.links.new(w_wr.outputs[0], w_cm.inputs["B"])
w_em = node(wnt_, "ShaderNodeEmission", Strength=1.6)
wnt_.links.new(w_cm.outputs[2], w_em.inputs["Color"])
w_tr = node(wnt_, "ShaderNodeBsdfTransparent")
w_lw = node(wnt_, "ShaderNodeLayerWeight", Blend=0.4)
w_pw = wnt_.nodes.new("ShaderNodeMath")
w_pw.operation = "POWER"
w_pw.inputs[1].default_value = 2.2
wnt_.links.new(w_lw.outputs["Facing"], w_pw.inputs[0])
w_ad = wnt_.nodes.new("ShaderNodeMath")                    # band colour shows more strongly once revealed
w_ad.operation = "MULTIPLY_ADD"
w_ad.use_clamp = True
w_ad.inputs[2].default_value = 0.04
wnt_.links.new(w_rev.outputs[0], w_ad.inputs[0])
w_ad.inputs[1].default_value = 0.30
w_sum = wnt_.nodes.new("ShaderNodeMath")
w_sum.operation = "ADD"
w_sum.use_clamp = True
wnt_.links.new(w_pw.outputs[0], w_sum.inputs[0])
wnt_.links.new(w_ad.outputs[0], w_sum.inputs[1])
w_mx = wnt_.nodes.new("ShaderNodeMixShader")
wnt_.links.new(w_sum.outputs[0], w_mx.inputs[0])
wnt_.links.new(w_tr.outputs[0], w_mx.inputs[1])
wnt_.links.new(w_em.outputs[0], w_mx.inputs[2])
wnt_.links.new(w_mx.outputs[0], wout.inputs[0])

ANG = np.linspace(0, 2 * np.pi, NA, endpoint=False)
COS, SIN = np.cos(ANG), np.sin(ANG)
BAND = 0.5 + 0.5 * np.tanh(5.0 * (np.abs(COS) - np.abs(SIN)))     # 1 = stretchy (sides), 0 = stiff (top/bottom)
WALL_X = np.linspace(TUBE_X0, XE, NX)


def superellipse_r(n):
    """Radius per angle of a superellipse |y|^n + |z|^n = 1 (n = 2 circle ... large n = square)."""
    n = np.asarray(n, float)[..., None] if np.ndim(n) else n
    return (np.abs(COS) ** n + np.abs(SIN) ** n) ** (-1.0 / n)


def squareness(x, t):
    """0 = round, 1 = square: grows towards the end of the gut once the squeezing starts."""
    s = T.smoother((t - T.T_SQUEEZE + 0.15) / 0.7)
    return s * np.clip((np.asarray(x) + 0.6) / 1.8, 0, 1) ** 1.2


def wall_verts(t):
    sq = squareness(WALL_X, t)
    n = 2.0 + 5.0 * sq
    rr = superellipse_r(n)                                           # (NX, NA)
    # peristaltic squeeze wave: the stiff bands pull in harder and faster than the stretchy ones
    act = T.smoother((t - T.T_SQUEEZE + 0.2) / 0.4)
    ph = ((t - T.T_SQUEEZE) * 0.9) % 1.0
    xw = -2.5 + 6.0 * ph
    wave = act * np.exp(-((WALL_X - xw) / 0.45) ** 2)
    k = 1.0 - wave[:, None] * (0.05 + 0.07 * (1 - BAND[None, :]))
    r = R_WALL * rr * k / (1 + 0.12 * sq[:, None])
    y = r * COS[None, :]
    z = r * SIN[None, :]
    xx = np.repeat(WALL_X[:, None], NA, axis=1)
    return np.stack([xx + GX, y + GY, z + GZ], axis=-1).reshape(-1, 3)


wall_f = []
for i in range(NX - 1):
    for k in range(NA):
        wall_f.append([i * NA + k, i * NA + (k + 1) % NA, (i + 1) * NA + (k + 1) % NA, (i + 1) * NA + k])
WALL = Dyn("GutWall", wall_verts(0.0), wall_f, wall_m, sets=("gut",))
WALL.o.visible_shadow = False
battr = WALL.o.data.attributes.new("band", "FLOAT", "POINT")
battr.data.foreach_set("value", np.tile(BAND, NX).astype(np.float32))

# poop log pieces (become cubes); wet and glossy, dries darker towards the end
log_m, lnt, lout = new_mat("PoopLog")
lp = node(lnt, "ShaderNodeBsdfPrincipled", Roughness=0.3)
lp.inputs["Coat Weight"].default_value = 0.5
lp.inputs["Coat Roughness"].default_value = 0.15
l_geo = lnt.nodes.new("ShaderNodeNewGeometry")
l_sep = lnt.nodes.new("ShaderNodeSeparateXYZ")
lnt.links.new(l_geo.outputs["Position"], l_sep.inputs[0])
l_mr = lnt.nodes.new("ShaderNodeMapRange")
l_mr.inputs["From Min"].default_value = GX + 0.4
l_mr.inputs["From Max"].default_value = GX + 2.4
lnt.links.new(l_sep.outputs["X"], l_mr.inputs["Value"])
l_dry = node(lnt, "ShaderNodeValue")
DRY = l_dry.outputs[0]
l_dm = lnt.nodes.new("ShaderNodeMath")
l_dm.operation = "MULTIPLY"
lnt.links.new(l_mr.outputs["Result"], l_dm.inputs[0])
lnt.links.new(l_dry.outputs[0], l_dm.inputs[1])
l_tc = node(lnt, "ShaderNodeTexCoord")
l_nz = node(lnt, "ShaderNodeTexNoise", Scale=9.0, Detail=6.0)
lnt.links.new(l_tc.outputs["Object"], l_nz.inputs["Vector"])
l_wet = ramp(lnt, [(0.35, (0.30, 0.17, 0.08)), (0.65, (0.46, 0.28, 0.13))])
l_dr = ramp(lnt, [(0.35, (0.10, 0.065, 0.035)), (0.65, (0.22, 0.14, 0.075))])
lnt.links.new(l_nz.outputs["Fac"], l_wet.inputs[0])
lnt.links.new(l_nz.outputs["Fac"], l_dr.inputs[0])
l_cm = lnt.nodes.new("ShaderNodeMix")
l_cm.data_type = "RGBA"
lnt.links.new(l_dm.outputs[0], l_cm.inputs["Factor"])
lnt.links.new(l_wet.outputs[0], l_cm.inputs["A"])
lnt.links.new(l_dr.outputs[0], l_cm.inputs["B"])
lnt.links.new(l_cm.outputs[2], lp.inputs["Base Color"])
l_rm = lnt.nodes.new("ShaderNodeMapRange")
l_rm.inputs["To Min"].default_value = 0.25
l_rm.inputs["To Max"].default_value = 0.85
lnt.links.new(l_dm.outputs[0], l_rm.inputs["Value"])
lnt.links.new(l_rm.outputs["Result"], lp.inputs["Roughness"])
l_cw = lnt.nodes.new("ShaderNodeMath")
l_cw.operation = "SUBTRACT"
l_cw.inputs[0].default_value = 0.6
lnt.links.new(l_dm.outputs[0], l_cw.inputs[1])
lnt.links.new(l_cw.outputs[0], lp.inputs["Coat Weight"])
l_bp = node(lnt, "ShaderNodeBump", Strength=0.35, Distance=0.02)
l_n2 = node(lnt, "ShaderNodeTexNoise", Scale=30.0, Detail=4.0)
lnt.links.new(l_tc.outputs["Object"], l_n2.inputs["Vector"])
lnt.links.new(l_n2.outputs["Fac"], l_bp.inputs["Height"])
lnt.links.new(l_bp.outputs["Normal"], lp.inputs["Normal"])
lnt.links.new(lp.outputs[0], lout.inputs[0])

NJ = 14                                        # rings per piece
PIECE_U = np.linspace(-1, 1, NJ)
N_PIECES = 9
PIECE_X0 = -6.0                                # piece 0 centre at T_STIFF


def piece_center(k, t):
    return PIECE_X0 + k * PITCH + LOG_V * (t - T.T_STIFF) + 0.25 * max(0.0, t - T.T_SQUEEZE)


def pinch(x, t):
    return T.smoother((t - T.T_INTO + 0.15) / 0.55) * float(np.clip((x - 0.5) / 0.8, 0, 1))


def piece_verts(k, t):
    cx = piece_center(k, t)
    sq = float(squareness(min(cx, XE), t))
    pn = pinch(min(cx, XE + 0.5), t)
    half = PITCH / 2 + 0.01 - (PITCH - SIDE) / 2 * pn
    n = 2.0 + 6.0 * sq
    rr = superellipse_r(n)
    a = A_POOP / (1 + 0.12 * sq)
    rows = []
    for u in PIECE_U:
        end = abs(u)
        bevel = 1.0 - pn * 0.10 * max(0.0, (end - 0.82) / 0.18) ** 2
        r = a * rr * bevel
        rows.append(np.stack([np.full(NA, u * half), r * COS, r * SIN], axis=-1))
    v = np.concatenate(rows + [np.array([[-half, 0, 0], [half, 0, 0]])])
    # out of the tube: fall and tumble
    drop = max(0.0, cx - (XE + SIDE / 2 + 0.05))
    if drop > 0:
        dt = drop / LOG_V
        ang = 0.6 * dt
        c_, s_ = math.cos(ang), math.sin(ang)
        v = v @ np.array([[c_, 0, s_], [0, 1, 0], [-s_, 0, c_]])
        cz = -4.9 * dt * dt
    else:
        cz = 0.0
    return v + np.array([GX + cx, GY, GZ + cz])


def piece_faces():
    f = []
    for i in range(NJ - 1):
        for k in range(NA):
            f.append([i * NA + k, i * NA + (k + 1) % NA, (i + 1) * NA + (k + 1) % NA, (i + 1) * NA + k])
    c0, c1 = NJ * NA, NJ * NA + 1
    for k in range(NA):
        f.append([(k + 1) % NA, k, c0])
        f.append([(NJ - 1) * NA + k, (NJ - 1) * NA + (k + 1) % NA, c1])
    return f


PF = piece_faces()
PIECES = [Dyn(f"LogPiece{k}", piece_verts(k, T.T_STIFF), PF, log_m, sets=("gut",)) for k in range(N_PIECES)]

# water leaving the drying poop (on "DRIES")
drop_m, _ = emit_mat("WaterDrop", (0.45, 0.85, 1.0), 5.0)
DROP_VF = sphere_vf(8, 6)
NDROP = 70
drng = random.Random(3)
DROPS = [(drng.uniform(0.2, 2.9), drng.uniform(0, 2 * math.pi), T.T_DRIES - 0.25 + drng.uniform(0, 0.9),
          drng.uniform(0.6, 1.0)) for _ in range(NDROP)]
dfaces = []
for i in range(NDROP):
    dfaces += [[j + i * len(DROP_VF[0]) for j in f] for f in DROP_VF[1]]


def drop_verts(t):
    out = []
    for x0, a0, ts, sz in DROPS:
        q = (t - ts) / 0.9
        if 0 < q < 1:
            r = A_POOP + (R_WALL * 1.6 - A_POOP) * q
            s = 0.022 * sz * math.sin(math.pi * q)
            c = np.array([GX + x0 + 0.1 * q, GY + r * math.cos(a0), GZ + r * math.sin(a0)])
        else:
            s, c = 0.0, np.array([GX, GY, GZ - 50])
        out.append(DROP_VF[0] * s + c)
    return np.concatenate(out)


DROPS_O = Dyn("WaterDrops", drop_verts(0.0), dfaces, drop_m, sets=("gut",))
DROPS_O.o.visible_shadow = False


def pose_gut(t):
    REVEAL_STIFF.default_value = T.smoother((t - T.T_STIFF + 0.05) / 0.3)
    REVEAL_STRETCH.default_value = T.smoother((t - T.T_STRETCHY + 0.05) / 0.3)
    DRY.default_value = T.smoother((t - T.T_DRIES + 0.1) / 0.8)
    WALL.set(wall_verts(t))
    for k, p in enumerate(PIECES):
        cx = piece_center(k, t)
        p.o.hide_render = cx < TUBE_X0 - 1.0 or cx > XE + 4.0
        p.set(piece_verts(k, t))
    DROPS_O.set(drop_verts(t))


# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.dof.use_dof = True
cam = bpy.data.objects.new("Cam", cam_d)
cam.rotation_mode = "QUATERNION"
col.objects.link(cam)
scene.camera = cam
cam_d.clip_start = 0.01
cam_d.clip_end = 200


# ================================================================= per-frame posing
def back_out(x, s=1.7):
    x = T.clamp(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def place(o, loc, rot=(0, 0, 0), scale=1.0):
    o.hide_render = (min(scale) if isinstance(scale, tuple) else scale) <= 0.001
    o.location = loc
    o.rotation_euler = rot
    o.scale = (scale, scale, scale) if not isinstance(scale, tuple) else scale


def pose_cube0(t, i):
    te = T.env_t(t)
    D = V(T.WALK_D)
    h = T.CUBE / 2
    yaw = T.WALK_A + 0.18
    if te < T.T_POP:
        place(CUBE0, (0, 0, -5), scale=0.0)
        return
    if te < T.T_OUT:
        u = (te - T.T_POP) / (T.T_OUT - T.T_POP)
        rp = rump_point(T.walk_pos(te), T.WALK_A) - D * (0.05 * u)
        place(CUBE0, rp, (0, 0, T.WALK_A), 0.25 + 0.75 * T.ease_out(u))
        return
    cx, cy, _ = T.CUBE0
    if te < T.T_LAND:
        u = (te - T.T_OUT) / (T.T_LAND - T.T_OUT)
        z = 0.22 - (0.22 - h) * u * u
        place(CUBE0, (cx, cy, z), (0.25 * (1 - u) * 0, -0.35 * u, T.WALK_A + 0.18 * u))
        return
    d = te - T.T_LAND
    sq = 0.14 * math.exp(-d / 0.07) * math.cos(d * 40)
    place(CUBE0, (cx, cy, h * (1 - sq)), (0, 0, yaw), (1 + sq * 0.5, 1 + sq * 0.5, 1 - sq))


def night_u(t):
    t0, t1 = T.SHOTS[5][0], T.SHOTS[5][1]
    return T.clamp((t - t0 + 0.05) / (t1 - t0 + 0.1)), t0, t1


def pose_trail(t):
    u, t0, t1 = night_u(t)
    for k, o in enumerate(TRAIL):
        uk = T.trail_drop_u(k)
        tk = t0 - 0.05 + uk * (t1 - t0 + 0.1)
        if t < tk or t < t0:
            place(o, (0, 0, -5), scale=0.0)
            continue
        p = T.night_path(uk)
        q = T.night_path(min(1.0, uk + 0.01))
        hd = math.atan2(q[1] - p[1], q[0] - p[0])
        j = random.Random(k)
        loc = (p[0] - math.cos(hd) * (T.REAR + 0.05) + j.uniform(-0.03, 0.03),
               p[1] - math.sin(hd) * (T.REAR + 0.05) + j.uniform(-0.03, 0.03), T.CUBE / 2)
        place(o, loc, (0, 0, hd + j.uniform(-0.5, 0.5)), back_out((t - tk) / 0.18))


def rock_rest(off):
    x, y = RX + off[0], RY + off[1]
    return V((x, y, rock_top_z(x, y) + T.CUBE / 2))


def pose_rock_cubes(t, pos, heading):
    for (td, off), o in zip(T.ROCK_DROPS, ROCK_CUBES):
        t_pop, t_out = td - 0.32, td - 0.17
        if t < t_pop:
            place(o, (0, 0, -5), scale=0.0)
            continue
        rest = rock_rest(off)
        yaw = 0.3 * off[0] * 10
        if t < t_out:
            u = (t - t_pop) / (t_out - t_pop)
            place(o, ROCK_RUMP + V((-0.04 * u, 0, -0.02 * u)), (0, 0.4, 0), 0.25 + 0.75 * T.ease_out(u))
            continue
        if t < td:
            u = (t - t_out) / (td - t_out)
            a = ROCK_RUMP + V((-0.04, 0, -0.02))
            p = a.lerp(rest, u)
            p.z = a.z + (rest.z - a.z) * u * u
            place(o, p, (0, 0.4 * (1 - u), yaw * u))
            continue
        d = t - td
        sq = 0.14 * math.exp(-d / 0.07) * math.cos(d * 40)
        place(o, rest - V((0, 0, T.CUBE / 2 * sq)), (0, 0, yaw), (1 + sq * 0.5, 1 + sq * 0.5, 1 - sq))


BALL_X0 = RX - 0.06
EDGE_X = RX + 0.33


def ball_state(t):
    """Round poop: appears on the stone, then rolls off the edge and away."""
    if t < T.BALL_T:
        return None
    s = max(0.0, t - T.BALL_ROLL)
    x = BALL_X0 + 1.1 * s * s
    t_edge = math.sqrt((EDGE_X - BALL_X0) / 1.1)
    if s < t_edge:
        z = rock_top_z(x, RY - 0.13) + BALL_R
        return x, z, (x - BALL_X0) / BALL_R
    v = 2.2 * t_edge
    d = s - t_edge
    x = EDGE_X + v * d
    z0 = rock_top_z(EDGE_X, RY - 0.13) + BALL_R
    z = max(BALL_R, z0 - 4.9 * d * d)
    return x, z, (x - BALL_X0) / BALL_R


def pose(t):
    st = T.shot_set(t)
    i = T.shot_index(t)
    for name, objs in SETS.items():
        for o in objs:
            o.hide_render = name != st
    if st == "gut":
        pose_gut(t)
        return
    cam_loc = T.camera(t)[0]
    # moon: fixed, except in the night time-lapse where it arcs across the sky
    if i == 5:
        u, _a, _b = night_u(t)
        az = math.radians(128 - 70 * u)
        el = math.radians(6 + 16 * math.sin(math.pi * (0.25 + 0.6 * u)))
        set_moon((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)), cam_loc)
    else:
        set_moon(MOON_DIR0, cam_loc)
    pos, hd, ph, mv, xr, vis = wombat_state(t)
    for o in W_OBJS:
        o.hide_render = not vis
    if vis:
        pose_wombat(pos, hd, ph, mv, t, xr)
        if i in (6, 7):
            pose_on_rock(t, pos)
    else:
        for o in GUT_OBJS:
            o.hide_render = True
    pose_cube0(t, i)
    glow = i == 1
    for o in (FACE, EDGES, SPARKS):
        o.hide_render = not glow or CUBE0.hide_render
    FACE_A.default_value = 0.07 * T.smoother((t - T.T_FLAT + 0.05) / 0.2) * (1 - 0.6 * T.smoother((t - T.T_CORNERS) / 0.3))
    EDGE_A.default_value = T.smoother((t - T.T_CORNERS + 0.08) / 0.2)
    SPARK_A.default_value = math.exp(-((t - T.T_CORNERS - 0.18) / 0.22) ** 2) + \
        0.35 * T.smoother((t - T.T_CORNERS - 0.3) / 0.3) * (0.6 + 0.4 * math.sin(t * 9))
    pose_trail(t)
    pose_rock_cubes(t, pos, hd)
    b = ball_state(t)
    if b is None or i not in (6, 7):
        place(BALL, (0, 0, -5), scale=0.0)
    else:
        x, z, ang = b
        place(BALL, (x, RY - 0.13, z), (0, ang, 0), back_out((t - T.BALL_T) / 0.2))
    for k, o in enumerate(RINGS):
        u = (t - T.T_TURF + 0.05 - 0.35 * k) / 1.3
        on = 0 < u < 1 and i in (6, 7)
        o.hide_render = not on
        if on:
            r = 0.4 + 2.2 * T.ease_out(u)
            o.location = (RX, RY, 0.015)
            o.scale = (r, r, 1)
    RING_A.default_value = 1.0


ROCK_RUMP = V((0, 0, 0))


def pose_on_rock(t, pos):
    """Rear feet up on the stone, nose down (how wombats mark a rock); steps off on "TURF"."""
    global ROCK_RUMP
    off = T.smoother((t - T.T_TURF + 0.1) / 0.45)
    p = 0.395 * (1 - off)
    W_ROOT.location = (pos[0], pos[1], 0.085 * (1 - off))
    W_ROOT.rotation_euler = (0, p, 0)
    R = Euler((0, p, 0)).to_matrix()
    ROCK_RUMP = V(W_ROOT.location) + R @ V((-T.REAR, 0, 0.22))


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
c.adaptive_threshold = 0.07
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
    scene.view_settings.exposure = 0.35
except Exception:
    pass
SPP = {"field": 8, "gut": 8}
if os.environ.get("WB_EXP"):                       # experiments
    exec(os.environ["WB_EXP"])


def focus_point(t, focus):
    pos = wombat_state(t)[0]
    return {"wombat": V((pos[0], pos[1], 0.3)), "cube0": V(T.CUBE0) + V((0, 0, 0.025)),
            "gut": V(T.GUT), "exit": V(T.GUT) + V((2.4, 0, 0)), "trail": V((pos[0], pos[1], 0.25)),
            "rock": V((RX + 0.1, RY, 0.25))}[focus]


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
    cam_d.dof.focus_distance = (V(loc) - focus_point(t, focus)).length
    scene.frame_set(f)
    c.samples = max(4, int(SPP[T.shot_set(t)] * QUALITY))
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"rendered {f} ({T.shot_set(t)})", flush=True)
print("done")
