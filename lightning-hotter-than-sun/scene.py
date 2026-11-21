"""Blender scene for "Lightning Is 5x Hotter Than the Sun" (procedural, Cycles, immediate-mode posing per frame).

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
    def __init__(self, name, verts, faces, mat, sets=("storm",), smooth=True):
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
SETS = {"storm": [], "macro": [], "sun": [], "earth": []}
TEX = os.environ.get("SPACE_TEX", "")
rng = random.Random(7)
nrng = np.random.default_rng(7)


def to_set(name, *objs):
    for o in objs:
        SETS[name].append(o)
    return objs[0] if len(objs) == 1 else objs


# ================================================================= world: storm sky (brightens with every flash)
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
wmr.inputs["From Min"].default_value = -0.1
wmr.inputs["From Max"].default_value = 0.6
wnt.links.new(wsep.outputs["Z"], wmr.inputs["Value"])
wr = ramp(wnt, [(0.0, (0.10, 0.11, 0.16)), (1.0, (0.03, 0.035, 0.06))])
wnt.links.new(wmr.outputs["Result"], wr.inputs[0])
wbg = wnt.nodes.new("ShaderNodeBackground")
wnt.links.new(wr.outputs[0], wbg.inputs["Color"])
WORLD_S = wbg.inputs["Strength"]
wnt.links.new(wbg.outputs[0], wnt.nodes["World Output"].inputs[0])


# ================================================================= STORM set
# ground: dark wet meadow on a gentle hill, with grass tufts
gm, gnt, gout = new_mat("Ground")
gp = node(gnt, "ShaderNodeBsdfPrincipled", Roughness=0.55)
gtc = node(gnt, "ShaderNodeTexCoord")
gnz = node(gnt, "ShaderNodeTexNoise", Scale=0.35, Detail=4.0)
gnt.links.new(gtc.outputs["Object"], gnz.inputs["Vector"])
grp = ramp(gnt, [(0.3, (0.06, 0.08, 0.05)), (0.7, (0.12, 0.13, 0.08))])
gnt.links.new(gnz.outputs["Fac"], grp.inputs[0])
gnt.links.new(grp.outputs[0], gp.inputs["Base Color"])
gn2 = node(gnt, "ShaderNodeTexNoise", Scale=6.0, Detail=3.0)
gnt.links.new(gtc.outputs["Object"], gn2.inputs["Vector"])
gbp = node(gnt, "ShaderNodeBump", Strength=0.6, Distance=0.05)
gnt.links.new(gn2.outputs["Fac"], gbp.inputs["Height"])
gnt.links.new(gbp.outputs["Normal"], gp.inputs["Normal"])
gnt.links.new(gp.outputs[0], gout.inputs[0])
gme = bpy.data.meshes.new("Ground")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=160, y_segments=160, size=160)


def hill(x, y):
    return 2.2 * math.exp(-((x / 9.0) ** 2 + (y / 7.0) ** 2)) + 0.5 * math.sin(x * 0.05) * math.sin(y * 0.07) \
        + (0.04 * max(0.0, y - 20) ** 1.25 if y > 20 else 0.0)


for v_ in bm.verts:
    v_.co.z = hill(v_.co.x, v_.co.y)
bm.to_mesh(gme)
bm.free()
gme.shade_smooth()
GROUND = bpy.data.objects.new("Ground", gme)
col.objects.link(GROUND)
GROUND.data.materials.append(gm)
to_set("storm", GROUND)

grass_m, _ = principled("Grass", (0.05, 0.07, 0.03), rough=0.6)
gv, gf = [], []
for _ in range(9000):
    x_, y_ = rng.uniform(-30, 30), rng.uniform(-22, 40)
    if math.hypot(x_, y_) < 0.8:
        continue
    h_ = rng.uniform(0.15, 0.55)
    z_ = hill(x_, y_)
    a_ = rng.uniform(0, 6.28)
    w_ = 0.015
    lx, ly = rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15)
    o = len(gv)
    gv += [(x_ - w_ * math.cos(a_), y_ - w_ * math.sin(a_), z_), (x_ + w_ * math.cos(a_), y_ + w_ * math.sin(a_), z_),
           (x_ + lx, y_ + ly, z_ + h_)]
    gf.append([o, o + 1, o + 2])
to_set("storm", obj_from("Grass", gv, gf, grass_m, smooth=False))

# the lone tree on the hilltop (the strike target)
TREE_TOP = V((0.0, 0.0, hill(0, 0) + 5.6))
bark_m, _ = principled("Bark", (0.03, 0.025, 0.02), rough=0.8, bump=0.6, bump_scale=8)
leaf_m, _ = principled("Leaves", (0.015, 0.03, 0.012), rough=0.8, bump=0.8, bump_scale=4)
tb = Builder()
lb = Builder()
base = V((0, 0, hill(0, 0) - 0.2))
trunk = [base + V((0.15 * math.sin(k * 0.9), 0.1 * math.cos(k * 0.7), 4.2 * k / 7)) for k in range(8)]
to_set("storm", tube("Trunk", trunk, [0.32 - 0.03 * k for k in range(8)], bark_m, seg=12))
for k in range(5):
    a_ = 2 * math.pi * k / 5 + 0.3
    p0 = trunk[4 + k % 3]
    p1 = p0 + V((1.6 * math.cos(a_), 1.4 * math.sin(a_), 1.2))
    to_set("storm", tube(f"Branch{k}", [p0, (p0 + p1) / 2 + V((0, 0, 0.3)), p1], [0.12, 0.08, 0.04], bark_m, seg=8))
for _ in range(90):
    r_ = rng.uniform(0.35, 0.8)
    a_, d_ = rng.uniform(0, 6.28), rng.uniform(0, 2.2) ** 0.8
    lb.sphere((d_ * math.cos(a_), d_ * math.sin(a_) * 0.85, hill(0, 0) + 4.6 + rng.uniform(-0.7, 0.9) - 0.15 * d_), (r_ * 1.15, r_, r_ * 0.85))
to_set("storm", lb.build("Canopy", leaf_m))

# distant tree line + far hills (silhouettes against the flashes)
far_m, _ = principled("Far", (0.01, 0.012, 0.01), rough=0.9)
fb = Builder()
for _ in range(70):
    x_ = rng.uniform(-70, 70)
    y_ = rng.uniform(45, 70)
    r_ = rng.uniform(1.5, 3.5)
    fb.sphere((x_, y_, hill(x_, y_) + r_ * 0.6), (r_, r_, r_ * 1.2))
to_set("storm", fb.build("TreeLine", far_m))

# cloud ceiling: a lumpy dark layer that catches the light of every flash
cm, cnt, cout = new_mat("Clouds")
cp = node(cnt, "ShaderNodeBsdfPrincipled", Roughness=1.0)
cp.inputs["Specular IOR Level"].default_value = 0.0
ctc = node(cnt, "ShaderNodeTexCoord")
cnz = node(cnt, "ShaderNodeTexNoise", Scale=0.08, Detail=6.0)
cnt.links.new(ctc.outputs["Object"], cnz.inputs["Vector"])
crp = ramp(cnt, [(0.35, (0.10, 0.11, 0.14)), (0.7, (0.35, 0.36, 0.42))])
cnt.links.new(cnz.outputs["Fac"], crp.inputs[0])
cnt.links.new(crp.outputs[0], cp.inputs["Base Color"])
cbp = node(cnt, "ShaderNodeBump", Strength=1.0, Distance=1.5)
cnt.links.new(cnz.outputs["Fac"], cbp.inputs["Height"])
cnt.links.new(cbp.outputs["Normal"], cp.inputs["Normal"])
cnt.links.new(cp.outputs[0], cout.inputs[0])
cme = bpy.data.meshes.new("Clouds")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=120, y_segments=120, size=220)
for v_ in bm.verts:
    x_, y_ = v_.co.x, v_.co.y
    v_.co.z = 15.5 + 1.6 * math.sin(x_ * 0.11) * math.sin(y_ * 0.09) + 0.9 * math.sin(x_ * 0.31 + y_ * 0.23) \
        - 0.02 * max(0.0, -y_ + 0)
bm.to_mesh(cme)
bm.free()
cme.shade_smooth()
CLOUDS = bpy.data.objects.new("Clouds", cme)
col.objects.link(CLOUDS)
CLOUDS.data.materials.append(cm)
for f_ in CLOUDS.data.polygons:
    f_.flip()
CLOUDS.visible_shadow = False
CLOUDS.visible_diffuse = False                    # the cloud deck must not block the dim ambient light
to_set("storm", CLOUDS)

# rain: thin streaks falling (phase-locked to the loop clock)
rain_m, RAIN_A, _ = fade_emit_mat("Rain", (0.6, 0.7, 0.85), 0.25)
NR = 900
R_X = nrng.uniform(-14, 18, NR)
R_Y = nrng.uniform(-9, 14, NR)
R_Z0 = nrng.uniform(0, 14, NR)
R_LEN = nrng.uniform(0.35, 0.7, NR)
rain_faces = []
for i in range(NR):
    o = i * 4
    rain_faces.append([o, o + 1, o + 2, o + 3])


def rain_verts(te, cam_loc):
    z = (R_Z0 - 11.0 * te) % 14.0
    out = np.zeros((NR * 4, 3))
    w = 0.004
    for i in range(NR):
        x, y = R_X[i] + 0.25 * (z[i] / 14), R_Y[i]
        out[i * 4:i * 4 + 4] = [(x - w, y, z[i]), (x + w, y, z[i]), (x + w + 0.03, y, z[i] + R_LEN[i]), (x - w + 0.03, y, z[i] + R_LEN[i])]
    return out


RAIN = Dyn("Rain", rain_verts(0.0, (0, 0, 0)), rain_faces, rain_m, sets=("storm",), smooth=False)
RAIN.o.visible_shadow = False
no_bounce([RAIN.o])


# ---- bolts: random-midpoint paths with branches
bolt_path = T.bolt_path


def make_bolt(name, top, bottom, seed, set_name, scale=1.0):
    main = bolt_path(top, bottom, 0.75 * scale, 7, seed)
    r = np.random.default_rng(seed + 1)
    branches = []
    for k in range(9):
        i0 = int(r.uniform(0.08, 0.7) * len(main))
        p0 = main[i0]
        dirn = main[min(i0 + 6, len(main) - 1)] - main[i0]
        dirn = dirn / (np.linalg.norm(dirn) + 1e-9)
        end = p0 + (dirn * 0.8 + np.array([r.normal(0, 0.6), r.normal(0, 0.3), -0.4])) * r.uniform(1.0, 2.6) * scale
        branches.append((i0, bolt_path(p0, end, 0.25 * scale, 4, seed + 10 + k)))
    return main, branches


core_m, CORE_S = emit_mat("BoltCore", (0.85, 0.9, 1.0), 0.0)
glow_m, GLOW_A, GLOW_S = fade_emit_mat("BoltGlow", (0.55, 0.65, 1.0), 6.0)
soften(glow_m)


class Bolt:
    """Main channel + branches as tubes; `reveal` (0..1 from the cloud down) draws the stepped leader."""
    def __init__(self, name, top, bottom, seed, set_name, r_core, scale=1.0):
        self.main, self.branches = make_bolt(name, top, bottom, seed, set_name, scale)
        self.r = r_core
        self.paths = [self.main] + [b for _, b in self.branches]
        self.cores, self.glows = [], []
        for k, p in enumerate(self.paths):
            n = len(p)
            rc = self.r * (1.0 if k == 0 else 0.45)
            self.cores.append(Dyn(f"{name}Core{k}", tube_verts(p, np.full(n, rc), 6), tube_faces(n, 6), core_m, sets=(set_name,)))
            self.glows.append(Dyn(f"{name}Glow{k}", tube_verts(p, np.full(n, rc * 6), 8), tube_faces(n, 8), glow_m, sets=(set_name,)))
        for d in self.cores + self.glows:
            d.o.visible_shadow = False
            no_bounce([d.o])
        self.z_top, self.z_bot = top[2], bottom[2]

    def pose(self, brightness, reveal=1.0):
        on = brightness > 0.003 or reveal < 1.0
        for k, p in enumerate(self.paths):
            n = len(p)
            if k == 0:
                zc = self.z_top - (self.z_top - self.z_bot) * reveal
            else:
                i0 = self.branches[k - 1][0]
                zc = self.z_top - (self.z_top - self.z_bot) * reveal if reveal < 1 else -1e9
                if p[0][2] < zc and reveal < 1:
                    zc = 1e9                     # branch not reached yet
            q = p.copy()
            if reveal < 1:
                below = q[:, 2] < zc
                if below.any():
                    first = np.argmax(below)
                    q[first:] = q[max(first - 1, 0)]
            rc = self.r * (1.0 if k == 0 else 0.45)
            self.cores[k].set(tube_verts(q, np.full(n, rc), 6))
            self.glows[k].set(tube_verts(q, np.full(n, rc * 6), 8))
            vis = on and not (reveal < 1 and zc > 1e8)
            self.cores[k].o.hide_render = not vis
            self.glows[k].o.hide_render = not vis


B_MAIN = Bolt("Bolt", (1.2, 2.5, 15.0), tuple(TREE_TOP), 3, "storm", 0.04)
B_FAR = Bolt("BoltFar", (-34.0, 52.0, 15.5), (-30.0, 50.0, hill(-30, 50)), 9, "storm", 0.09, scale=1.6)
lamps = []
for k, z_ in enumerate((3.0, 8.0, 13.0)):
    ld = bpy.data.lights.new(f"BoltLamp{k}", "POINT")
    ld.color, ld.shadow_soft_size = (0.75, 0.82, 1.0), 0.3
    lo = bpy.data.objects.new(f"BoltLamp{k}", ld)
    p_ = B_MAIN.main[int((1 - z_ / 15.5) * (len(B_MAIN.main) - 1))]
    lo.location = tuple(p_)
    col.objects.link(lo)
    lamps.append(lo)
far_ld = bpy.data.lights.new("FarLamp", "POINT")
far_ld.color, far_ld.shadow_soft_size = (0.75, 0.82, 1.0), 2.0
far_lo = bpy.data.objects.new("FarLamp", far_ld)
far_lo.location = (-30, 50, 10)
col.objects.link(far_lo)
moon_d = bpy.data.lights.new("Ambient", "SUN")
moon_d.energy, moon_d.color, moon_d.angle = 1.4, (0.6, 0.7, 1.0), 0.5
moon_o = bpy.data.objects.new("Ambient", moon_d)
moon_o.rotation_euler = (math.radians(50), 0, math.radians(30))
col.objects.link(moon_o)
to_set("storm", *lamps, far_lo, moon_o)
# a scorch glow on the tree top right after the hit
spark_m, SPARK_A, _ = fade_emit_mat("Impact", (1.0, 0.8, 0.5), 30.0)
soften(spark_m)
IMPACT = sph("Impact", tuple(TREE_TOP), 0.6, spark_m, u=24, v=12)
IMPACT.visible_shadow = False
no_bounce([IMPACT])
to_set("storm", IMPACT)


# ================================================================= MACRO set: a glowing channel segment
MX, MY, MZ = T.MACRO
mback_m, _ = emit_mat("MacroBack", (0.004, 0.005, 0.012), 1.0)
to_set("macro", sph("MacroBack", (MX, MY, MZ), 40.0, mback_m, u=32, v=16))
seg_path = T.SEG_PATH
R_INCH = 0.0127                                    # macro units are metres: a 1-inch-wide channel
MC = [Dyn("MacroCore", tube_verts(seg_path, np.full(len(seg_path), R_INCH), 16), tube_faces(len(seg_path), 16), core_m, sets=("macro",))]
MG = Dyn("MacroGlow", tube_verts(seg_path, np.full(len(seg_path), R_INCH * 3), 16), tube_faces(len(seg_path), 16), glow_m, sets=("macro",))
for d in MC + [MG]:
    d.o.visible_shadow = False
    no_bounce([d.o])
heat_m, HEAT_A, _ = fade_emit_mat("Heat", (1.0, 0.55, 0.25), 3.0)
soften(heat_m)
HEAT = Dyn("HeatHalo", tube_verts(seg_path, np.full(len(seg_path), 0.09), 16), tube_faces(len(seg_path), 16), heat_m, sets=("macro",))
HEAT.o.visible_shadow = False
CH_X, CH_Y = T.CH_X, T.CH_Y                       # channel centre at the ruler height
no_bounce([HEAT.o])
# shock wave: two expanding transparent cylinders with a bright rim
shock_m, SHOCK_A, _ = fade_emit_mat("Shock", (0.45, 0.72, 1.0), 7.0)
soften(shock_m)
SHOCKS = []
for k in range(2):
    ring_pts = [(math.cos(2 * math.pi * i / 96), math.sin(2 * math.pi * i / 96), 0.0) for i in range(97)]
    o_ = tube(f"Shock{k}", ring_pts, [0.012] * 97, shock_m.copy(), seg=8)
    o_.location = (CH_X, MY, MZ + 0.2)
    o_.visible_shadow = False
    no_bounce([o_])
    to_set("macro", o_)
    SHOCKS.append(o_)
# ruler (inch marks) next to the channel for the "an inch wide" shot
ruler_img = os.path.join(TEX, "ruler.png")
if not os.path.exists(ruler_img):
    from PIL import Image as _I, ImageDraw as _D, ImageFont as _F
    W_, H_ = 2400, 400
    im_ = _I.new("RGB", (W_, H_), (232, 214, 160))
    d_ = _D.Draw(im_)
    try:
        f_ = _F.truetype(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viral-hooks", "fonts", "Montserrat-Bold.ttf"), 90)
    except Exception:
        f_ = _F.load_default()
    for k in range(0, 49):                         # 3 inches, 1/16 marks
        x_ = 100 + k * (2200 / 48)
        ln = 220 if k % 16 == 0 else (150 if k % 8 == 0 else (100 if k % 4 == 0 else 60))
        d_.rectangle([x_ - 3, 0, x_ + 3, ln], fill=(30, 25, 20))
        if k % 16 == 0:
            d_.text((x_, 330), str(k // 16), fill=(30, 25, 20), font=f_, anchor="mm")
    im_.save(ruler_img)
rul_m, rnt, rout = new_mat("Ruler")
rp = node(rnt, "ShaderNodeBsdfPrincipled", Roughness=0.5)
rtx = rnt.nodes.new("ShaderNodeTexImage")
rtx.image = bpy.data.images.load(ruler_img)
rtc = node(rnt, "ShaderNodeTexCoord")
rnt.links.new(rtc.outputs["UV"], rtx.inputs["Vector"])
rnt.links.new(rtx.outputs["Color"], rp.inputs["Base Color"])
rnt.links.new(rp.outputs[0], rout.inputs[0])
RL = 0.0762 * 2400 / 2200                          # 3 in of marks + margins
rme = bpy.data.meshes.new("Ruler")
rme.from_pydata([(0, 0, 0), (RL, 0, 0), (RL, 0, RL / 6), (0, 0, RL / 6)], [], [[0, 1, 2, 3]])
uvl = rme.uv_layers.new()
for i_, uv_ in enumerate(((0, 1), (1, 1), (1, 0), (0, 0))):
    uvl.data[i_].uv = uv_
RULER = bpy.data.objects.new("Ruler", rme)
RULER.data.materials.append(rul_m)
col.objects.link(RULER)
to_set("macro", RULER)
rl_d = bpy.data.lights.new("RulerFill", "AREA")
rl_d.energy, rl_d.size = 0.6, 0.2
rl_o = bpy.data.objects.new("RulerFill", rl_d)
col.objects.link(rl_o)
to_set("macro", rl_o)


# ================================================================= SUN set
SX, SY, SZ = T.SUNSET_
sunsurf_m, ssnt, ssout = new_mat("SunSurface")
sstc = node(ssnt, "ShaderNodeTexCoord")
ssnz = ssnt.nodes.new("ShaderNodeTexNoise")
ssnz.noise_dimensions = "4D"
ssnz.inputs["Scale"].default_value = 9.0
ssnz.inputs["Detail"].default_value = 8.0
ssnt.links.new(sstc.outputs["Object"], ssnz.inputs["Vector"])
SUN_W = ssnz.inputs["W"]
ssrp = ramp(ssnt, [(0.3, (1.0, 0.22, 0.02)), (0.55, (1.0, 0.45, 0.06)), (0.75, (1.0, 0.75, 0.3))])
ssnt.links.new(ssnz.outputs["Fac"], ssrp.inputs[0])
ssem = node(ssnt, "ShaderNodeEmission", Strength=1.3)
ssnt.links.new(ssrp.outputs[0], ssem.inputs["Color"])
ssnt.links.new(ssem.outputs[0], ssout.inputs[0])
SUN = sph("Sun", (SX, SY, SZ), 1.4, sunsurf_m, u=128, v=64)
corona_m, COR_A, _ = fade_emit_mat("Corona", (1.0, 0.5, 0.14), 1.1)
soften(corona_m)
COR_A.default_value = 0.35
CORONA = sph("Corona", (SX, SY, SZ), 2.3, corona_m, u=64, v=32)
for o_ in (SUN, CORONA):
    o_.visible_shadow = False
    no_bounce([o_])
to_set("sun", SUN, CORONA)


# ================================================================= EARTH set (night side with flashes)
EX, EY, EZ = T.EARTHSET
def lonlat_vector(nt, coord_socket):
    """Object-space position -> equirectangular UV (u = lon/2pi + .5, v = lat/pi + .5)."""
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord_socket, sep.inputs[0])
    at = nt.nodes.new("ShaderNodeMath")
    at.operation = "ARCTAN2"
    nt.links.new(sep.outputs["Y"], at.inputs[0])
    nt.links.new(sep.outputs["X"], at.inputs[1])
    u = nt.nodes.new("ShaderNodeMath")
    u.operation = "MULTIPLY_ADD"
    nt.links.new(at.outputs[0], u.inputs[0])
    u.inputs[1].default_value = 1 / (2 * math.pi)
    u.inputs[2].default_value = 0.5
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    nt.links.new(coord_socket, ln.inputs[0])
    dv = nt.nodes.new("ShaderNodeMath")
    dv.operation = "DIVIDE"
    nt.links.new(sep.outputs["Z"], dv.inputs[0])
    nt.links.new(ln.outputs["Value"], dv.inputs[1])
    asn = nt.nodes.new("ShaderNodeMath")
    asn.operation = "ARCSINE"
    nt.links.new(dv.outputs[0], asn.inputs[0])
    v = nt.nodes.new("ShaderNodeMath")
    v.operation = "MULTIPLY_ADD"
    nt.links.new(asn.outputs[0], v.inputs[0])
    v.inputs[1].default_value = 1 / math.pi
    v.inputs[2].default_value = 0.5
    cmb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(u.outputs[0], cmb.inputs["X"])
    nt.links.new(v.outputs[0], cmb.inputs["Y"])
    return cmb.outputs[0]


earth_m, ent, eout = new_mat("EarthNight")
etc = node(ent, "ShaderNodeTexCoord")
eimg = ent.nodes.new("ShaderNodeTexImage")
eimg.image = bpy.data.images.load(os.path.join(TEX, "bmng.jpg"))
ent.links.new(lonlat_vector(ent, etc.outputs["Object"]), eimg.inputs["Vector"])
ep = node(ent, "ShaderNodeBsdfPrincipled", Roughness=0.8)
ent.links.new(eimg.outputs["Color"], ep.inputs["Base Color"])
ent.links.new(ep.outputs[0], eout.inputs[0])
EARTH = sph("EarthN", (EX, EY, EZ), 1.0, earth_m, u=192, v=96)
def atmo_mat(name, sun_pos):
    """Thin glowing shell: bright blue at the limb on the day side, fading into the night side."""
    m, nt, out = new_mat(name)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    sub.inputs[0].default_value = sun_pos
    nt.links.new(oi.outputs["Location"], sub.inputs[1])
    nrm = nt.nodes.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    nt.links.new(sub.outputs[0], nrm.inputs[0])
    rel = nt.nodes.new("ShaderNodeVectorMath")              # outward direction from the planet centre
    rel.operation = "SUBTRACT"                                # (not the shading normal: back faces flip it)
    nt.links.new(geo.outputs["Position"], rel.inputs[0])
    nt.links.new(oi.outputs["Location"], rel.inputs[1])
    reln = nt.nodes.new("ShaderNodeVectorMath")
    reln.operation = "NORMALIZE"
    nt.links.new(rel.outputs[0], reln.inputs[0])
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(reln.outputs[0], dot.inputs[0])
    nt.links.new(nrm.outputs[0], dot.inputs[1])
    lit = nt.nodes.new("ShaderNodeMapRange")
    lit.inputs["From Min"].default_value = -0.15
    lit.inputs["From Max"].default_value = 0.5
    nt.links.new(dot.outputs["Value"], lit.inputs["Value"])
    lw = node(nt, "ShaderNodeLayerWeight", Blend=0.5)        # Facing: 0 towards the camera, 1 at the limb
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 7.0
    nt.links.new(lw.outputs["Facing"], pw.inputs[0])
    inv = nt.nodes.new("ShaderNodeMath")                     # the outermost edge fades out (soft limb)
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], inv.inputs[1])
    edge = nt.nodes.new("ShaderNodeMath")
    edge.operation = "POWER"
    edge.inputs[1].default_value = 0.3
    nt.links.new(inv.outputs[0], edge.inputs[0])
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY"
    nt.links.new(pw.outputs[0], m1.inputs[0])
    nt.links.new(edge.outputs[0], m1.inputs[1])
    m2 = nt.nodes.new("ShaderNodeMath")
    m2.operation = "MULTIPLY"
    nt.links.new(m1.outputs[0], m2.inputs[0])
    nt.links.new(lit.outputs["Result"], m2.inputs[1])
    em = node(nt, "ShaderNodeEmission", Color=(0.22, 0.48, 1.0, 1))
    sm = nt.nodes.new("ShaderNodeMath")
    sm.operation = "MULTIPLY"
    sm.inputs[1].default_value = 6.0
    nt.links.new(m2.outputs[0], sm.inputs[0])
    nt.links.new(sm.outputs[0], em.inputs["Strength"])
    tr = node(nt, "ShaderNodeBsdfTransparent")
    ad = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], ad.inputs[0])
    nt.links.new(em.outputs[0], ad.inputs[1])
    nt.links.new(ad.outputs[0], out.inputs[0])
    return m


ATMO = sph("EarthNAtmo", (EX, EY, EZ), 1.02, atmo_mat("AtmoN", (EX - 1e5, EY + 3e4, EZ + 2e4)), u=128, v=64)
no_bounce([ATMO])
esun_d = bpy.data.lights.new("EarthSun", "SUN")
esun_d.energy, esun_d.color = 2.2, (1.0, 0.97, 0.92)
esun = bpy.data.objects.new("EarthSun", esun_d)
esun.rotation_euler = V((-1.0, 0.3, 0.2)).normalized().to_track_quat("Z", "Y").to_euler()
col.objects.link(esun)
fl_m, _ = emit_mat("Flash", (0.75, 0.82, 1.0), 40.0)
fl_halo_m, FLH_A, _ = fade_emit_mat("FlashHalo", (0.6, 0.7, 1.0), 6.0)
soften(fl_halo_m)
NFL = 260
frng = np.random.default_rng(13)
FL_LAT = np.radians(np.clip(frng.normal(0, 18, NFL), -45, 45))
FL_LON = np.radians(frng.uniform(-180, 180, NFL))
FL_T = np.sort(frng.uniform(0, 4.2, NFL))           # flash times within the shot (seconds from its start)
FLASHES = []
for i in range(NFL):
    d = V((math.cos(FL_LAT[i]) * math.cos(FL_LON[i]), math.cos(FL_LAT[i]) * math.sin(FL_LON[i]), math.sin(FL_LAT[i])))
    h_ = sph(f"Fl{i}", tuple(V((EX, EY, EZ)) + d * 1.012), 0.03, fl_halo_m, u=12, v=6)
    h_.visible_shadow = False
    no_bounce([h_])
    FLASHES.append((h_, d))
to_set("earth", EARTH, ATMO, esun, *[h for h, _ in FLASHES])
EARTH_SPIN0 = math.radians(-20)


# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.clip_start = 0.005
cam_d.clip_end = 5000
cam = bpy.data.objects.new("Cam", cam_d)
cam.rotation_mode = "QUATERNION"
col.objects.link(cam)
scene.camera = cam


# ================================================================= per-frame posing
def pose_storm(t, te, i):
    f0 = T.flash(te, 0)
    f1 = T.flash(te, 1)
    lead = T.leader(te) if i == len(T.SHOTS) - 1 else 0.0
    if f0 > 0.003:
        B_MAIN.pose(f0, 1.0)
    elif lead > 0:
        B_MAIN.pose(0.0, lead)
    else:
        B_MAIN.pose(0.0, 1.0)
    B_FAR.pose(f1, 1.0)
    lead_b = 0.18 if lead > 0 and f0 <= 0.003 else 0.0
    b = max(f0, lead_b)
    CORE_S.default_value = 60.0 * b
    GLOW_A.default_value = min(1.0, 0.9 * b + 0.25 * lead_b)
    for k, lo in enumerate(lamps):
        lo.data.energy = 6000.0 * f0 + 150.0 * lead_b
    far_lo.data.energy = 40000.0 * f1
    amb = 0.5 + 0.5 * math.sin(te * 1.7) * math.sin(te * 0.9 + 1)      # distant cloud flicker
    WORLD_S.default_value = 1.6 + 5.0 * f0 + 3.0 * f1 + 1.5 * max(0.0, amb - 0.75) * 4
    SPARK_A.default_value = min(1.0, 2.0 * f0)
    IMPACT.hide_render = f0 < 0.01
    RAIN.set(rain_verts(te, None))
    RAIN_A.default_value = 0.55 + 1.5 * max(f0, f1)


def pose_macro(t, i):
    # the channel is held "lit" (slow motion); it flickers slightly
    fl = 0.85 + 0.15 * math.sin(t * 37) * math.sin(t * 23)
    CORE_S.default_value = (4.0 if i == 4 else 30.0) * fl
    GLOW_A.default_value = 0.8 * fl
    heat = 0.0
    if i == 1:
        heat = T.smoother((t - T.T_50 + 0.6) / 1.2)
    HEAT.o.hide_render = heat < 0.01
    HEAT_A.default_value = 0.7 * heat
    for k, o in enumerate(SHOCKS):
        o.hide_render = True
    if i == 3:
        for k, (r, a) in enumerate(T.shock(t)):
            o = SHOCKS[k]
            o.hide_render = a <= 0.01
            o.scale = (r, r, r)
            next(n for n in o.data.materials[0].node_tree.nodes if n.type == "VALUE").outputs[0].default_value = 0.7 * a
    RULER.hide_render = i != 4
    MG.o.hide_render = i == 4                    # the macro of the ruler: no glow haze over the scale
    if i == 4:
        RULER.location = (MX - 0.0127 - 0.004 - RL * 100 / 2400 * 0 - 0.0381 + 0.0127 * 0, MY - 0.03, MZ + 0.37)
        # the 1-inch mark span [1, 2] sits across the channel
        x_in = 100 + 16 * (2200 / 48)                # pixel of the "1" mark
        RULER.location = (CH_X - 0.0127 - x_in / 2400 * RL, CH_Y - 0.03, MZ + 0.345)
        rl_o.location = (MX + 0.05, MY - 0.15, MZ + 0.5)
        rl_o.rotation_euler = (V((MX, MY, MZ + 0.4)) - V(rl_o.location)).to_track_quat("-Z", "Y").to_euler()


def pose_earth(t):
    t0 = T.SHOTS[5][0]
    u = t - t0
    EARTH.rotation_euler = (0, 0, EARTH_SPIN0 + 0.05 * u)
    rot = Matrix.Rotation(EARTH_SPIN0 + 0.05 * u, 3, "Z")
    cam_loc = V(T.camera(t)[0])
    for k, (h_, d) in enumerate(FLASHES):
        dt = u - FL_T[k]
        on = 0 <= dt < 0.25
        h_.hide_render = not on
        if on:
            p = V((EX, EY, EZ)) + (rot @ d) * 1.012
            h_.location = p
            s = 0.016 + 0.03 * math.exp(-dt / 0.05)
            h_.scale = (s / 0.03,) * 3
    FLH_A.default_value = 1.0
    SUN_W.default_value = 0.0


def pose(t):
    st = T.shot_set(t)
    i = T.shot_index(t)
    te = T.env_t(t)
    for name, objs in SETS.items():
        for o in objs:
            o.hide_render = name != st
    scene.view_settings.exposure = 1.3 if st == "storm" else 0.0
    if st == "storm":
        pose_storm(t, te, i)
    else:
        WORLD_S.default_value = 0.0              # space / macro sets: black background, no storm sky
    if st == "macro":
        pose_macro(t, i)
    elif st == "sun":
        SUN_W.default_value = 0.2 * t
    elif st == "earth":
        pose_earth(t)


# ================================================================= render
r = scene.render
r.engine = "CYCLES"
r.resolution_x, r.resolution_y = RES
r.resolution_percentage = 100
r.image_settings.file_format = "PNG"
r.use_motion_blur = False
r.use_persistent_data = False
c = scene.cycles
c.device = "CPU"
c.use_adaptive_sampling = True
c.adaptive_threshold = 0.07
c.use_denoising = True
c.denoising_quality = "BALANCED"
c.denoising_prefilter = "FAST"
c.max_bounces = 4
c.diffuse_bounces = 1
c.glossy_bounces = 1
c.transparent_max_bounces = 16
c.transmission_bounces = 1
c.caustics_reflective = False
c.caustics_refractive = False
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0
except Exception:
    pass
SPP = {"storm": 10, "macro": 10, "sun": 8, "earth": 10}
if os.environ.get("LT_EXP"):
    exec(os.environ["LT_EXP"])

for f in FRAMES:
    t = f / T.FPS
    path = os.path.join(OUT, f"f_{f:04d}.png")
    if os.path.exists(path):
        continue
    pose(t)
    loc, tgt, lens = T.camera(t)
    cam.location = loc
    cam.rotation_quaternion = (V(tgt) - V(loc)).to_track_quat("-Z", "Y")
    cam_d.lens = lens
    scene.frame_set(f)
    c.samples = max(4, int(SPP[T.shot_set(t)] * QUALITY))
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"rendered {f} ({T.shot_set(t)})", flush=True)
print("done")
