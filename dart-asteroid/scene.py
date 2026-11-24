"""Blender scene for "NASA Slammed a Spacecraft Into an Asteroid" (Cycles, posed per frame).

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
    def __init__(self, name, verts, faces, mat, sets=("space",), smooth=True):
        self.o = obj_from(name, verts, faces, mat, smooth)
        self.n = len(verts)
        for s in sets:
            SETS[s].append(self.o)

    def set(self, verts):
        v = np.asarray(verts, np.float32).reshape(-1)
        self.o.data.vertices.foreach_set("co", v)
        self.o.data.update()




# ================================================================= sets
SETS = {"space": []}
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



# ================================================================= world: black sky with stars at infinity
world = bpy.data.worlds.new("Space")
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
_wn = wnt.nodes.new("ShaderNodeTexNoise")              # only some voronoi cells get a star
_wn.inputs["Scale"].default_value = 900.0
wnt.links.new(_wtc.outputs["Generated"], _wn.inputs["Vector"])
_wt = ramp(wnt, [(0.0, (0, 0, 0)), (0.62, (0, 0, 0)), (0.72, (1, 1, 1))])
wnt.links.new(_wn.outputs["Fac"], _wt.inputs[0])
_wm = wnt.nodes.new("ShaderNodeMixRGB")
_wm.blend_type = "MULTIPLY"
_wm.inputs[0].default_value = 1.0
wnt.links.new(_wr.outputs[0], _wm.inputs[1])
wnt.links.new(_wt.outputs[0], _wm.inputs[2])
wbg = wnt.nodes.new("ShaderNodeBackground")
wbg.inputs["Strength"].default_value = 0.9
wnt.links.new(_wm.outputs[0], wbg.inputs["Color"])
_wlp = wnt.nodes.new("ShaderNodeLightPath")             # stars only seen by the camera, never light the rocks
_wbk = wnt.nodes.new("ShaderNodeBackground")
_wbk.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1)
_wmx = wnt.nodes.new("ShaderNodeMixShader")
wnt.links.new(_wlp.outputs["Is Camera Ray"], _wmx.inputs[0])
wnt.links.new(_wbk.outputs[0], _wmx.inputs[1])
wnt.links.new(wbg.outputs[0], _wmx.inputs[2])
wnt.links.new(_wmx.outputs[0], wnt.nodes["World Output"].inputs[0])

# ================================================================= lights
_sd = bpy.data.lights.new("Sun", "SUN")
_sd.energy = 5.0
_sd.angle = math.radians(0.6)
_sd.color = (1.0, 0.97, 0.92)
SUN_L = bpy.data.objects.new("Sun", _sd)
SUN_L.rotation_mode = "QUATERNION"
SUN_L.rotation_quaternion = (-V(T.SUN)).to_track_quat("-Z", "Y")
col.objects.link(SUN_L)
_fd = bpy.data.lights.new("Fill", "SUN")                # faint cool bounce so shadows are not pure black
_fd.energy = 0.06
_fd.color = (0.55, 0.65, 1.0)
FILL_L = bpy.data.objects.new("Fill", _fd)
FILL_L.rotation_mode = "QUATERNION"
FILL_L.rotation_quaternion = V((T.SUN[0], T.SUN[1], -T.SUN[2])).to_track_quat("-Z", "Y")
col.objects.link(FILL_L)


# ================================================================= rock geometry
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


def craters(d, seed, n, rmin, rmax, depth):
    """Bowl craters with raised rims on the unit sphere; returns a radial offset (relative)."""
    g = np.random.default_rng(seed)
    c = g.normal(0, 1, (n, 3))
    c /= np.linalg.norm(c, axis=1, keepdims=True)
    rad = np.exp(g.uniform(math.log(rmin), math.log(rmax), n))
    off = np.zeros(len(d))
    for k in range(n):
        x = np.arccos(np.clip(d @ c[k], -1, 1)) / rad[k]
        bowl = np.where(x < 1, -(1 - x * x), 0.0)
        rim = 0.25 * np.exp(-((x - 1.05) / 0.22) ** 2)
        off += depth * rad[k] * (bowl + rim)
    return off


def top_shape(d, R):
    """Didymos: a spinning top with an equatorial ridge."""
    z = np.abs(d[:, 2])
    rho = np.sqrt(np.clip(1 - z * z, 0, 1))
    p = 1.7
    return R / (((1.22 * z) ** p + rho ** p) ** (1 / p))


def ell_r(d, ax):
    return 1.0 / np.sqrt((d[:, 0] / ax[0]) ** 2 + (d[:, 1] / ax[1]) ** 2 + (d[:, 2] / ax[2]) ** 2)


def regolith_mat(name, base=(0.15, 0.135, 0.12), boulder=False):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.95)
    p.inputs["Specular IOR Level"].default_value = 0.2
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise", Scale=0.35 if not boulder else 2.0, Detail=6.0, Roughness=0.6)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    b = base
    rp = ramp(nt, [(0.3, (b[0] * 0.65, b[1] * 0.65, b[2] * 0.62)), (0.5, b), (0.72, (b[0] * 1.35, b[1] * 1.3, b[2] * 1.25))])
    nt.links.new(nz.outputs["Fac"], rp.inputs[0])
    nt.links.new(rp.outputs[0], p.inputs["Base Color"])
    n2 = node(nt, "ShaderNodeTexNoise", Scale=7.0 if not boulder else 14.0, Detail=10.0, Roughness=0.75)
    nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
    bp = node(nt, "ShaderNodeBump", Strength=0.8, Distance=0.08 if not boulder else 0.04)
    nt.links.new(n2.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


rock_m = regolith_mat("Regolith")
boulder_m = regolith_mat("Boulder", base=(0.17, 0.155, 0.14), boulder=True)

# ---------------------------------------------------------------- Didymos (static)
_dd, _df = icosphere(6)
_dr = top_shape(_dd, T.DIDY_R) * (1 + 0.035 * Noise(3)(_dd)) + T.DIDY_R * craters(_dd, 4, 70, 0.04, 0.28, 0.22)
DIDY = obj_from("Didymos", _dd * _dr[:, None], _df, rock_m)
SETS["space"].append(DIDY)

# ---------------------------------------------------------------- Dimorphos (rubble pile, reshapes)
DM_D, DM_F = icosphere(6)
DM_N = Noise(11, octaves=((2.5, 1.0), (5.0, 0.5), (10.0, 0.3), (20.0, 0.15)))(DM_D)
AX0 = np.array(T.DIMO_AX)
AX1 = np.array([10.4, 8.0, 5.4])                       # after: more elongated, flatter (Raducan et al. 2024)
N_IMP = np.array(T.N_IMP)


def dimo_radius(d, s, crater):
    """Radius along unit dirs d: ellipsoid morph s (0 before, 1 reshaped) + lumps + DART crater (0..1)."""
    ax = AX0 + (AX1 - AX0) * s
    r = ell_r(d, ax) * (1 + 0.05 * DM_N_of(d))
    x = np.arccos(np.clip(d @ N_IMP, -1, 1))
    if crater > 0:                                      # the bowl forming under the plume
        u = x / 0.42
        r = r - crater * (1.3 * np.where(u < 1, 1 - u * u, 0.0) - 0.35 * np.exp(-((u - 1.08) / 0.2) ** 2))
    if s > 0:                                           # the impact side slumps broadly instead
        r = r - s * 1.1 * np.exp(-(x / 0.9) ** 2)
    return r


_dmn = Noise(11, octaves=((2.5, 1.0), (5.0, 0.5), (10.0, 0.3), (20.0, 0.15)))


def DM_N_of(d):
    return _dmn(d)


DIMO = Dyn("Dimorphos", DM_D * dimo_radius(DM_D, 0.0, 0.0)[:, None], DM_F, rock_m)

# boulders resting on Dimorphos (they ride the reshape)
NBD = 1400
_g = np.random.default_rng(21)
BD_DIR = _g.normal(0, 1, (NBD, 3))
BD_DIR /= np.linalg.norm(BD_DIR, axis=1, keepdims=True)
BD_SIZE = np.exp(_g.uniform(math.log(0.1), math.log(0.75), NBD)) * (1 + 0.6 * (_g.uniform(0, 1, NBD) < 0.04))
BD_SIZE[_g.choice(NBD, 8, replace=False)] = _g.uniform(1.2, 1.6, 8)   # a few big ones
_bv, _bf = icosphere(2)
BV_SHAPES = []
for k in range(NBD):
    sc = _g.uniform(0.5, 1.0, 3)
    nz = Noise(100 + k, octaves=((2.0, 1.0), (4.0, 0.5)), n=4)
    BV_SHAPES.append(_bv * sc * (1 + 0.35 * nz(_bv))[:, None])
BV_SHAPES = np.array(BV_SHAPES)
BD_ROT = []
for k in range(NBD):
    q = Quaternion(V(_g.normal(0, 1, 3)).normalized(), _g.uniform(0, 2 * math.pi))
    BD_ROT.append(np.array(q.to_matrix()))
BD_ROT = np.array(BD_ROT)
BD_LOCAL = np.einsum("kij,kvj->kvi", BD_ROT, BV_SHAPES) * BD_SIZE[:, None, None]
NBV = len(_bv)
BOULDERS = Dyn("Boulders", np.zeros((NBD * NBV, 3)),
               [[i + k * NBV for i in f] for k in range(NBD) for f in _bf], boulder_m)
# gravel: many small rocks around the impact site (DART's last images)
NGR = 2600
_g2 = np.random.default_rng(23)
_e1 = np.cross(N_IMP, [0, 0, 1.0]); _e1 /= np.linalg.norm(_e1); _e2 = np.cross(N_IMP, _e1)
_rr = 0.5 * np.sqrt(_g2.uniform(0, 1, NGR)); _ph = _g2.uniform(0, 2 * np.pi, NGR)
GR_DIR = N_IMP + _rr[:, None] * (np.cos(_ph)[:, None] * _e1 + np.sin(_ph)[:, None] * _e2)
GR_DIR /= np.linalg.norm(GR_DIR, axis=1, keepdims=True)
GR_SIZE = np.exp(_g2.uniform(math.log(0.025), math.log(0.16), NGR))
_gv, _gf = icosphere(1)
GR_LOCAL = []
for k in range(NGR):
    nz = Noise(5000 + k % 97, octaves=((2.0, 1.0),), n=3)
    q = np.array(Quaternion(V(_g2.normal(0, 1, 3)).normalized(), _g2.uniform(0, 6.3)).to_matrix())
    GR_LOCAL.append((_gv * _g2.uniform(0.5, 1.0, 3) * (1 + 0.3 * nz(_gv))[:, None]) @ q.T * GR_SIZE[k])
GR_LOCAL = np.array(GR_LOCAL)
NGV = len(_gv)
GRAVEL = Dyn("Gravel", np.zeros((NGR * NGV, 3)), [[i + k * NGV for i in f] for k in range(NGR) for f in _gf], boulder_m)
# avoid boulders in the crater bowl (they were blasted away)
_bx = np.arccos(np.clip(BD_DIR @ N_IMP, -1, 1))
BD_IN_BOWL = _bx < 0.3


def pose_dimorphos(t):
    c = np.array(T.dimo_pos(t))
    s = T.reshape(t)
    a = T.impact_age(t)
    cr = 0.0 if a is None or a < 0 else T.ease_out(a / 0.9)
    DIMO.set(DM_D * dimo_radius(DM_D, s, cr)[:, None] + c)
    rr = dimo_radius(BD_DIR, s, cr)
    # each boulder sits a bit into the surface; in the reshape they slide a little downslope
    p = BD_DIR * (rr - 0.25 * BD_SIZE)[:, None] + c
    slide = s * 0.6 * np.sin(np.arange(NBD) * 1.7)[:, None] * np.cross(BD_DIR, [0, 0, 1])
    p = p + slide
    v = BD_LOCAL + p[:, None, :]
    if cr > 0:
        v[BD_IN_BOWL] = -9000.0
    BOULDERS.set(v)
    gr = dimo_radius(GR_DIR, s, cr)
    gp = GR_DIR * (gr - 0.3 * GR_SIZE)[:, None] + c
    gv = GR_LOCAL + gp[:, None, :]
    if cr > 0:
        gv[np.arccos(np.clip(GR_DIR @ N_IMP, -1, 1)) < 0.3] = -9000.0
    GRAVEL.set(gv)


# ================================================================= ejecta
TET = np.array([(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)], float) / math.sqrt(3)
TETF = [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]]


def cone_dirs(n, axis, a0, a1, g):
    axis = np.asarray(axis) / np.linalg.norm(axis)
    e1 = np.cross(axis, [0, 0, 1.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    th = np.radians(g.uniform(a0, a1, n))
    ph = g.uniform(0, 2 * np.pi, n)
    return (np.cos(th)[:, None] * axis + np.sin(th)[:, None] * (np.cos(ph)[:, None] * e1 + np.sin(ph)[:, None] * e2))


EJ_AXIS = np.array(T.N_IMP) * 0.85 - np.array(T.V_DART) * 0.15
# flying boulders
NFB = 140
_g = np.random.default_rng(31)
FB_DIR = cone_dirs(NFB, np.array(T.N_IMP) * 0.6 + np.array(T.SIDE) * 0.75 + np.array(T.UP) * 0.25, 0, 38, _g)
FB_SP = _g.uniform(4.0, 18.0, NFB)
FB_SIZE = np.exp(_g.uniform(math.log(0.08), math.log(0.8), NFB))
FB_T0 = _g.uniform(0.0, 0.25, NFB)
FB_SPIN = _g.normal(0, 1, (NFB, 3))
FB_SHAPE = BV_SHAPES[:NFB] * FB_SIZE[:, None, None]
FBOULD = Dyn("FlyingBoulders", np.zeros((NFB * NBV, 3)),
             [[i + k * NBV for i in f] for k in range(NFB) for f in _bf], boulder_m)
# dust grains (hollow cone)
NDU = 3000
DU_DIR = cone_dirs(NDU, EJ_AXIS, 30, 62, _g)
DU_SP = _g.uniform(6.0, 42.0, NDU)
DU_R = _g.uniform(0.025, 0.07, NDU)
DU_T0 = _g.uniform(0.0, 0.2, NDU)
du_m, DU_A, DU_E = fade_emit_mat("DustGrain", (1.0, 0.92, 0.8), 0.7)
DUST = Dyn("Dust", np.zeros((NDU * 4, 3)), [[i + k * 4 for i in f] for k in range(NDU) for f in TETF], du_m,
           smooth=False)

# plume: a hollow translucent cone of fine dust
NPC, NPR = 48, 24
_pa = np.linspace(0, 2 * np.pi, NPC, endpoint=False)
_pr = np.linspace(0, 1, NPR)
PL_F = [[i * NPC + k, i * NPC + (k + 1) % NPC, (i + 1) * NPC + (k + 1) % NPC, (i + 1) * NPC + k]
        for i in range(NPR - 1) for k in range(NPC)]
pl_m, PL_NT, PL_OUT = new_mat("Plume")
_ptc = node(PL_NT, "ShaderNodeTexCoord")
_pat = PL_NT.nodes.new("ShaderNodeAttribute")
_pat.attribute_name = "along"
_pn = node(PL_NT, "ShaderNodeTexNoise", Scale=1.0, Detail=6.0, Roughness=0.65)
_pang = PL_NT.nodes.new("ShaderNodeAttribute")
_pang.attribute_name = "ang"
_pcx = PL_NT.nodes.new("ShaderNodeCombineXYZ")
PL_NT.links.new(math_node(PL_NT, "MULTIPLY", _pang.outputs["Fac"], 38.0), _pcx.inputs["X"])
PL_NT.links.new(math_node(PL_NT, "MULTIPLY", _pat.outputs["Fac"], 1.6), _pcx.inputs["Y"])
PL_NT.links.new(_pcx.outputs[0], _pn.inputs["Vector"])
_pstreak = ramp(PL_NT, [(0.35, (0, 0, 0)), (0.65, (1, 1, 1))])
PL_NT.links.new(_pn.outputs["Fac"], _pstreak.inputs[0])
_pfade = ramp(PL_NT, [(0.0, (0.25, 0.25, 0.25)), (0.12, (1, 1, 1)), (0.6, (0.55, 0.55, 0.55)), (1.0, (0, 0, 0))])
PL_NT.links.new(_pat.outputs["Fac"], _pfade.inputs[0])
_pa1 = math_node(PL_NT, "MULTIPLY", _pstreak.outputs[0], _pfade.outputs[0])
PL_ALPHA = value(PL_NT, 0.0)
_pa2 = math_node(PL_NT, "MULTIPLY", _pa1, PL_ALPHA)
_pem = node(PL_NT, "ShaderNodeEmission", Color=(1.0, 0.9, 0.75, 1), Strength=0.5)
_pdf = node(PL_NT, "ShaderNodeBsdfDiffuse", Color=(0.8, 0.72, 0.62, 1))
_padd = PL_NT.nodes.new("ShaderNodeAddShader")
PL_NT.links.new(_pem.outputs[0], _padd.inputs[0])
PL_NT.links.new(_pdf.outputs[0], _padd.inputs[1])
_ptr = node(PL_NT, "ShaderNodeBsdfTransparent")
_pmx = PL_NT.nodes.new("ShaderNodeMixShader")
PL_NT.links.new(_pa2, _pmx.inputs[0])
PL_NT.links.new(_ptr.outputs[0], _pmx.inputs[1])
PL_NT.links.new(_padd.outputs[0], _pmx.inputs[2])
PL_NT.links.new(_pmx.outputs[0], PL_OUT.inputs[0])
PLUME = Dyn("Plume", np.zeros((NPC * NPR, 3)), PL_F, pl_m)
_along = PLUME.o.data.attributes.new("along", "FLOAT", "POINT")
_along.data.foreach_set("value", np.repeat(_pr, NPC).astype(np.float32))
_pangA = PLUME.o.data.attributes.new("ang", "FLOAT", "POINT")
_angv = np.tile(np.arange(NPC) / NPC, NPR)
_angv = np.minimum(_angv, 1 - _angv)                 # symmetric: no seam where the ring closes
_pangA.data.foreach_set("value", _angv.astype(np.float32))
PLUME.o.visible_shadow = False

# flash
fl_m, FL_A, FL_E = fade_emit_mat("Flash", (1.0, 0.85, 0.6), 0.0)
soften(fl_m)
_sv, _sf = icosphere(3)
FLASH = Dyn("Flash", _sv, _sf, fl_m)
FLASH.o.visible_shadow = False
_fl = bpy.data.lights.new("FlashL", "POINT")
_fl.shadow_soft_size = 1.0
_fl.color = (1.0, 0.8, 0.55)
FLASH_L = bpy.data.objects.new("FlashL", _fl)
col.objects.link(FLASH_L)


def frame_of(axis):
    axis = np.asarray(axis) / np.linalg.norm(axis)
    e1 = np.cross(axis, [0, 0, 1.0])
    e1 /= np.linalg.norm(e1)
    return axis, e1, np.cross(axis, e1)


def rotm(w, ang):
    return np.array(Matrix.Rotation(ang, 3, V(w / (np.linalg.norm(w) + 1e-9))))


def pose_ejecta(t, origin, scale=1.0):
    a = T.impact_age(t)
    if T.shot_index(t) == 3:
        a = t - T.T_HIT
    if a is None or a < 0:
        FBOULD.o.hide_render = DUST.o.hide_render = PLUME.o.hide_render = True
        return
    FBOULD.o.hide_render = DUST.o.hide_render = PLUME.o.hide_render = False
    o = np.asarray(origin)
    # boulders: fly out slowly, tumbling
    v = []
    for k in range(NFB):
        ak = max(0.0, a - FB_T0[k])
        p = o + FB_DIR[k] * (0.4 + FB_SP[k] * ak) * scale
        R = rotm(FB_SPIN[k], ak * 2.5)
        v.append(FB_SHAPE[k] @ R.T * scale + p)
    FBOULD.set(np.concatenate(v))
    # dust grains: fast hollow cone, they shrink as they thin out
    ak = np.clip(a - DU_T0, 0, None)
    p = o + DU_DIR * (0.3 + DU_SP * ak * (1 - 0.15 * np.minimum(ak, 3)))[:, None] * scale
    r = DU_R * np.clip(1.6 - 0.25 * ak, 0.35, 1.6) * scale
    DUST.set((TET[None, :, :] * r[:, None, None] + p[:, None, :]).reshape(-1, 3))
    DU_A.default_value = float(np.clip(0.8 - 0.12 * a, 0.2, 0.8))
    # plume cone: grows, the mouth opens (half angle ~ 60 deg)
    ax, e1, e2 = frame_of(EJ_AXIS)
    Lc = (2.0 + 14.0 * (1 - math.exp(-a / 0.7)) + 2.5 * a) * scale
    ring = np.cos(_pa)[:, None] * e1 + np.sin(_pa)[:, None] * e2
    v = []
    for u in _pr:
        rad = 0.4 + math.tan(math.radians(42)) * Lc * u ** 0.85
        v.append(o + ax * Lc * u + ring * rad)
    PLUME.set(np.concatenate(v))
    PL_ALPHA.default_value = float(0.45 * T.ease_out(a / 0.25) * math.exp(-max(0.0, a - 1.5) / 4.0))


# ================================================================= the tail of rock (S4)
NTL = 6000
_g = np.random.default_rng(41)
TL_U = _g.uniform(0, 1, NTL) ** 1.6                    # position along the tail (dense near the moon)
TL_OFF = _g.normal(0, 1, (NTL, 2))
TL_R = _g.uniform(0.08, 0.3, NTL)
tl_m, TL_A, TL_E = fade_emit_mat("TailGrain", (1.0, 0.9, 0.78), 2.2)
TAILP = Dyn("TailGrains", np.zeros((NTL * 4, 3)), [[i + k * 4 for i in f] for k in range(NTL) for f in TETF], tl_m,
            smooth=False)
TAILP.o.visible_shadow = False
# a long translucent streak ribbon (wedge) behind the grains
NTS, NTW = 60, 12
TS_F = [[i * NTW + k, i * NTW + k + 1, (i + 1) * NTW + k + 1, (i + 1) * NTW + k] for i in range(NTS - 1) for k in range(NTW - 1)]
ts_m, TS_NT, TS_OUT = new_mat("TailSheet")
_tat = TS_NT.nodes.new("ShaderNodeAttribute")
_tat.attribute_name = "uv2"
_tsep = TS_NT.nodes.new("ShaderNodeSeparateXYZ")
TS_NT.links.new(_tat.outputs["Vector"], _tsep.inputs[0])
_tw = node(TS_NT, "ShaderNodeTexNoise", Scale=6.0, Detail=5.0)
_tmap = TS_NT.nodes.new("ShaderNodeMapping")
_tmap.inputs["Scale"].default_value = (0.25, 9.0, 1.0)
TS_NT.links.new(_tat.outputs["Vector"], _tmap.inputs["Vector"])
TS_NT.links.new(_tmap.outputs[0], _tw.inputs["Vector"])
_tstr = ramp(TS_NT, [(0.38, (0, 0, 0)), (0.62, (1, 1, 1))])
TS_NT.links.new(_tw.outputs["Fac"], _tstr.inputs[0])
_tal = ramp(TS_NT, [(0.0, (1, 1, 1)), (0.5, (0.45, 0.45, 0.45)), (1.0, (0, 0, 0))])
TS_NT.links.new(_tsep.outputs["X"], _tal.inputs[0])
_tacr = ramp(TS_NT, [(0.0, (0, 0, 0)), (0.3, (1, 1, 1)), (0.7, (1, 1, 1)), (1.0, (0, 0, 0))])
TS_NT.links.new(_tsep.outputs["Y"], _tacr.inputs[0])
_ta = math_node(TS_NT, "MULTIPLY", _tstr.outputs[0], _tal.outputs[0])
_ta = math_node(TS_NT, "MULTIPLY", _ta, _tacr.outputs[0])
TS_ALPHA = value(TS_NT, 0.0)
_ta = math_node(TS_NT, "MULTIPLY", _ta, TS_ALPHA)
_tem = node(TS_NT, "ShaderNodeEmission", Color=(1.0, 0.88, 0.72, 1), Strength=1.4)
_ttr = node(TS_NT, "ShaderNodeBsdfTransparent")
_tmx = TS_NT.nodes.new("ShaderNodeMixShader")
TS_NT.links.new(_ta, _tmx.inputs[0])
TS_NT.links.new(_ttr.outputs[0], _tmx.inputs[1])
TS_NT.links.new(_tem.outputs[0], _tmx.inputs[2])
TS_NT.links.new(_tmx.outputs[0], TS_OUT.inputs[0])
TSHEET = Dyn("TailSheet", np.zeros((NTS * NTW, 3)), TS_F, ts_m)
TSHEET.o.visible_shadow = False
_uv2 = TSHEET.o.data.attributes.new("uv2", "FLOAT_VECTOR", "POINT")
_uvv = np.array([(i / (NTS - 1), k / (NTW - 1), 0.0) for i in range(NTS) for k in range(NTW)], np.float32)
_uv2.data.foreach_set("vector", _uvv.reshape(-1))
TAIL_LEN = 900.0


def pose_tail(t):
    on = T.shot_index(t) == 4
    TAILP.o.hide_render = TSHEET.o.hide_render = not on
    if not on:
        return
    g = T.tail_grow(t)
    m = np.array(T.M0)
    d = np.array(T.TAIL_DIR)
    e1 = np.cross(d, [0, 0, 1.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    s = TL_U * TAIL_LEN * g
    w = 6.0 + 0.3 * s                                 # spreads as it streams away
    drift = (t - T.SHOTS[4][0]) * 6.0
    p = m + d[None] * (s + 9.0 + drift * TL_U)[:, None] + (TL_OFF[:, :1] * e1 + TL_OFF[:, 1:] * 0.6 * e2) * w[:, None]
    r = TL_R * (1 + s / 200.0)
    TAILP.set((TET[None] * r[:, None, None] + p[:, None, :]).reshape(-1, 3))
    TL_A.default_value = 1.0
    v = []
    for i in range(NTS):
        u = i / (NTS - 1)
        ss = u * TAIL_LEN * g
        ww = 6.0 + 0.3 * ss
        for k in range(NTW):
            y = (k / (NTW - 1)) * 2 - 1
            v.append(m + d * (ss + 9.0) + e1 * y * ww * 1.6)
    TSHEET.set(np.array(v))
    TS_ALPHA.default_value = 0.6


# ================================================================= orbit rings (S2, S3)
def ring_obj(name, color, dashed):
    m, nt, out = new_mat(name)
    em = node(nt, "ShaderNodeEmission", Color=(*color, 1), Strength=3.0)
    tr = node(nt, "ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader")
    a = value(nt, 0.0)
    if dashed:
        tc = node(nt, "ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs[0])
        at = math_node(nt, "ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
        sn = math_node(nt, "SINE", math_node(nt, "MULTIPLY", at, 60.0))
        dash = math_node(nt, "GREATER_THAN", sn, 0.0)
        a2 = math_node(nt, "MULTIPLY", a, dash)
    else:
        a2 = a
    nt.links.new(a2, mx.inputs[0])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])
    prof = [(1.0 + 0.006 * math.cos(a_), 0.006 * math.sin(a_)) for a_ in np.linspace(0, 2 * math.pi, 9)]
    o = lathe(name, prof, m, seg=256)
    o.visible_shadow = False
    SETS["space"].append(o)
    return o, a


RING_OLD, RING_OLD_A = ring_obj("RingOld", (1.0, 1.0, 1.0), True)
RING_NEW, RING_NEW_A = ring_obj("RingNew", (1.0, 0.62, 0.2), False)


# ================================================================= spacecraft
def gold_mat(name, gold=True):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.42, Metallic=1.0)
    p.inputs["Base Color"].default_value = (0.95, 0.66, 0.25, 1) if gold else (0.7, 0.7, 0.72, 1)
    tc = node(nt, "ShaderNodeTexCoord")
    vo = node(nt, "ShaderNodeTexVoronoi", Scale=420.0)
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    bp = node(nt, "ShaderNodeBump", Strength=0.5, Distance=0.002)
    nt.links.new(vo.outputs["Distance"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


def panel_mat(name):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled", Roughness=0.22, Metallic=0.6)
    tc = node(nt, "ShaderNodeTexCoord")
    br = node(nt, "ShaderNodeTexBrick", Scale=34.0, Color1=(0.03, 0.05, 0.16, 1), Color2=(0.035, 0.06, 0.19, 1),
              Mortar=(0.16, 0.17, 0.2, 1))
    br.inputs["Mortar Size"].default_value = 0.015
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], p.inputs["Base Color"])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


gold_m = gold_mat("Gold")
panel_m = panel_mat("Panel")
white_m, _ = principled("WhiteBody", (0.8, 0.8, 0.78), rough=0.45)
silver_m = gold_mat("Silver", gold=False)
dish_m, _ = principled("Dish", (0.85, 0.85, 0.82), rough=0.3)
thr_m, THR_E = emit_mat("Thruster", (0.45, 0.7, 1.0), 0.0)


def craft(name, bus, wing_len, wing_w, wing_gap, body_mat, dish_r, wing_kind):
    """Bus centred at the origin, flying along +Y, wings along +-X. Returns a parent empty."""
    root = bpy.data.objects.new(name, None)
    col.objects.link(root)
    parts = []
    bx, by, bz = bus
    parts.append(box(name + "Bus", (-bx, -by, -bz), (bx, by, bz), body_mat))
    for sgn in (-1, 1):
        x0 = sgn * (bx + wing_gap)
        x1 = sgn * (bx + wing_gap + wing_len)
        if wing_kind == "rosa":                          # DART's roll-out arrays: a long rectangle
            parts.append(box(name + f"Wing{sgn}", (min(x0, x1), -wing_w / 2, -0.004), (max(x0, x1), wing_w / 2, 0.004),
                             panel_m))
        else:                                            # Hera: two square panels per wing
            seg = wing_len / 2
            for j in range(2):
                a = x0 + sgn * j * (seg + 0.01)
                b = a + sgn * seg
                parts.append(box(name + f"Wing{sgn}{j}", (min(a, b), -wing_w / 2, -0.004), (max(a, b), wing_w / 2, 0.004),
                                 panel_m))
        parts.append(box(name + f"Boom{sgn}", (min(sgn * bx, x0), -0.006, -0.006), (max(sgn * bx, x0), 0.006, 0.006),
                         white_m))
    dish = lathe(name + "Dish", [(0.0, 0.0), (dish_r * 0.5, 0.01 * dish_r / 0.1), (dish_r, 0.04 * dish_r / 0.1),
                                 (dish_r, 0.045 * dish_r / 0.1), (0.0, 0.01)], dish_m, seg=48)
    dish.location = (0.0, 0.0, bz)
    parts.append(dish)
    thr = sph(name + "Thr", (0.0, -by - 0.01, 0.0), 0.025, thr_m, u=16, v=8)
    parts.append(thr)
    for p in parts:
        p.parent = root
        SETS["space"].append(p)
    root.rotation_mode = "QUATERNION"
    return root, parts


DART, DART_PARTS = craft("DART", (0.06, 0.065, 0.065), 0.85, 0.24, 0.03, gold_m, 0.05, "rosa")
HERA, HERA_PARTS = craft("Hera", (0.08, 0.085, 0.08), 0.48, 0.2, 0.03, silver_m, 0.056, "hera")
HERA_PARTS[-1].parent = None
HERA_PARTS[-1].hide_render = True
HERA_PARTS = HERA_PARTS[:-1]


def place_craft(root, parts, pos, fwd, roll_up):
    for p in parts:
        p.hide_render = pos is None
    if pos is None:
        return
    root.location = pos
    m = Matrix((V(fwd).cross(V(roll_up)).normalized(), V(fwd).normalized(), V(roll_up).normalized())).transposed()
    # columns: x = wing axis, y = forward, z = up
    x = V(fwd).cross(V(roll_up)).normalized()
    y = V(fwd).normalized()
    z = x.cross(y)
    root.rotation_quaternion = Matrix((x, y, z)).transposed().to_quaternion()


_cl = bpy.data.lights.new("CraftKey", "POINT")
_cl.energy = 60.0
_cl.shadow_soft_size = 0.3
_cl.color = (1.0, 0.95, 0.9)
CRAFT_L = bpy.data.objects.new("CraftKey", _cl)
col.objects.link(CRAFT_L)

# ghost: the shape before (S6)
gh_m, GH_A, GH_E = fade_emit_mat("Ghost", (0.45, 0.85, 1.0), 1.5)
_gu = bpy.data.meshes.new("GhostM")
_bmg = bmesh.new()
bmesh.ops.create_uvsphere(_bmg, u_segments=20, v_segments=10, radius=1.0)
_bmg.to_mesh(_gu)
_bmg.free()
GHOST = bpy.data.objects.new("Ghost", _gu)
GHOST.data.materials.append(gh_m)
col.objects.link(GHOST)
GHOST.scale = tuple(a * 1.01 for a in T.DIMO_AX)
GHOST.location = T.M0
_wm = GHOST.modifiers.new("wire", "WIREFRAME")
_wm.thickness = 0.012
GHOST.visible_shadow = False

# sand: grains sliding off in the reshape (S6)
NSD = 1500
_g = np.random.default_rng(51)
SD_DIR = _g.normal(0, 1, (NSD, 3))
SD_DIR /= np.linalg.norm(SD_DIR, axis=1, keepdims=True)
SD_R = _g.uniform(0.04, 0.1, NSD)
SD_T0 = _g.uniform(0.0, 1.2, NSD)
sd_m, SD_A, SD_E = fade_emit_mat("Sand", (0.95, 0.85, 0.7), 0.9)
SAND = Dyn("Sand", np.zeros((NSD * 4, 3)), [[i + k * 4 for i in f] for k in range(NSD) for f in TETF], sd_m,
           smooth=False)


def pose_sand(t):
    on = T.shot_index(t) == 6 and t > T.T_WHOLE
    SAND.o.hide_render = not on
    if not on:
        return
    s = T.reshape(t)
    a = np.clip(t - T.T_WHOLE - SD_T0, 0, None)
    rr = dimo_radius(SD_DIR, s, 1 - s)
    tang = np.cross(SD_DIR, [0, 0, 1.0])
    p = (SD_DIR * (rr + 0.15 + 0.9 * np.sin(np.clip(a / 1.4, 0, 1) * np.pi))[:, None]
         + tang * (0.8 * a)[:, None] + np.array(T.M0))
    r = SD_R * (a > 0)
    SAND.set((TET[None] * r[:, None, None] + p[:, None, :]).reshape(-1, 3))


# ================================================================= per-frame posing
def pose(t):
    i = T.shot_index(t)
    pose_dimorphos(t)
    c = np.array(T.dimo_pos(t))
    if i in (0, 1, 7):
        pose_ejecta(t, T.P_IMP)
    elif i == 3:
        pose_ejecta(t, c + (np.array(T.P_IMP) - np.array(T.M0)), scale=1.0)
    else:
        for o in (FBOULD, DUST, PLUME):
            o.o.hide_render = True
    f = T.flash(t)
    a = T.impact_age(t)
    fo = np.array(T.P_IMP) if i != 3 else c + (np.array(T.P_IMP) - np.array(T.M0))
    FLASH.o.hide_render = f < 0.01
    FLASH_L.hide_render = f < 0.01
    if f >= 0.01:
        aa = (a if i != 3 else t - T.T_HIT) or 0.0
        rad = (0.6 + 2.2 * min(aa, 0.6)) * (2.0 if i == 3 else 1.0)
        FLASH.set(_sv * rad + fo + N_IMP * rad * 0.3)
        FL_A.default_value = 1.0
        FL_E.default_value = 60.0 * f
        FLASH_L.location = tuple(fo + N_IMP * 2.0)
        _fl.energy = 1.0e5 * f
    # rings
    oa, na, nr = T.orbit_rings(t)
    RING_OLD.hide_render = oa < 0.01
    RING_NEW.hide_render = na < 0.01
    RING_OLD_A.default_value = oa * (0.55 if i == 3 else 0.8)
    RING_NEW_A.default_value = na
    RING_OLD.scale = (T.ORBIT_R, T.ORBIT_R, T.ORBIT_R)
    RING_NEW.scale = (nr, nr, nr)
    pose_tail(t)
    # spacecraft
    dp = T.dart_pos(t) if i == 2 else None
    place_craft(DART, DART_PARTS, dp, T.dart_dir(t), (0.35, -0.2, 1.0))
    THR_E.default_value = 6.0
    hp = T.hera_pos(t)
    place_craft(HERA, HERA_PARTS, hp, T.HERA_DIR, (0.0, 0.0, 1.0))
    CRAFT_L.hide_render = hp is None and dp is None
    if hp is not None or dp is not None:
        pp, dd = (hp, T.HERA_DIR) if hp is not None else (dp, T.dart_dir(t))
        sd = np.cross(dd, [0, 0, 1.0])
        CRAFT_L.location = tuple(np.array(pp) - 0.8 * np.array(dd) + 1.2 * sd + np.array([0, 0, 1.0]))
    GHOST.hide_render = T.ghost(t) < 0.01
    GH_A.default_value = 0.4 * T.ghost(t)
    pose_sand(t)


# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.clip_start = 0.01
cam_d.clip_end = 6000
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
c.transmission_bounces = 2
c.caustics_reflective = False
c.caustics_refractive = False
c.blur_glossy = 1.0
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0
except Exception:
    pass

SPP = 24
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
