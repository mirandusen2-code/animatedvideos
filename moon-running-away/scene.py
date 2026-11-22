"""Blender scene for "The Moon Is Running Away From Us" (procedural, Cycles, immediate-mode posing per frame).

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


# ================================================================= world: open water




# ================================================================= sets and textures
SETS = {"earth": [], "surface": [], "young": [], "eclipse": []}
TEX = os.environ.get("SPACE_TEX", os.path.join(os.path.dirname(OUT.rstrip("/")), "tex"))
rng = random.Random(7)


def to_set(name, *objs):
    for o in objs:
        SETS[name].append(o)
    return objs[0] if len(objs) == 1 else objs


def img(name, colorspace="sRGB"):
    im = bpy.data.images.load(os.path.join(TEX, name))
    im.colorspace_settings.name = colorspace
    return im


DAY_IMG = img("bmng.jpg")
PANG_IMG = img("pangaea.png")


# light from the Sun in the Earth set: lit hemisphere centred on world lon -8, lat 14 (dawn on the left)
SUN_L = V((math.cos(math.radians(14)) * math.cos(math.radians(-8)),
           math.cos(math.radians(14)) * math.sin(math.radians(-8)), math.sin(math.radians(14)))).normalized()

# ================================================================= world: deep space with stars
world = bpy.data.worlds.new("Space")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
for n_ in list(wnt.nodes):
    if n_.type != "OUTPUT_WORLD":
        wnt.nodes.remove(n_)
wtc = wnt.nodes.new("ShaderNodeTexCoord")
stars_col = None
layers = []
for scale_, thr, bright in ((420.0, 0.022, 1.6), (160.0, 0.018, 3.5), (60.0, 0.012, 6.0)):
    vo = wnt.nodes.new("ShaderNodeTexVoronoi")
    vo.inputs["Scale"].default_value = scale_
    wnt.links.new(wtc.outputs["Generated"], vo.inputs["Vector"])
    rp = ramp(wnt, [(0.0, (bright, bright, bright)), (thr, (0.0, 0.0, 0.0))])
    wnt.links.new(vo.outputs["Distance"], rp.inputs[0])
    gt = wnt.nodes.new("ShaderNodeMath")                    # only some cells hold a star
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.72
    sep = wnt.nodes.new("ShaderNodeSeparateColor")
    wnt.links.new(vo.outputs["Color"], sep.inputs[0])
    wnt.links.new(sep.outputs[0], gt.inputs[0])
    mul = wnt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "SCALE"
    wnt.links.new(rp.outputs[0], mul.inputs[0])
    wnt.links.new(gt.outputs[0], mul.inputs["Scale"])
    layers.append(mul)
neb = wnt.nodes.new("ShaderNodeTexNoise")
neb.inputs["Scale"].default_value = 1.6
neb.inputs["Detail"].default_value = 6.0
wnt.links.new(wtc.outputs["Generated"], neb.inputs["Vector"])
nr = ramp(wnt, [(0.45, (0.0, 0.0, 0.0)), (0.75, (0.012, 0.010, 0.030))])
wnt.links.new(neb.outputs["Fac"], nr.inputs[0])
acc = nr.outputs[0]
for m_ in layers:
    ad = wnt.nodes.new("ShaderNodeVectorMath")
    ad.operation = "ADD"
    wnt.links.new(acc, ad.inputs[0])
    wnt.links.new(m_.outputs[0], ad.inputs[1])
    acc = ad.outputs[0]
wbg = wnt.nodes.new("ShaderNodeBackground")
wbg.inputs["Strength"].default_value = 1.0
wnt.links.new(acc, wbg.inputs["Color"])
# the background lights nothing (space is black); it is only seen by the camera
lp_ = wnt.nodes.new("ShaderNodeLightPath")
wmix = wnt.nodes.new("ShaderNodeMixShader")
blk = wnt.nodes.new("ShaderNodeBackground")
blk.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1)
wnt.links.new(lp_.outputs["Is Camera Ray"], wmix.inputs[0])
wnt.links.new(blk.outputs[0], wmix.inputs[1])
wnt.links.new(wbg.outputs[0], wmix.inputs[2])
wnt.links.new(wmix.outputs[0], wnt.nodes["World Output"].inputs[0])


# ================================================================= Earth
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


earth_m, ent, eout = new_mat("Earth")
etc = node(ent, "ShaderNodeTexCoord")
euv = lonlat_vector(ent, etc.outputs["Object"])
eday = ent.nodes.new("ShaderNodeTexImage")
eday.image = DAY_IMG
eday.interpolation = "Cubic"
ent.links.new(euv, eday.inputs["Vector"])
epan = ent.nodes.new("ShaderNodeTexImage")
epan.image = PANG_IMG
epan.interpolation = "Cubic"
ent.links.new(euv, epan.inputs["Vector"])
epv = node(ent, "ShaderNodeValue")
PANG = epv.outputs[0]
emx = ent.nodes.new("ShaderNodeMix")
emx.data_type = "RGBA"
ent.links.new(epv.outputs[0], emx.inputs["Factor"])
ent.links.new(eday.outputs["Color"], emx.inputs["A"])
ent.links.new(epan.outputs["Color"], emx.inputs["B"])
ep = node(ent, "ShaderNodeBsdfPrincipled", Roughness=0.8)
ep.inputs["Specular IOR Level"].default_value = 0.35
esep = ent.nodes.new("ShaderNodeSeparateColor")                      # ocean = bluer than red -> glossy glint
ent.links.new(emx.outputs[2], esep.inputs[0])
eoc = ent.nodes.new("ShaderNodeMath")
eoc.operation = "SUBTRACT"
ent.links.new(esep.outputs[2], eoc.inputs[0])
ent.links.new(esep.outputs[0], eoc.inputs[1])
eoc2 = ent.nodes.new("ShaderNodeMath")
eoc2.operation = "MULTIPLY"
eoc2.use_clamp = True
eoc2.inputs[1].default_value = 6.0
ent.links.new(eoc.outputs[0], eoc2.inputs[0])
erough = ent.nodes.new("ShaderNodeMapRange")
erough.inputs["To Min"].default_value = 0.85
erough.inputs["To Max"].default_value = 0.45
ent.links.new(eoc2.outputs[0], erough.inputs["Value"])
ent.links.new(erough.outputs["Result"], ep.inputs["Roughness"])
# a little atmospheric blue towards the limb
elw = node(ent, "ShaderNodeLayerWeight", Blend=0.35)
ehz = ent.nodes.new("ShaderNodeMix")
ehz.data_type = "RGBA"
ent.links.new(elw.outputs["Fresnel"], ehz.inputs["Factor"])
ent.links.new(emx.outputs[2], ehz.inputs["A"])
ehz.inputs["B"].default_value = (0.35, 0.55, 0.95, 1)
ebr = ent.nodes.new("ShaderNodeVectorMath")
ebr.operation = "SCALE"
ebr.inputs["Scale"].default_value = 1.25
ent.links.new(ehz.outputs[2], ebr.inputs[0])
ent.links.new(ebr.outputs[0], ep.inputs["Base Color"])
ent.links.new(ep.outputs[0], eout.inputs[0])

cloud_m, cnt, cout = new_mat("Clouds")
ctc = node(cnt, "ShaderNodeTexCoord")
cmap = cnt.nodes.new("ShaderNodeMapping")
cnt.links.new(ctc.outputs["Object"], cmap.inputs["Vector"])
cnz = cnt.nodes.new("ShaderNodeTexNoise")
cnz.noise_dimensions = "4D"
cnz.inputs["Scale"].default_value = 4.5
cnz.inputs["Detail"].default_value = 10.0
cnz.inputs["Roughness"].default_value = 0.62
cnz.inputs["Distortion"].default_value = 0.7
cnt.links.new(cmap.outputs[0], cnz.inputs["Vector"])
CLOUD_W = cnz.inputs["W"]
cbig = cnt.nodes.new("ShaderNodeTexNoise")
cbig.inputs["Scale"].default_value = 1.8
cbig.inputs["Detail"].default_value = 3.0
cnt.links.new(cmap.outputs[0], cbig.inputs["Vector"])
cbr = ramp(cnt, [(0.42, (0.0, 0.0, 0.0)), (0.62, (1.0, 1.0, 1.0))])
cnt.links.new(cbig.outputs["Fac"], cbr.inputs[0])
crp0 = ramp(cnt, [(0.48, (0.0, 0.0, 0.0)), (0.74, (1.0, 1.0, 1.0))])
cnt.links.new(cnz.outputs["Fac"], crp0.inputs[0])
crp = cnt.nodes.new("ShaderNodeMix")
crp.data_type = "RGBA"
crp.blend_type = "MULTIPLY"
crp.inputs["Factor"].default_value = 1.0
cnt.links.new(crp0.outputs[0], crp.inputs["A"])
cnt.links.new(cbr.outputs[0], crp.inputs["B"])
cmap.inputs["Scale"].default_value = (1.0, 1.0, 1.6)        # clouds stretch along latitudes
cdens = node(cnt, "ShaderNodeValue")
cdens.outputs[0].default_value = 0.85
CLOUD_D = cdens.outputs[0]
cmul = cnt.nodes.new("ShaderNodeMath")
cmul.operation = "MULTIPLY"
cnt.links.new(crp.outputs[2], cmul.inputs[0])
cnt.links.new(cdens.outputs[0], cmul.inputs[1])
cpr = node(cnt, "ShaderNodeBsdfPrincipled", Roughness=0.9)
cpr.inputs["Base Color"].default_value = (1, 1, 1, 1)
cpr.inputs["Specular IOR Level"].default_value = 0.1
ctr = node(cnt, "ShaderNodeBsdfTransparent")
cmx = cnt.nodes.new("ShaderNodeMixShader")
cnt.links.new(cmul.outputs[0], cmx.inputs[0])
cnt.links.new(ctr.outputs[0], cmx.inputs[1])
cnt.links.new(cpr.outputs[0], cmx.inputs[2])
cnt.links.new(cmx.outputs[0], cout.inputs[0])



# ---- bake the cloud layer once into an equirectangular texture (the procedural noise cost ~13 s per frame)
def bake_clouds(path, w=4096, h=2048):
    me = bpy.data.meshes.new("BakePlane")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [[0, 1, 2, 3]])
    uvl = me.uv_layers.new()
    for i_, uv_ in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uvl.data[i_].uv = uv_
    ob = bpy.data.objects.new("BakePlane", me)
    col.objects.link(ob)
    m = cloud_m.copy()
    nt = m.node_tree
    mp = next(n for n in nt.nodes if n.type == "MAPPING")
    tcn = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tcn.outputs["UV"], sep.inputs[0])
    def math_(op, a, b=None, c_=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for k_, v_ in enumerate((a, b, c_)):
            if v_ is None:
                continue
            if isinstance(v_, (int, float)):
                n.inputs[k_].default_value = v_
            else:
                nt.links.new(v_, n.inputs[k_])
        return n.outputs[0]
    lon = math_("MULTIPLY", math_("SUBTRACT", sep.outputs["X"], 0.5), 2 * math.pi)
    lat = math_("MULTIPLY", math_("SUBTRACT", sep.outputs["Y"], 0.5), math.pi)
    cl = math_("COSINE", lat)
    cmb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(math_("MULTIPLY", math_("MULTIPLY", cl, math_("COSINE", lon)), 1.006), cmb.inputs["X"])
    nt.links.new(math_("MULTIPLY", math_("MULTIPLY", cl, math_("SINE", lon)), 1.006), cmb.inputs["Y"])
    nt.links.new(math_("MULTIPLY", math_("SINE", lat), 1.006), cmb.inputs["Z"])
    nt.links.new(cmb.outputs[0], mp.inputs["Vector"])
    mix_ = next(n for n in nt.nodes if n.type == "MIX" and n.blend_type == "MULTIPLY" and n.data_type == "RGBA")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(mix_.outputs[2], em.inputs["Color"])
    out_ = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    nt.links.new(em.outputs[0], out_.inputs[0])
    im = bpy.data.images.new("CloudBake", w, h, float_buffer=False)
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = im
    nt.nodes.active = tn
    ob.data.materials.append(m)
    for o_ in list(bpy.context.view_layer.objects):
        o_.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    bpy.ops.object.bake(type="EMIT", margin=0)
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    bpy.data.objects.remove(ob)
    bpy.data.materials.remove(m)


CLOUD_PNG = os.path.join(TEX, "clouds_baked.png")
if not os.path.exists(CLOUD_PNG):
    bake_clouds(CLOUD_PNG)
cimg = cnt.nodes.new("ShaderNodeTexImage")
cimg.image = img("clouds_baked.png", "sRGB")   # the bake was written sRGB-encoded
cimg.interpolation = "Cubic"
cnt.links.new(lonlat_vector(cnt, ctc.outputs["Object"]), cimg.inputs["Vector"])
cnt.links.new(cimg.outputs["Color"], cmul.inputs[0])            # the noise nodes are now unused
CLOUD_W = cnt.nodes.new("ShaderNodeValue").outputs[0]            # (kept so pose code can still set it)


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


def earth_objects(name, loc, radius, atmo):
    e = sph(name, loc, radius, earth_m, u=192, v=96)
    c = sph(name + "Clouds", loc, radius * 1.006, cloud_m, u=192, v=96)
    a = sph(name + "Atmo", loc, radius * 1.02, atmo, u=128, v=64)
    c.parent = None
    for o_ in (c, a):
        o_.visible_shadow = o_ is c
    no_bounce([a])
    return e, c, a


atmo_earth = atmo_mat("AtmoEarth", tuple(SUN_L * 1e5))
EARTH, CLOUDS, ATMO = earth_objects("Earth", (0, 0, 0), 1.0, atmo_earth)
to_set("earth", EARTH, CLOUDS, ATMO)
sun_d = bpy.data.lights.new("SunLamp", "SUN")
sun_d.energy, sun_d.color, sun_d.angle = 5.5, (1.0, 0.97, 0.92), math.radians(0.6)
sun_l = bpy.data.objects.new("SunLamp", sun_d)
sun_l.rotation_euler = SUN_L.to_track_quat("Z", "Y").to_euler()
col.objects.link(sun_l)
to_set("earth", sun_l)


# ================================================================= the Moon (procedural: maria + craters)
def moon_mat(name):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.95)
    p.inputs["Specular IOR Level"].default_value = 0.05
    tc = node(nt, "ShaderNodeTexCoord")
    big = node(nt, "ShaderNodeTexNoise", Scale=1.3, Detail=4.0)          # dark maria
    nt.links.new(tc.outputs["Object"], big.inputs["Vector"])
    mr = ramp(nt, [(0.45, (0.20, 0.20, 0.21)), (0.58, (0.48, 0.47, 0.45)), (0.8, (0.62, 0.61, 0.58))])
    nt.links.new(big.outputs["Fac"], mr.inputs[0])
    fine = node(nt, "ShaderNodeTexNoise", Scale=14.0, Detail=8.0)
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    fm = nt.nodes.new("ShaderNodeMix")
    fm.data_type = "RGBA"
    fm.blend_type = "MULTIPLY"
    fm.inputs["Factor"].default_value = 0.35
    nt.links.new(mr.outputs[0], fm.inputs["A"])
    fr = ramp(nt, [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.2, 1.2, 1.2))])
    nt.links.new(fine.outputs["Fac"], fr.inputs[0])
    nt.links.new(fr.outputs[0], fm.inputs["B"])
    nt.links.new(fm.outputs[2], p.inputs["Base Color"])
    # craters: voronoi bowls at two scales into the bump
    h_sum = None
    for sc, st in ((7.0, 1.0), (22.0, 0.5)):
        vo = nt.nodes.new("ShaderNodeTexVoronoi")
        vo.inputs["Scale"].default_value = sc
        vo.inputs["Randomness"].default_value = 1.0
        nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
        cr = ramp(nt, [(0.0, (0.0, 0.0, 0.0)), (0.32, (0.25, 0.25, 0.25)), (0.42, (1.0, 1.0, 1.0)), (0.52, (0.5, 0.5, 0.5))])
        nt.links.new(vo.outputs["Distance"], cr.inputs[0])
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = st
        nt.links.new(cr.outputs[0], mul.inputs[0])
        if h_sum is None:
            h_sum = mul.outputs[0]
        else:
            ad = nt.nodes.new("ShaderNodeMath")
            ad.operation = "ADD"
            nt.links.new(h_sum, ad.inputs[0])
            nt.links.new(mul.outputs[0], ad.inputs[1])
            h_sum = ad.outputs[0]
    bp = node(nt, "ShaderNodeBump", Strength=0.55, Distance=0.02)
    nt.links.new(h_sum, bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


MOON_M = moon_mat("Moon")
MOON = sph("Moon", T.moon_pos(0.0), 1.0, MOON_M, u=128, v=64, scale=(T.MOON_R,) * 3)
to_set("earth", MOON)
# orbit trail behind the receding Moon (the path it has drifted)
trail_m, TRAIL_A, _ = fade_emit_mat("MoonTrail", (0.7, 0.82, 1.0), 3.0)
soften(trail_m)
NTR = 80
MTRAIL = Dyn("MoonTrail", tube_verts(np.linspace((0, 0, 0), (1, 1, 1), NTR), np.full(NTR, 0.01), 6), tube_faces(NTR, 6),
             trail_m, sets=("earth",))
MTRAIL.o.visible_shadow = False
no_bounce([MTRAIL.o])

# ---- laser: a beam from an observatory on Earth to the reflector on the Moon
laser_m, LASER_A, _ = fade_emit_mat("Laser", (0.2, 1.0, 0.35), 18.0)
NLS = 2
LASER = Dyn("Laser", tube_verts(np.array([(0, 0, 0), (1, 0, 0)]), np.full(NLS, 0.008), 8), tube_faces(NLS, 8),
            laser_m, sets=("earth",))
LASER.o.visible_shadow = False
no_bounce([LASER.o])
pulse_m, _ = emit_mat("Pulse", (0.4, 1.0, 0.5), 60.0)
PULSE = sph("Pulse", (0, 0, 0), 0.035, pulse_m, u=16, v=8)
PULSE.visible_shadow = False
no_bounce([PULSE])
to_set("earth", PULSE)
OBS_DIR = V((0.35, 0.80, 0.49)).normalized()       # observatory location (facing the Moon side)


# ================================================================= SURFACE set: the Apollo retroreflector
SX, SY, SZ = T.SURF
regolith_m = moon_mat("Regolith")
for n_ in regolith_m.node_tree.nodes:
    if n_.type == "TEX_NOISE":
        n_.inputs["Scale"].default_value *= 6
    if n_.type == "TEX_VORONOI":
        n_.inputs["Scale"].default_value *= 0.35
    if n_.type == "BUMP":
        n_.inputs["Strength"].default_value = 0.25
gme = bpy.data.meshes.new("Regolith")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=120, y_segments=120, size=6)
for v_ in bm.verts:
    x_, y_ = v_.co.x, v_.co.y
    v_.co.z = 0.03 * math.sin(x_ * 3.1) * math.sin(y_ * 2.7) + 0.015 * math.sin(x_ * 9 + y_ * 7) \
        - 0.12 * math.exp(-((x_ + 1.4) ** 2 + (y_ - 1.2) ** 2) / 0.25) + 0.05 * math.exp(-((math.hypot(x_ + 1.4, y_ - 1.2) - 0.55) / 0.12) ** 2)
    v_.co.x, v_.co.y = x_ + SX, y_ + SY
    v_.co.z += SZ
bm.to_mesh(gme)
bm.free()
gme.shade_smooth()
REG = bpy.data.objects.new("Regolith", gme)
col.objects.link(REG)
REG.data.materials.append(regolith_m)
# reflector: a tilted aluminium panel with a grid of corner-cube prisms, on two legs
alu_m, _ = principled("Alu", (0.75, 0.75, 0.78), rough=0.25)
alu_m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
prism_m, _ = principled("Prism", (0.05, 0.06, 0.08), rough=0.05, coat=1.0)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
pme = bpy.data.meshes.new("Panel")
bm.to_mesh(pme)
bm.free()
panel = bpy.data.objects.new("Panel", pme)
panel.data.materials.append(alu_m)
col.objects.link(panel)
panel.scale = (0.46, 0.46, 0.035)
cb = Builder()
for ix in range(10):
    for iy in range(10):
        cb.sphere((-0.205 + ix * 0.0456, -0.205 + iy * 0.0456, 0.0185), (0.019, 0.019, 0.003), vf=sphere_vf(16, 6))
prisms = cb.build("Prisms", prism_m)
panel.location = (SX, SY, SZ + 0.2)
panel.rotation_euler = (math.radians(38), 0, 0)
prisms.location = panel.location
prisms.rotation_euler = panel.rotation_euler
legs = []
for lx in (-0.18, 0.18):
    legs.append(tube(f"Leg{lx}", [(SX + lx, SY + 0.12, SZ), (SX + lx, SY + 0.08, SZ + 0.2)], [0.012, 0.012], alu_m, seg=8))
spot_m, SPOT_A, _ = fade_emit_mat("LaserSpot", (0.3, 1.0, 0.4), 6.0)
soften(spot_m)
SPOT = sph("LaserSpot", (SX, SY - 0.02, SZ + 0.21), 0.16, spot_m, u=32, v=16)
SPOT.scale = (1, 0.8, 0.6)
SPOT.visible_shadow = False
no_bounce([SPOT])
sbeam_m, SBEAM_A, _ = fade_emit_mat("SurfBeamM", (0.25, 1.0, 0.4), 3.0)
soften(sbeam_m)
beam_s = tube("SurfBeam", [(SX - 0.4, SY + 2.0, SZ + 6.0), (SX, SY - 0.02, SZ + 0.21)], [0.02, 0.02], sbeam_m, seg=12)
beam_s.visible_shadow = False
no_bounce([beam_s])
boot_m, _ = principled("Boot", (0.32, 0.31, 0.30), rough=1.0)
bb = Builder()
for k, (bx, by) in enumerate(((-0.75, -0.35), (-0.55, -0.62), (0.55, 0.45), (0.8, 0.2))):
    for j in range(7):
        bb.sphere((SX + bx + 0.0, SY + by + (j - 3) * 0.035, SZ - 0.004), (0.06, 0.012, 0.006))
s_sun = bpy.data.lights.new("SurfSun", "SUN")
s_sun.energy, s_sun.angle = 4.0, math.radians(0.5)
s_sun_o = bpy.data.objects.new("SurfSun", s_sun)
s_sun_o.rotation_euler = (math.radians(62), 0, math.radians(-35))
col.objects.link(s_sun_o)
to_set("surface", REG, panel, prisms, *legs, SPOT, beam_s, bb.build("BootPrints", boot_m), s_sun_o)
SURF_EARTH = sph("SurfEarth", (SX - 1.2, SY + 40.0, SZ + 9.0), 2.0, earth_m, u=96, v=48)
SURF_EARTH.rotation_euler = (0, 0, math.radians(-60))
to_set("surface", SURF_EARTH)


# ================================================================= YOUNG set: the young Earth's surface, a giant Moon
YX, YY, YZ = T.YOUNG
lava_m, lnt, lout = new_mat("YoungGround")
lp = node(lnt, "ShaderNodeBsdfPrincipled", Roughness=0.7)
ltc = node(lnt, "ShaderNodeTexCoord")
lvo = lnt.nodes.new("ShaderNodeTexVoronoi")
lvo.feature = "DISTANCE_TO_EDGE"
lvo.inputs["Scale"].default_value = 1.6
lnt.links.new(ltc.outputs["Object"], lvo.inputs["Vector"])
lcr = ramp(lnt, [(0.0, (1.0, 1.0, 1.0)), (0.018, (0.0, 0.0, 0.0))])
lnt.links.new(lvo.outputs["Distance"], lcr.inputs[0])
lem = node(lnt, "ShaderNodeEmission", Color=(1.0, 0.32, 0.05, 1), Strength=6.0)
lnz = node(lnt, "ShaderNodeTexNoise", Scale=1.5, Detail=6.0)
lnt.links.new(ltc.outputs["Object"], lnz.inputs["Vector"])
lrp = ramp(lnt, [(0.4, (0.03, 0.025, 0.025)), (0.7, (0.09, 0.07, 0.06))])
lnt.links.new(lnz.outputs["Fac"], lrp.inputs[0])
lnt.links.new(lrp.outputs[0], lp.inputs["Base Color"])
lbp = node(lnt, "ShaderNodeBump", Strength=0.8, Distance=0.2)
lnt.links.new(lnz.outputs["Fac"], lbp.inputs["Height"])
lnt.links.new(lbp.outputs["Normal"], lp.inputs["Normal"])
lmx = lnt.nodes.new("ShaderNodeMixShader")
lnt.links.new(lcr.outputs[0], lmx.inputs[0])
lnt.links.new(lp.outputs[0], lmx.inputs[1])
lnt.links.new(lem.outputs[0], lmx.inputs[2])
lnt.links.new(lmx.outputs[0], lout.inputs[0])
yme = bpy.data.meshes.new("YoungGround")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=150, y_segments=150, size=120)
for v_ in bm.verts:
    x_, y_ = v_.co.x, v_.co.y
    v_.co.z = 0.4 * math.sin(x_ * 0.21) * math.sin(y_ * 0.17) + 0.15 * math.sin(x_ * 0.9 + y_ * 0.7) \
        + (0.05 * max(0.0, y_ - 30) ** 1.3 if y_ > 30 else 0.0)
    v_.co.x, v_.co.y, v_.co.z = x_ + YX, y_ + YY, v_.co.z + YZ
bm.to_mesh(yme)
bm.free()
yme.shade_smooth()
YG = bpy.data.objects.new("YoungGround", yme)
col.objects.link(YG)
YG.data.materials.append(lava_m)
volc_m, _ = principled("Volcano", (0.035, 0.03, 0.03), rough=0.9, bump=0.8, bump_scale=3)
vb = Builder()
for vx, vy, vh in ((-22, 50, 5), (16, 58, 7), (34, 46, 4), (-40, 62, 6)):
    vb.sphere((YX + vx, YY + vy, YZ - vh * 0.3), (vh * 2.2, vh * 2.2, vh))
YMOON = sph("YoungMoon", (YX - 1.0, YY + 60.0, YZ + 31.0), 1.0, MOON_M, u=128, v=64, scale=(23.0,) * 3)
YMOON.rotation_euler = (0.3, 0.2, 1.0)
ysun = bpy.data.lights.new("YoungSun", "SUN")
ysun.energy, ysun.color, ysun.angle = 3.5, (1.0, 0.97, 0.94), math.radians(1)
ysun_o = bpy.data.objects.new("YoungSun", ysun)
ysun_o.rotation_euler = V((0.9, -0.4, 0.5)).normalized().to_track_quat("Z", "Y").to_euler()
col.objects.link(ysun_o)
haze_m, _ = emit_mat("YoungHaze", (0.35, 0.12, 0.05), 1.0)
to_set("young", YG, vb.build("Volcanoes", volc_m), YMOON, ysun_o)


# ================================================================= ECLIPSE set: Sun disc + Moon passing in front
EX, EY, EZ = T.ECL
# ================================================================= the Sun and Earth's orbit

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
ssem = node(ssnt, "ShaderNodeEmission", Strength=1.25)
ssnt.links.new(ssrp.outputs[0], ssem.inputs["Color"])
ssnt.links.new(ssem.outputs[0], ssout.inputs[0])
corona_m, COR_A, _ = fade_emit_mat("Corona", (1.0, 0.5, 0.14), 1.1)
soften(corona_m)
COR_A.default_value = 0.3

ESUN = sph("EclSun", (EX, EY + 40.0, EZ), 1.0, sunsurf_m, u=96, v=48)
ECOR = sph("EclCorona", (EX, EY + 40.0, EZ), 2.6, corona_m, u=64, v=32)
emoon_m, _ = principled("EclMoon", (0.0, 0.0, 0.0), rough=1.0)
EMOON = sph("EclMoon", (EX, EY + 30.0, EZ), 0.5, emoon_m, u=96, v=48)
for o_ in (ESUN, ECOR):
    o_.visible_shadow = False
    no_bounce([o_])
to_set("eclipse", ESUN, ECOR, EMOON)


# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.clip_start = 0.01
cam_d.clip_end = 5000
cam = bpy.data.objects.new("Cam", cam_d)
cam.rotation_mode = "QUATERNION"
col.objects.link(cam)
scene.camera = cam


# ================================================================= per-frame posing
def pose_earth(t, te, i):
    young = i == 4
    spin = math.radians(-35) + 0.03 * te
    if young:
        u = t - T.SHOTS[4][0]
        spin = math.radians(-35) + 2 * math.pi * u / 1.6       # time-lapse: a full turn every 1.6 s
    EARTH.rotation_euler = (0, 0, spin)
    CLOUDS.rotation_euler = (0, 0, spin + 0.01 * te)
    PANG.default_value = 0.0
    CLOUD_D.default_value = 0.9
    # the Moon: receding (opening/loop), fixed at today's distance for the laser, close for the young Earth
    if i in (0, len(T.SHOTS) - 1):
        mp = V(T.moon_pos(te))
    elif i == 1:
        mp = V(T.moon_pos(0.0)) * 1.0
    else:
        n = V(T.MOON_DIR).normalized()
        mp = n * 2.6
    MOON.location = mp
    MOON.rotation_euler = (0, 0, math.atan2(mp.y, mp.x) + math.pi)   # tidally locked: same face to Earth
    # trail of where it has been (opening/loop only)
    on = False
    MTRAIL.o.hide_render = True
    if on:
        n = V(T.MOON_DIR).normalized()
        d1 = T.moon_dist(te) - T.MOON_R * 1.3
        d0 = max(1.6, d1 - 3.5)
        pts = np.array([tuple(n * (d0 + (d1 - d0) * k / (NTR - 1))) for k in range(NTR)])
        MTRAIL.set(tube_verts(pts, np.linspace(0.002, 0.018, NTR), 6))
        TRAIL_A.default_value = 0.55
    # laser (S1): fire on "year", reach the Moon, come back
    lon = i == 1
    LASER.o.hide_render = not lon
    PULSE.hide_render = not lon
    if lon:
        a = OBS_DIR @ Matrix.Rotation(0.0, 3, "Z")
        start = V(a) * 1.01
        end = mp - (mp - start).normalized() * T.MOON_R
        u = (t - T.T_YEAR + 0.1) / 0.9
        ph = u % 2.0
        k = ph if ph < 1 else 2 - ph
        k = T.clamp(k)
        LASER.set(tube_verts(np.array([tuple(start), tuple(end)]), np.full(2, 0.006), 8))
        LASER_A.default_value = 0.35 if u > 0 else 0.0
        PULSE.location = start.lerp(end, k)
        PULSE.hide_render = u < 0


def pose(t):
    st = T.shot_set(t)
    i = T.shot_index(t)
    te = T.env_t(t)
    for name, objs in SETS.items():
        for o in objs:
            o.hide_render = name != st
    for o in (MTRAIL.o, LASER.o, PULSE):
        o.hide_render = True
    if st == "earth":
        pose_earth(t, te, i)
    elif st == "surface":
        SPOT_A.default_value = 0.55 + 0.25 * math.sin(t * 9)
        SBEAM_A.default_value = 0.7
        SURF_EARTH.rotation_euler = (0, 0, math.radians(-60) + 0.02 * t)
    elif st == "young":
        YMOON.rotation_euler = (0.3, 0.2, 1.0 + 0.01 * t)
    elif st == "eclipse":
        SUN_W.default_value = 0.2 * t
        t0, t1 = T.SHOTS[5][0], T.SHOTS[5][1]
        u = T.clamp((t - t0) / (t1 - t0))
        # the Moon crosses the Sun twice: first total (same size), then after "600 million years" smaller (a ring)
        k = T.smoother((t - T.T_FAR + 0.1) / 0.7)
        cam_y = T.camera(t)[0][1] - EY
        fit = (30.0 - cam_y) / (40.0 - cam_y)             # Moon radius that exactly covers the Sun from the camera
        EMOON.scale = (T.lerp(1.0, 0.78, k) * fit / 0.5,) * 3
        cross = T.lerp(-1.3, 0.0, T.smoother((t - t0) / 0.9)) * fit
        EMOON.location = (EX + cross, EY + 30.0, EZ)
        COR_A.default_value = 0.3 + 0.6 * (1 - k) * T.smoother((t - t0 - 0.75) / 0.25)


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
SPP = {"earth": 12, "surface": 12, "young": 10, "eclipse": 8}
if os.environ.get("MO_EXP"):
    exec(os.environ["MO_EXP"])

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
