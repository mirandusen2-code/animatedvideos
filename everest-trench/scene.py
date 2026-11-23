"""Blender scene for "Mount Everest Would Vanish in the Mariana Trench" (real elevation data, Cycles, posed per frame).

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
SETS = {"tank": [], "macro": []}
TEX = os.environ.get("SPACE_TEX", os.path.join(os.path.dirname(OUT.rstrip("/")), "tex"))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
rng = np.random.default_rng(5)


def to_set(name, *objs):
    for o in objs:
        SETS[name].append(o)
    return objs[0] if len(objs) == 1 else objs


def math_node(nt, op, a=None, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def world_z(nt):
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    return sep.outputs["Z"]


# ---- underwater look: every surface in the water fades towards the colour of the deep with depth.
# VIS (one value per material, set per shot) scales how strongly the deep swallows the surface.
DEPTH_N = -T.FLOOR_Z
D3000 = 3000 * T.FT / DEPTH_N
VIS_SOCKETS = []
FOG_COLS = [(0.0, (0.05, 0.36, 0.48)), (D3000, (0.016, 0.12, 0.22)), (0.35, (0.004, 0.03, 0.075)), (1.0, (0.001, 0.006, 0.02))]


def depth_mix(nt, shader_socket, out_socket, strength=1.0):
    z = world_z(nt)
    d = math_node(nt, "DIVIDE", z, -DEPTH_N)
    d = math_node(nt, "MAXIMUM", d, 0.0)
    under = math_node(nt, "LESS_THAN", z, 0.0)
    fr = ramp(nt, [(0.0, (0.16, 0.16, 0.16)), (D3000, (0.42, 0.42, 0.42)), (0.3, (0.8, 0.8, 0.8)), (1.0, (0.95, 0.95, 0.95))])
    nt.links.new(d, fr.inputs[0])
    vis = node(nt, "ShaderNodeValue")
    vis.outputs[0].default_value = 1.0
    VIS_SOCKETS.append(vis.outputs[0])
    fac = math_node(nt, "MULTIPLY", fr.outputs[0], under)
    fac = math_node(nt, "MULTIPLY", fac, vis.outputs[0])
    cr = ramp(nt, FOG_COLS)
    nt.links.new(d, cr.inputs[0])
    em = node(nt, "ShaderNodeEmission", Strength=strength)
    nt.links.new(cr.outputs[0], em.inputs["Color"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fac, mix.inputs[0])
    nt.links.new(shader_socket, mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out_socket)


def rock_principled(nt, base_socket_or_color, bump=0.5, scale=1.5, rough=0.85):
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=rough)
    p.inputs["Specular IOR Level"].default_value = 0.25
    if isinstance(base_socket_or_color, tuple):
        p.inputs["Base Color"].default_value = (*base_socket_or_color, 1)
    else:
        nt.links.new(base_socket_or_color, p.inputs["Base Color"])
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=scale, Detail=8.0, Roughness=0.62)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = node(nt, "ShaderNodeBump", Strength=bump, Distance=0.3)
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    return p, tc, nz


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
wr = ramp(wnt, [(0.0, (0.004, 0.007, 0.014)), (0.5, (0.010, 0.020, 0.040)), (1.0, (0.030, 0.055, 0.10))])
wnt.links.new(wsep.outputs["Z"], wr.inputs[0])
wbg = wnt.nodes.new("ShaderNodeBackground")
WORLD_S = wbg.inputs["Strength"]
WORLD_S.default_value = 1.6
wnt.links.new(wr.outputs[0], wbg.inputs["Color"])
wnt.links.new(wbg.outputs[0], wnt.nodes["World Output"].inputs[0])

sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy = 5.5
sun_d.angle = math.radians(3)
sun_d.color = (1.0, 0.96, 0.9)
SUN = bpy.data.objects.new("Sun", sun_d)
SUN.rotation_euler = (V((-0.45, -0.55, 1.0)).normalized()).to_track_quat("Z", "Y").to_euler()
col.objects.link(SUN)
to_set("tank", SUN)


# ================================================================= the trench block (real bathymetry)
TD = np.load(os.path.join(DATA, "trench_dem.npy"))               # metres, 101 x 101 over 60 x 60 km, axis along y
NT = TD.shape[0]
xs = np.linspace(-T.HALF, T.HALF, NT)
BASE_Z = -12.6 * T.KM
tz = TD / 1000.0 * T.KM
tv = [(xs[i], xs[j], tz[j, i]) for j in range(NT) for i in range(NT)]
tf = [[j * NT + i, j * NT + i + 1, (j + 1) * NT + i + 1, (j + 1) * NT + i] for j in range(NT - 1) for i in range(NT - 1)]
ring = [(i, 0) for i in range(NT)] + [(NT - 1, j) for j in range(1, NT)] + \
       [(i, NT - 1) for i in range(NT - 2, -1, -1)] + [(0, j) for j in range(NT - 2, 0, -1)]
off = len(tv)
for i, j in ring:
    tv.append((xs[i], xs[j], BASE_Z))
nring = len(ring)
wall_faces = []
for k in range(nring):
    i0, j0 = ring[k]
    i1, j1 = ring[(k + 1) % nring]
    wall_faces.append([j0 * NT + i0, off + k, off + (k + 1) % nring, j1 * NT + i1])
bottom = [off + k for k in range(nring)][::-1]

# seabed: sediment with rocky bumps, swallowed by the deep
sb_m, nt, out = new_mat("Seabed")
p, tc_, nz_ = rock_principled(nt, (0.30, 0.27, 0.22), bump=0.6, scale=0.35)
cv = ramp(nt, [(0.35, (0.22, 0.20, 0.17)), (0.65, (0.36, 0.33, 0.27))])
nt.links.new(nz_.outputs["Fac"], cv.inputs[0])
nt.links.new(cv.outputs[0], p.inputs["Base Color"])
depth_mix(nt, p.outputs[0], out.inputs[0])

# cut faces of the block: layered crust
wl_m, nt, out = new_mat("Crust")
z_ = world_z(nt)
wv = node(nt, "ShaderNodeTexWave", Scale=0.08, Distortion=6.0, Detail=4.0)
wv.bands_direction = "Z"
tcw = node(nt, "ShaderNodeTexCoord")
nt.links.new(tcw.outputs["Object"], wv.inputs["Vector"])
cw = ramp(nt, [(0.0, (0.10, 0.075, 0.06)), (0.45, (0.20, 0.15, 0.11)), (0.7, (0.14, 0.11, 0.09)), (1.0, (0.26, 0.20, 0.15))])
nt.links.new(wv.outputs["Fac"], cw.inputs[0])
dk = math_node(nt, "MAP_RANGE" if False else "DIVIDE", z_, BASE_Z)        # 0 at sea level .. 1 at the base
dkr = ramp(nt, [(0.0, (1.0, 1.0, 1.0)), (1.0, (0.35, 0.35, 0.4))])
nt.links.new(dk, dkr.inputs[0])
mulc = nt.nodes.new("ShaderNodeMix")
mulc.data_type = "RGBA"
mulc.blend_type = "MULTIPLY"
mulc.inputs[0].default_value = 1.0
nt.links.new(cw.outputs[0], mulc.inputs[6])
nt.links.new(dkr.outputs[0], mulc.inputs[7])
p, _, _ = rock_principled(nt, mulc.outputs[2], bump=0.4, scale=0.5)
nt.links.new(p.outputs[0], out.inputs[0])

TRENCH = obj_from("Trench", tv, tf + wall_faces + [bottom], sb_m, smooth=True)
TRENCH.data.materials.append(wl_m)
nf = len(tf)
mi = np.zeros(len(TRENCH.data.polygons), np.int32)
mi[nf:] = 1
TRENCH.data.polygons.foreach_set("material_index", mi)
sm = np.ones(len(TRENCH.data.polygons), bool)
sm[nf:] = False
TRENCH.data.polygons.foreach_set("use_smooth", sm)
to_set("tank", TRENCH)


# ================================================================= the water
def water_side_mat(name):
    m, nt, out = new_mat(name)
    z = world_z(nt)
    d = math_node(nt, "DIVIDE", z, -DEPTH_N)
    d = math_node(nt, "MAXIMUM", d, 0.0)
    cr = ramp(nt, FOG_COLS)
    nt.links.new(d, cr.inputs[0])
    em = node(nt, "ShaderNodeEmission", Strength=1.0)
    nt.links.new(cr.outputs[0], em.inputs["Color"])
    ar = ramp(nt, [(0.0, (0.05, 0.05, 0.05)), (D3000, (0.12, 0.12, 0.12)), (1.0, (0.32, 0.32, 0.32))])
    nt.links.new(d, ar.inputs[0])
    tr = node(nt, "ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(ar.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    gl = node(nt, "ShaderNodeBsdfGlossy", Roughness=0.05)
    fr = node(nt, "ShaderNodeFresnel", IOR=1.33)
    mix2 = nt.nodes.new("ShaderNodeMixShader")
    sc = math_node(nt, "MULTIPLY", fr.outputs[0], 0.5)
    nt.links.new(sc, mix2.inputs[0])
    nt.links.new(mix.outputs[0], mix2.inputs[1])
    nt.links.new(gl.outputs[0], mix2.inputs[2])
    nt.links.new(mix2.outputs[0], out.inputs[0])
    return m


ws_m = water_side_mat("WaterSide")
sv, sf_ = [], []
for k in range(nring):                                   # side panes: from the seabed edge up to sea level
    i, j = ring[k]
    sv += [(xs[i], xs[j], tz[j, i]), (xs[i], xs[j], 0.0)]
for k in range(nring):
    a, b = 2 * k, 2 * ((k + 1) % nring)
    sf_.append([a, b, b + 1, a + 1])
WSIDE = obj_from("WaterSides", sv, sf_, ws_m, smooth=False)
to_set("tank", WSIDE)

# surface: glossy with moving waves, see-through from above
wt_m, nt, out = new_mat("WaterTop")
tr = node(nt, "ShaderNodeBsdfTransparent", Color=(0.75, 0.92, 0.95, 1))
gl = node(nt, "ShaderNodeBsdfGlossy", Roughness=0.06)
tcw = node(nt, "ShaderNodeTexCoord")
wn = node(nt, "ShaderNodeTexNoise", Scale=0.9, Detail=6.0)
wn.noise_dimensions = "4D"
WAVE_W = wn.inputs["W"]
nt.links.new(tcw.outputs["Object"], wn.inputs["Vector"])
bp = node(nt, "ShaderNodeBump", Strength=0.35, Distance=0.4)
nt.links.new(wn.outputs["Fac"], bp.inputs["Height"])
nt.links.new(bp.outputs["Normal"], gl.inputs["Normal"])
fr = node(nt, "ShaderNodeFresnel", IOR=1.33)
nt.links.new(bp.outputs["Normal"], fr.inputs["Normal"])
em = node(nt, "ShaderNodeEmission", Color=(0.05, 0.30, 0.40, 1), Strength=0.35)
mx1 = nt.nodes.new("ShaderNodeMixShader")
mx1.inputs[0].default_value = 0.18
nt.links.new(tr.outputs[0], mx1.inputs[1])
nt.links.new(em.outputs[0], mx1.inputs[2])
mx2 = nt.nodes.new("ShaderNodeMixShader")
frs = math_node(nt, "ADD", fr.outputs[0], 0.08, clamp=True)
nt.links.new(frs, mx2.inputs[0])
nt.links.new(mx1.outputs[0], mx2.inputs[1])
nt.links.new(gl.outputs[0], mx2.inputs[2])
nt.links.new(mx2.outputs[0], out.inputs[0])
WTOP = obj_from("WaterTop", [(-T.HALF, -T.HALF, 0), (T.HALF, -T.HALF, 0), (T.HALF, T.HALF, 0), (-T.HALF, T.HALF, 0)],
                [[0, 1, 2, 3]], wt_m, smooth=False)
to_set("tank", WTOP)

# sunbeams: fade out completely 3,000 ft down
bm_m, nt, out = new_mat("Sunbeam")
z = world_z(nt)
br = ramp(nt, [(0.0, (0.0, 0.0, 0.0)), (0.75, (0.5, 0.5, 0.5)), (1.0, (1.0, 1.0, 1.0))])
bz = math_node(nt, "DIVIDE", z, 3000 * T.FT)
bz = math_node(nt, "ADD", bz, 1.0, clamp=True)
nt.links.new(bz, br.inputs[0])
lw = node(nt, "ShaderNodeLayerWeight", Blend=0.35)
fc = math_node(nt, "POWER", lw.outputs["Facing"], 3.0)
BEAM_A = node(nt, "ShaderNodeValue")
BEAM_A.outputs[0].default_value = 0.12
a_ = math_node(nt, "MULTIPLY", br.outputs[0], fc)
a_ = math_node(nt, "MULTIPLY", a_, BEAM_A.outputs[0])
em = node(nt, "ShaderNodeEmission", Color=(0.75, 0.95, 1.0, 1), Strength=1.0)
tr = node(nt, "ShaderNodeBsdfTransparent")
mx = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(a_, mx.inputs[0])
nt.links.new(tr.outputs[0], mx.inputs[1])
nt.links.new(em.outputs[0], mx.inputs[2])
nt.links.new(mx.outputs[0], out.inputs[0])
BEAM_A = BEAM_A.outputs[0]
bb = Builder()
cyl_v, cyl_f = [], []
seg = 12
for k in range(seg):
    a = 2 * math.pi * k / seg
    cyl_v += [(math.cos(a), math.sin(a), 0.0), (math.cos(a), math.sin(a), -1.0)]
for k in range(seg):
    a, b = 2 * k, 2 * ((k + 1) % seg)
    cyl_f.append([a, b, b + 1, a + 1])
cyl_v = np.array(cyl_v)
beam_len = 3000 * T.FT * 1.05
for k in range(26):
    x0, y0 = rng.uniform(-26, 26), rng.uniform(-26, 26)
    r0 = rng.uniform(0.8, 2.2)
    tilt = Euler((math.radians(-14), math.radians(-11), 0)).to_matrix().to_4x4()
    bb.add(cyl_v, cyl_f, Matrix.Translation((x0, y0, -0.02)) @ tilt @ Matrix.Diagonal((r0, r0, beam_len, 1)))
BEAMS = bb.build("Sunbeams", bm_m, smooth=True)
BEAMS.visible_shadow = False
no_bounce([BEAMS])
to_set("tank", BEAMS)


# ================================================================= Mount Everest (real elevation data)
ED = np.load(os.path.join(DATA, "everest_dem.npy"))              # metres, 210 x 210, 67.4 m spacing
EPX = 0.0674
ER = 6.8                                                         # radius of the chunk (km)


def dem_at(x, y):
    c = ED.shape[0] / 2
    u, v = x / EPX + c, -y / EPX + c
    i0, j0 = int(math.floor(u)), int(math.floor(v))
    fu, fv = u - i0, v - j0
    i0, j0 = max(0, min(ED.shape[1] - 2, i0)), max(0, min(ED.shape[0] - 2, j0))
    a = ED[j0, i0] * (1 - fu) + ED[j0, i0 + 1] * fu
    b = ED[j0 + 1, i0] * (1 - fu) + ED[j0 + 1, i0 + 1] * fu
    return float(a * (1 - fv) + b * fv)


# the summit is at the centre of the data; shift so the chunk is centred on it
EV_NR, EV_NA, EV_NK = 70, 160, 22
ev, ef = [], []
ev.append((0.0, 0.0, dem_at(0, 0) / 1000 * T.KM))
for r_i in range(1, EV_NR + 1):
    rr = ER * (r_i / EV_NR) ** 1.2
    for a_i in range(EV_NA):
        a = 2 * math.pi * a_i / EV_NA
        x, y = rr * math.cos(a), rr * math.sin(a)
        ev.append((x, y, dem_at(x, y) / 1000 * T.KM))
for a_i in range(EV_NA):
    ef.append([0, 1 + a_i, 1 + (a_i + 1) % EV_NA])
for r_i in range(1, EV_NR):
    b0, b1 = 1 + (r_i - 1) * EV_NA, 1 + r_i * EV_NA
    for a_i in range(EV_NA):
        a2 = (a_i + 1) % EV_NA
        ef.append([b0 + a_i, b1 + a_i, b1 + a2, b0 + a2])
rim0 = 1 + (EV_NR - 1) * EV_NA
rim_h = np.array([ev[rim0 + a_i][2] for a_i in range(EV_NA)])
rim_s = np.convolve(np.concatenate([rim_h[-12:], rim_h, rim_h[:12]]), np.ones(25) / 25, "same")[12:-12]
nzr = np.random.default_rng(3)
wob = [nzr.normal(0, 1, EV_NA) for _ in range(3)]
for k in range(1, EV_NK + 1):                                   # the rough root under the mountain, to a point
    s = k / EV_NK
    for a_i in range(EV_NA):
        a = 2 * math.pi * a_i / EV_NA
        n = sum(w[(a_i * (q + 1)) % EV_NA] * 0.5 ** q for q, w in enumerate(wob))
        rr = ER * (1 - s) ** 1.25 * (1 + 0.06 * math.sin(3 * a + 5 * s) + 0.035 * n) + 0.02
        hz = rim_h[a_i] * max(0.0, 1 - 4 * s) + rim_s[a_i] * min(1.0, 4 * s)
        z = hz * (1 - s) ** 1.05 - 0.3 * s * (1 - s)
        ev.append((rr * math.cos(a), rr * math.sin(a), max(0.0, z)))
tip = len(ev)
ev.append((0.0, 0.0, 0.0))
for k in range(EV_NK):
    b0 = rim0 + k * EV_NA
    b1 = b0 + EV_NA
    for a_i in range(EV_NA):
        a2 = (a_i + 1) % EV_NA
        ef.append([b0 + a_i, b0 + a2, b1 + a2, b1 + a_i] if k < EV_NK else None)
last = rim0 + EV_NK * EV_NA
for a_i in range(EV_NA):
    ef.append([last + a_i, last + (a_i + 1) % EV_NA, tip])
ef = [f for f in ef if f]
EV_TOP_FACES = EV_NA + (EV_NR - 1) * EV_NA
SUMMIT_LOCAL = max(v[2] for v in ev)

# material: rock and snow by height and slope, rim glow for the dark, then the deep
ev_m, nt, out = new_mat("Everest")
tc = node(nt, "ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(tc.outputs["Object"], sep.inputs[0])
nz = node(nt, "ShaderNodeTexNoise", Scale=1.2, Detail=10.0, Roughness=0.6)
nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
geo = nt.nodes.new("ShaderNodeNewGeometry")
nsep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(geo.outputs["Normal"], nsep.inputs[0])
hgt = math_node(nt, "SUBTRACT", sep.outputs["Z"], 7.2 * T.KM)
hgt = math_node(nt, "MULTIPLY", hgt, 0.8 / T.KM)
nzo = math_node(nt, "SUBTRACT", nz.outputs["Fac"], 0.5)
hgt = math_node(nt, "ADD", hgt, nzo)
flat = math_node(nt, "SUBTRACT", nsep.outputs["Z"], 0.62)
flat = math_node(nt, "MULTIPLY", flat, 3.0)
snow = math_node(nt, "ADD", hgt, flat)
snow = math_node(nt, "MULTIPLY", snow, 1.6, clamp=True)
rockc = ramp(nt, [(0.3, (0.13, 0.12, 0.11)), (0.55, (0.24, 0.21, 0.18)), (0.75, (0.33, 0.30, 0.26))])
nt.links.new(nz.outputs["Fac"], rockc.inputs[0])
rootc = ramp(nt, [(0.0, (0.12, 0.09, 0.07)), (1.0, (0.20, 0.15, 0.11))])
nt.links.new(nz.outputs["Fac"], rootc.inputs[0])
isroot = math_node(nt, "LESS_THAN", sep.outputs["Z"], 4.95 * T.KM)
c1 = nt.nodes.new("ShaderNodeMix")
c1.data_type = "RGBA"
nt.links.new(isroot, c1.inputs[0])
nt.links.new(rockc.outputs[0], c1.inputs[6])
nt.links.new(rootc.outputs[0], c1.inputs[7])
c2 = nt.nodes.new("ShaderNodeMix")
c2.data_type = "RGBA"
nt.links.new(snow, c2.inputs[0])
nt.links.new(c1.outputs[2], c2.inputs[6])
c2.inputs[7].default_value = (0.86, 0.89, 0.94, 1)
p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.8)
p.inputs["Specular IOR Level"].default_value = 0.3
nt.links.new(c2.outputs[2], p.inputs["Base Color"])
nz2 = node(nt, "ShaderNodeTexNoise", Scale=4.0, Detail=10.0, Roughness=0.65)
nt.links.new(tc.outputs["Object"], nz2.inputs["Vector"])
bp = node(nt, "ShaderNodeBump", Strength=0.45, Distance=0.12)
nt.links.new(nz2.outputs["Fac"], bp.inputs["Height"])
nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
# rim glow: shows the mountain's outline in the dark deep (strength set per shot)
lwr = node(nt, "ShaderNodeLayerWeight", Blend=0.25)
rimf = math_node(nt, "POWER", lwr.outputs["Fresnel"], 5.0)
RIM = node(nt, "ShaderNodeValue")
RIM.outputs[0].default_value = 0.0
rimf = math_node(nt, "MULTIPLY", rimf, RIM.outputs[0])
RIM = RIM.outputs[0]
rem = node(nt, "ShaderNodeEmission", Color=(0.35, 0.85, 1.0, 1), Strength=1.6)
pre = nt.nodes.new("ShaderNodeMixShader")
dm = nt.nodes.new("ShaderNodeMixShader")           # depth mix goes in between
depth_mix(nt, p.outputs[0], dm.inputs[1])
dm.inputs[0].default_value = 0.0
nt.links.new(rimf, pre.inputs[0])
nt.links.new(dm.outputs[0], pre.inputs[1])
nt.links.new(rem.outputs[0], pre.inputs[2])
nt.links.new(pre.outputs[0], out.inputs[0])

EVEREST = obj_from("Everest", ev, ef, ev_m, smooth=True)
_bm = bmesh.new()
_bm.from_mesh(EVEREST.data)
bmesh.ops.recalc_face_normals(_bm, faces=_bm.faces)
_bm.to_mesh(EVEREST.data)
_bm.free()
to_set("tank", EVEREST)

# ---- splash at the impact: an expanding ring wave and a burst of droplets
spl_m, nt, out = new_mat("Splash")
p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.15)
p.inputs["Base Color"].default_value = (0.85, 0.95, 1.0, 1)
p.inputs["Transmission Weight"].default_value = 0.0
p.inputs["Emission Color"].default_value = (0.6, 0.85, 1.0, 1)
p.inputs["Emission Strength"].default_value = 0.25
nt.links.new(p.outputs[0], out.inputs[0])
NDROP = 220
DROP_V, DROP_F = sphere_vf(10, 6)
drop_faces = [[i + k * len(DROP_V) for i in f] for k in range(NDROP) for f in DROP_F]
DROPS = Dyn("Drops", np.zeros((NDROP * len(DROP_V), 3)), drop_faces, spl_m, sets=("tank",))
dang = rng.uniform(0, 2 * math.pi, NDROP)
drad = rng.uniform(1.0, 6.5, NDROP)
dvel = rng.uniform(10, 30, NDROP)
dout = rng.uniform(2, 9, NDROP)
dsz = rng.uniform(0.2, 0.7, NDROP)
NRW = 96
RW_SEG = 8


def ring_wave_verts(r, h, w):
    a = np.linspace(0, 2 * np.pi, NRW, endpoint=False)
    b = np.linspace(0, 2 * np.pi, RW_SEG, endpoint=False)
    rr = r + w * np.cos(b)[None, :]
    zz = np.maximum(h * np.sin(b), -0.05)[None, :] * np.ones((NRW, 1))
    return np.stack([rr * np.cos(a)[:, None], rr * np.sin(a)[:, None], zz], -1).reshape(-1, 3)


rw_f = [[i * RW_SEG + k, i * RW_SEG + (k + 1) % RW_SEG, ((i + 1) % NRW) * RW_SEG + (k + 1) % RW_SEG,
         ((i + 1) % NRW) * RW_SEG + k] for i in range(NRW) for k in range(RW_SEG)]
foam_m, FOAM_A, _fs = fade_emit_mat("Foam", (0.75, 0.9, 1.0), 0.5)
FOAM_A.default_value = 0.6
RWAVE = Dyn("RingWave", ring_wave_verts(1, 0.1, 0.1), rw_f, foam_m, sets=("tank",))

# ---- depth gauge next to Everest (S1): a bar from sea level to the bottom, a tick every 5,000 ft
gauge_m, GAUGE_A, _gs = fade_emit_mat("Gauge", (0.85, 0.95, 1.0), 3.0)
gb = Builder()
GX, GY = 9.0, -4.0
gb.add(np.array(cyl_v), cyl_f, Matrix.Translation((GX, GY, 0.0)) @ Matrix.Diagonal((0.09, 0.09, DEPTH_N * (DEEP := 1.0), 1)))
for k in range(1, 8):
    z = -k * 5000 * T.FT
    gb.sphere((GX - 0.9 * 0.5, GY, z), (0.9 * 0.5, 0.07, 0.07))
gb.sphere((GX, GY, T.FLOOR_Z), (1.3, 0.12, 0.12))
GAUGE = gb.build("Gauge", gauge_m, smooth=True)
GAUGE.visible_shadow = False
no_bounce([GAUGE])
to_set("tank", GAUGE)

# ---- bracket from Everest's peak up to the surface (S2)
br_m, BR_A, _bs = fade_emit_mat("Bracket", (1.0, 0.72, 0.25), 4.0)
BRACKET = Dyn("Bracket", np.zeros((3 * (2 * 12 + 2), 3)), tube_faces(2, 12) + tube_faces(2, 12, 26) + tube_faces(2, 12, 52),
              br_m, sets=("tank",))
BRACKET.o.visible_shadow = False
no_bounce([BRACKET.o])

# ---- the 3,000 ft line around the tank (S3)
ln_m, LINE_A, _ls = fade_emit_mat("Line3000", (1.0, 0.7, 0.25), 1.8)
lb = Builder()
zl = -3000 * T.FT
H_ = T.HALF
for (x0, y0, x1, y1) in ((-H_, -H_, H_, -H_), (H_, -H_, H_, H_), (H_, H_, -H_, H_), (-H_, H_, -H_, -H_)):
    lb.sphere(((x0 + x1) / 2, (y0 + y1) / 2, zl), (max(abs(x1 - x0) / 2, 0.09), max(abs(y1 - y0) / 2, 0.09), 0.09))
sh_m, SHEET_A, _shs = fade_emit_mat("Sheet3000", (1.0, 0.8, 0.4), 1.0)
SHEET = obj_from("Sheet3000", [(-H_, -H_, zl), (H_, -H_, zl), (H_, H_, zl), (-H_, H_, zl)], [[0, 1, 2, 3]], sh_m, smooth=False)
SHEET.visible_shadow = False
no_bounce([SHEET])
to_set("tank", SHEET)
LINE = lb.build("Line3000", ln_m, smooth=True)
LINE.visible_shadow = False
no_bounce([LINE])
to_set("tank", LINE)


# ================================================================= macro: one square inch of the trench floor
MX, MY, MZ = T.MACRO
mn = 90
mg = np.linspace(-30, 30, mn)
rs = np.random.default_rng(8)
hn = rs.normal(0, 1, (mn, mn))
for _ in range(3):
    hn = (hn + np.roll(hn, 1, 0) + np.roll(hn, -1, 0) + np.roll(hn, 1, 1) + np.roll(hn, -1, 1)) / 5
mv = [(MX + mg[i], MY + mg[j], MZ + 0.35 * hn[j, i] * min(1.0, (mg[i] ** 2 + mg[j] ** 2) ** 0.5 / 3.0))
      for j in range(mn) for i in range(mn)]
mf = [[j * mn + i, j * mn + i + 1, (j + 1) * mn + i + 1, (j + 1) * mn + i] for j in range(mn - 1) for i in range(mn - 1)]
mud_m, nt, out = new_mat("Ooze")
p, tc_, nz_ = rock_principled(nt, (0.2, 0.18, 0.15), bump=0.35, scale=1.6, rough=0.9)
cv = ramp(nt, [(0.3, (0.10, 0.095, 0.085)), (0.7, (0.19, 0.17, 0.145))])
nt.links.new(nz_.outputs["Fac"], cv.inputs[0])
nt.links.new(cv.outputs[0], p.inputs["Base Color"])
nt.links.new(p.outputs[0], out.inputs[0])
MFLOOR = obj_from("Ooze", mv, mf, mud_m, smooth=True)
to_set("macro", MFLOOR)

steel_m, nt, out = new_mat("Steel")
p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.32, Metallic=1.0)
p.inputs["Base Color"].default_value = (0.62, 0.64, 0.66, 1)
nt.links.new(p.outputs[0], out.inputs[0])
PIL_H = 1.6
bm_ = bmesh.new()
bmesh.ops.create_cube(bm_, size=1.0)
cube_v = np.array([v.co[:] for v in bm_.verts])
cube_f = [[v.index for v in f.verts] for f in bm_.faces]
bm_.free()
PILLAR = obj_from("Pillar", (cube_v * (1.0, 1.0, PIL_H) + (MX, MY, MZ + PIL_H / 2 - 0.3)).tolist(), cube_f, steel_m, smooth=False)
bev = PILLAR.modifiers.new("Bevel", "BEVEL")
bev.width, bev.segments = 0.04, 2
to_set("macro", PILLAR)

# ruler: inch marks (texture: 0 mark at 100 px, 732 px per inch, 2400 x 400 px)
rl_m, nt, out = new_mat("Ruler")
ti = node(nt, "ShaderNodeTexImage")
ti.image = bpy.data.images.load(os.path.join(TEX, "ruler.png"))
tcr = node(nt, "ShaderNodeTexCoord")
nt.links.new(tcr.outputs["UV"], ti.inputs["Vector"])
p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.5)
nt.links.new(ti.outputs["Color"], p.inputs["Base Color"])
p.inputs["Emission Strength"].default_value = 0.15
nt.links.new(ti.outputs["Color"], p.inputs["Emission Color"])
nt.links.new(p.outputs[0], out.inputs[0])
RW_, RH_ = 2400 / 732, 400 / 732
rx0 = MX - 0.5 - 100 / 732
ry0 = MY - 0.62
RULER = obj_from("Ruler", [(rx0, ry0 - RH_, MZ + 0.06), (rx0 + RW_, ry0 - RH_, MZ + 0.06), (rx0 + RW_, ry0, MZ + 0.06),
                           (rx0, ry0, MZ + 0.06)], [[0, 1, 2, 3]], rl_m, smooth=False)
RULER.data.uv_layers.new(name="UV")
for li, uv in zip(range(4), [(0, 0), (1, 0), (1, 1), (0, 1)]):
    RULER.data.uv_layers[0].data[li].uv = uv
sol = RULER.modifiers.new("Solid", "SOLIDIFY")
sol.thickness = 0.05
to_set("macro", RULER)

# the weight: an iron block with "8 TONS" on its face
iron_m, nt, out = new_mat("Iron")
p, _, _ = rock_principled(nt, (0.07, 0.07, 0.075), bump=0.15, scale=6.0, rough=0.45)
p.inputs["Metallic"].default_value = 0.8
nt.links.new(p.outputs[0], out.inputs[0])
WB, WT, WH, WD = 5.0, 3.6, 5.2, 3.0                     # half widths bottom/top, height, half depth
wv_ = [(-WB, -WD, 0), (WB, -WD, 0), (WB, WD, 0), (-WB, WD, 0),
       (-WT, -WD * 0.8, WH), (WT, -WD * 0.8, WH), (WT, WD * 0.8, WH), (-WT, WD * 0.8, WH)]
wf_ = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
WEIGHT = obj_from("Weight", wv_, wf_, iron_m, smooth=False)
wbv = WEIGHT.modifiers.new("Bevel", "BEVEL")
wbv.width, wbv.segments = 0.25, 3
handle = tube("Handle", [(-1.8, 0, WH - 0.2), (-1.8, 0, WH + 1.6), (-1.2, 0, WH + 2.4), (0, 0, WH + 2.7), (1.2, 0, WH + 2.4),
                         (1.8, 0, WH + 1.6), (1.8, 0, WH - 0.2)], [0.42] * 7, iron_m)
handle.parent = WEIGHT
txt_c = bpy.data.curves.new("WText", "FONT")
txt_c.body = "8 TONS"
txt_c.align_x, txt_c.align_y = "CENTER", "CENTER"
txt_c.size = 1.75
txt_c.extrude = 0.08
paint_m, nt, out = new_mat("Paint")
p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.5)
p.inputs["Base Color"].default_value = (0.95, 0.62, 0.16, 1)
p.inputs["Emission Color"].default_value = (0.95, 0.62, 0.16, 1)
p.inputs["Emission Strength"].default_value = 0.6
nt.links.new(p.outputs[0], out.inputs[0])
txt_c.materials.append(paint_m)
TXT = bpy.data.objects.new("WText", txt_c)
col.objects.link(TXT)
# on the sloped front face: it leans back by atan((WD - 0.8 WD) / WH)
lean = math.atan2(WD * 0.2, WH)
TXT.rotation_euler = (math.pi / 2 - lean, 0, 0)
TXT.location = (0, -WD + WD * 0.2 * 0.45 - 0.09, WH * 0.45)
TXT.parent = WEIGHT
to_set("macro", WEIGHT, handle, TXT)

# dust kicked up by the impact
dust_m, DUST_A, _ds = fade_emit_mat("Dust", (0.30, 0.29, 0.26), 0.15)
NDUST = 60
DUST = Dyn("Dust", np.zeros((NDUST * len(DROP_V), 3)), [[i + k * len(DROP_V) for i in f] for k in range(NDUST) for f in DROP_F],
           dust_m, sets=("macro",))
dd_ang = rng.uniform(0, 2 * math.pi, NDUST)
dd_v = rng.uniform(3, 9, NDUST)
dd_s = rng.uniform(0.15, 0.45, NDUST)

# marine snow drifting in the light
sn_m, _sa, _ss = fade_emit_mat("Snow", (0.8, 0.9, 1.0), 1.2)
snb = Builder()
for k in range(500):
    snb.sphere((MX + rng.uniform(-14, 14), MY + rng.uniform(-14, 10), MZ + rng.uniform(0.2, 14)), (rng.uniform(0.02, 0.06),) * 3,
               vf=(DROP_V, DROP_F))
SNOW = snb.build("MarineSnow", sn_m, smooth=True)
SNOW.visible_shadow = False
no_bounce([SNOW])
to_set("macro", SNOW)

# lights: a submersible's lamps from above-front, a cold rim from behind
area("SubLamp", (MX + 4, MY - 9, MZ + 13), (MX, MY, MZ + 1), 900, 4.0, (0.85, 0.95, 1.0), "macro")
area("SubFill", (MX - 10, MY - 6, MZ + 6), (MX, MY, MZ + 2), 160, 6.0, (0.3, 0.6, 1.0), "macro")
area("RimBack", (MX + 2, MY + 12, MZ + 8), (MX, MY, MZ + 2), 900, 6.0, (0.4, 0.75, 1.0), "macro")
for o_ in SETS["macro"]:
    if o_.type == "LIGHT":
        o_.data.shape = "DISK"


# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.clip_start = 0.05
cam_d.clip_end = 2000
cam = bpy.data.objects.new("Cam", cam_d)
cam.rotation_mode = "QUATERNION"
col.objects.link(cam)
scene.camera = cam


# ================================================================= per-frame posing
def set_vis(v):
    for s in VIS_SOCKETS:
        s.default_value = v


def pose_tank(t, te, i):
    ez = T.tip_z(te) if i != 2 and i != 3 else T.REST_Z
    if i == 1:
        ez = T.tip_z(te)
    EVEREST.location = (0.0, 0.0, ez)
    EVEREST.rotation_euler = (0, 0, math.radians(20) + (0.06 * min(te, 3.0) if te > 0 else 0.0))
    WAVE_W.default_value = 0.25 * t
    # the splash
    age = te
    if 0 <= age < 2.6:
        g = 22.0
        pos = []
        for k in range(NDROP):
            tt = age
            r = drad[k] + dout[k] * tt
            z = dvel[k] * tt - 0.5 * g * tt * tt
            s = dsz[k] * T.clamp(1 - tt / 2.4) * T.smoother(tt / 0.1) * (1 if z > -0.2 else 0.0)
            c = (r * math.cos(dang[k]), r * math.sin(dang[k]), max(z, -0.3))
            pos.append(DROP_V * s + c)
        DROPS.set(np.concatenate(pos))
        DROPS.o.hide_render = False
        rr = 4.0 + 16.0 * T.ease_out(age / 2.6)
        hh = 0.7 * (1 - T.smoother(age / 2.2))
        RWAVE.set(ring_wave_verts(rr, hh, 0.35 + 0.5 * age))
        RWAVE.o.hide_render = hh < 0.02
    else:
        DROPS.o.hide_render = True
        RWAVE.o.hide_render = True
    # per-shot looks
    vis, rim, gauge, br, line, beam = 1.0, 0.0, 0.0, 0.0, 0.0, 0.10
    if i == 0:
        rim = 0.0
    elif i == 1:
        rim = 0.5 * T.smoother((t - T.SHOTS[1][0]) / 1.0)
        gauge = T.smoother((t - T.SHOTS[1][0]) / 0.4)
    elif i == 2:
        vis = 0.75
        rim = 0.9
        br = T.smoother((t - T.T_MILE + 0.15) / 0.35)
    elif i == 3:
        line = T.smoother((t - T.T_3000 + 0.2) / 0.3)
        beam = 0.22
    set_vis(vis)
    RIM.default_value = rim
    GAUGE_A.default_value = gauge
    GAUGE.hide_render = gauge <= 0
    BR_A.default_value = br
    BRACKET.o.hide_render = br <= 0
    LINE_A.default_value = line
    LINE.hide_render = line <= 0
    SHEET_A.default_value = 0.10 * line
    SHEET.hide_render = line <= 0
    BEAM_A.default_value = beam
    if br > 0:
        top = T.REST_Z + SUMMIT_LOCAL
        bx, by = 2.2, -1.5
        zt = T.lerp(top, 0.0, br)
        v = np.concatenate([tube_verts(np.array([(bx, by, top), (bx, by, zt)]), np.full(2, 0.12), 12),
                            tube_verts(np.array([(bx - 0.8, by, top), (bx + 0.8, by, top)]), np.full(2, 0.12), 12),
                            tube_verts(np.array([(bx - 0.8, by, zt), (bx + 0.8, by, zt)]), np.full(2, 0.12), 12)])
        BRACKET.set(v)


IMPACT = None


def pose_macro(t):
    ti = T.T_8 - 0.02                                    # the weight lands on "eight"
    rest = MZ + PIL_H - 0.3
    if t < ti:
        u = (ti - t)
        z = rest + 26.0 * u + 25 * u * u
    else:
        u = t - ti
        z = rest - 0.18 * math.exp(-u / 0.06) * math.sin(u * 40)
    WEIGHT.location = (MX, MY, z)
    # dust
    u = t - ti
    if u > 0:
        pos = []
        for k in range(NDUST):
            r = 1.0 + dd_v[k] * T.ease_out(u / 1.6) * 1.2
            s = dd_s[k] * (1 + 1.6 * u)
            pos.append(DROP_V * s + (MX + r * math.cos(dd_ang[k]), MY + r * math.sin(dd_ang[k]), MZ + 0.3 + 0.8 * T.ease_out(u)))
        DUST.set(np.concatenate(pos))
        DUST_A.default_value = 0.13 * T.clamp(1 - u / 2.0) * T.smoother(u / 0.08)
        DUST.o.hide_render = False
    else:
        DUST.o.hide_render = True
    SNOW.location = (0.15 * math.sin(t * 0.4), 0.0, -0.25 * t)


def pose(t):
    st = T.shot_set(t)
    i = T.shot_index(t)
    te = T.env_t(t)
    for name, objs in SETS.items():
        for o in objs:
            o.hide_render = name != st
    for d in (DROPS, RWAVE, BRACKET, DUST):
        d.o.hide_render = True
    if st == "tank":
        pose_tank(t, te, i)
    else:
        pose_macro(t)


def cam_shake(t):
    if T.shot_set(t) != "macro":
        return (0, 0, 0)
    u = t - T.T_8
    if 0 < u < 0.7:
        k = 0.12 * math.exp(-u / 0.12)
        return (k * math.sin(u * 70), 0, k * math.sin(u * 53))
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
c.adaptive_threshold = 0.06
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
SPP = {"tank": 14, "macro": 14}
if os.environ.get("EV_EXP"):
    exec(os.environ["EV_EXP"])

for f in FRAMES:
    t = f / T.FPS
    path = os.path.join(OUT, f"f_{f:04d}.png")
    if os.path.exists(path):
        continue
    pose(t)
    loc, tgt, lens = T.camera(t)
    loc = add_ = tuple(a + b for a, b in zip(loc, cam_shake(t)))
    cam.location = loc
    cam.rotation_quaternion = (V(tgt) - V(loc)).to_track_quat("-Z", "Y")
    cam_d.lens = lens
    scene.frame_set(f)
    c.samples = max(4, int(SPP[T.shot_set(t)] * QUALITY))
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"rendered {f} ({T.shot_set(t)})", flush=True)
print("done")
