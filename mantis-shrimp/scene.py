"""Blender scene for 'This Shrimp Can Punch Hard Enough to Break Glass' (procedural, Cycles).

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


SETS = {k: [] for k in ("tank", "reef", "macro")}

# ================================================================= world: deep water blue
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wn = world.node_tree
bgw = wn.nodes["Background"]
tcw = node(wn, "ShaderNodeTexCoord")
sxw = wn.nodes.new("ShaderNodeSeparateXYZ")
wn.links.new(tcw.outputs["Generated"], sxw.inputs[0])
mrw = node(wn, "ShaderNodeMapRange", **{"From Min": -0.3, "From Max": 0.9})
wn.links.new(sxw.outputs["Z"], mrw.inputs["Value"])
rw = ramp(wn, [(0.0, (0.001, 0.006, 0.012)), (0.45, (0.004, 0.035, 0.06)), (1.0, (0.03, 0.16, 0.22))])
wn.links.new(mrw.outputs["Result"], rw.inputs[0])
wn.links.new(rw.outputs[0], bgw.inputs[0])
bgw.inputs[1].default_value = 1.0
WORLD_STRENGTH = bgw.inputs[1]

# ================================================================= materials
M_BODY = spotted_mat("Body", (0.015, 0.20, 0.05), (0.004, 0.03, 0.012), scale=7.0, thr=0.05)
M_CARA = spotted_mat("Carapace", (0.03, 0.26, 0.07), (0.005, 0.025, 0.012), scale=11.0, thr=0.09)
M_ARM = spotted_mat("Arm", (0.75, 0.10, 0.02), (0.85, 0.75, 0.6), scale=16.0, thr=0.05)
M_CLUB = pmat("Club", (0.55, 0.02, 0.07), rough=0.25, coat=1.0, bump=0.2, bump_scale=22.0)
M_LEG = pmat("Leg", (0.85, 0.18, 0.02), bump=0.05)
M_SCALE = spotted_mat("AntScale", (1.0, 0.36, 0.03), (0.15, 0.35, 1.0), scale=10.0, thr=0.05, bump=0.05)
M_TAIL = spotted_mat("Tail", (0.03, 0.28, 0.10), (0.9, 0.3, 0.02), scale=8.0, thr=0.12, bump=0.05)
M_UROPOD = pmat("Uropod", (0.03, 0.12, 0.75), bump=0.05)
M_ANT = pmat("Antenna", (0.6, 0.45, 0.3), bump=0.0)

# compound eye: green-teal with the dark mid band
M_EYE, nt_ey, out_ey = new_mat("Eye")
pey = shell_bsdf(nt_ey, (0.2, 0.6, 0.4), rough=0.2, coat=1.0)
tce = node(nt_ey, "ShaderNodeTexCoord")
sep = nt_ey.nodes.new("ShaderNodeSeparateXYZ")
nt_ey.links.new(tce.outputs["Object"], sep.inputs[0])
rey = ramp(nt_ey, [(0.0, (0.25, 0.65, 0.35)), (0.42, (0.25, 0.65, 0.35)), (0.45, (0.01, 0.02, 0.02)),
                   (0.55, (0.01, 0.02, 0.02)), (0.58, (0.55, 0.75, 0.25)), (1.0, (0.55, 0.75, 0.25))])
mpz = node(nt_ey, "ShaderNodeMapRange", **{"From Min": -1.0, "From Max": 1.0})
nt_ey.links.new(sep.outputs["Z"], mpz.inputs["Value"])
nt_ey.links.new(mpz.outputs["Result"], rey.inputs[0])
nt_ey.links.new(rey.outputs[0], pey.inputs["Base Color"])
nt_ey.links.new(pey.outputs[0], out_ey.inputs[0])


# ================================================================= hero: mantis shrimp rig
# local frame: +X forward (head), Z up, ground at z = 0. Body length ~2.4.
ABDOMEN = [(-0.02 - 0.155 * i, 0.095, 0.25 - 0.01 * i, 0.13 - 0.005 * i, 0.25 - 0.006 * i) for i in range(6)]
ELBOW = 0.30                                   # forearm length
REST, STRIKE_OUT = math.radians(-150), math.radians(-15)


def make_shrimp(name, loc, scale=1.0, sets=()):
    root = empty(name, loc)
    root.scale = (scale,) * 3
    P = {"root": root, "arms": [], "eyes": [], "ants": [], "tail": None}
    objs = []

    def add(o):
        o.parent = root
        objs.append(o)
        return o

    # carapace (head shield) + thorax
    add(sph(f"{name}_cara", (0.60, 0, 0.29), 1.0, M_CARA, scale=(0.29, 0.22, 0.14)))
    add(sph(f"{name}_rostrum", (0.90, 0, 0.32), 1.0, M_CARA, u=24, v=12, scale=(0.08, 0.07, 0.05)))
    for i, x in enumerate((0.20, 0.09)):
        add(sph(f"{name}_th{i}", (x, 0, 0.27), 1.0, M_BODY, u=32, v=16, scale=(0.10, 0.21, 0.15)))
    # abdomen
    for i, (x, rx, ry, rz, z) in enumerate(ABDOMEN):
        add(sph(f"{name}_ab{i}", (x, 0, z), 1.0, M_BODY, u=32, v=16, scale=(rx, ry, rz)))
        for sy in (1, -1):                        # small side spines (pleura), orange edge
            add(sph(f"{name}_pl{i}{sy}", (x, sy * (ry - 0.01), z - 0.06), 1.0, M_LEG, u=12, v=6,
                    scale=(0.07, 0.025, 0.04)))
    # tail fan
    tail = empty(f"{name}_tailp", (-1.03, 0, 0.21), root)
    objs.append(tail)
    P["tail"] = tail
    o = sph(f"{name}_telson", (-0.14, 0, 0), 1.0, M_TAIL, u=32, v=12, scale=(0.17, 0.15, 0.04))
    o.parent = tail
    objs.append(o)
    for sy in (1, -1):
        for k, (dx, dy, ang, mat) in enumerate(((-0.12, 0.17, 0.5, M_UROPOD), (-0.06, 0.13, 0.25, M_LEG))):
            o = sph(f"{name}_ur{sy}{k}", (dx, sy * dy, 0.01), 1.0, mat, u=24, v=8, scale=(0.15, 0.06, 0.015),
                    rot=(0, 0, -sy * ang + math.pi))
            o.parent = tail
            objs.append(o)
    # walking legs
    for i, x in enumerate((0.30, 0.18, 0.06)):
        for sy in (1, -1):
            add(tube(f"{name}_leg{i}{sy}", [(x, sy * 0.12, 0.2), (x + 0.02, sy * 0.27, 0.14), (x + 0.05, sy * 0.33, 0.0)],
                     [0.022, 0.018, 0.012], M_LEG, seg=8))
    # eyes on stalks (each one moves on its own)
    for sy in (1, -1):
        piv = empty(f"{name}_eyep{sy}", (0.90, sy * 0.06, 0.38), root)
        objs.append(piv)
        o = tube(f"{name}_stalk{sy}", [(0, 0, 0), (0.03, sy * 0.02, 0.07), (0.05, sy * 0.03, 0.12)],
                 [0.03, 0.026, 0.024], M_ARM, seg=10)
        o.parent = piv
        objs.append(o)
        o = sph(f"{name}_eye{sy}", (0.06, sy * 0.035, 0.17), 1.0, M_EYE, u=32, v=24, scale=(0.055, 0.055, 0.075))
        o.parent = piv
        objs.append(o)
        P["eyes"].append((piv, sy))
    # antennules + antennal scales (bright orange paddles)
    for sy in (1, -1):
        piv = empty(f"{name}_antp{sy}", (0.95, sy * 0.05, 0.33), root)
        objs.append(piv)
        for k, spread in enumerate((0.08, 0.16)):
            o = tube(f"{name}_ant{sy}{k}", [(0, 0, 0), (0.25, sy * spread, 0.18), (0.5, sy * spread * 2.2, 0.28),
                                            (0.75, sy * spread * 3.2, 0.30)], [0.007, 0.005, 0.0035, 0.002], M_ANT, seg=6)
            o.parent = piv
            objs.append(o)
        P["ants"].append((piv, sy))
        add(sph(f"{name}_ascale{sy}", (0.97, sy * 0.25, 0.30), 1.0, M_SCALE, u=24, v=8, scale=(0.09, 0.035, 0.012),
                rot=(0, 0, sy * 0.5)))
    # raptorial clubs: fixed merus, then a forearm pivot at the elbow with the club bulb at its end
    for sy in (1, -1):
        add(tube(f"{name}_merus{sy}", [(0.78, sy * 0.13, 0.22), (0.88, sy * 0.135, 0.15), (0.95, sy * 0.14, 0.10)],
                 [0.05, 0.05, 0.045], M_ARM, seg=12))
        piv = empty(f"{name}_elbow{sy}", (0.95, sy * 0.14, 0.10), root)
        objs.append(piv)
        for o in (sph(f"{name}_fore{sy}", (ELBOW * 0.5, 0, 0), 1.0, M_ARM, u=32, v=12, scale=(ELBOW * 0.55, 0.05, 0.055)),
                  sph(f"{name}_club{sy}", (ELBOW, 0, 0), 0.075, M_CLUB, u=40, v=20, scale=(1.0, 0.85, 1.0)),
                  sph(f"{name}_dact{sy}", (ELBOW * 0.6, 0, 0.055), 1.0, M_ARM, u=16, v=8, scale=(0.15, 0.02, 0.018),
                      rot=(0, -0.1, 0))):
            o.parent = piv
            objs.append(o)
        P["arms"].append((piv, sy))
    allobjs = [root] + objs
    for st in sets:
        SETS[st].extend(allobjs)
    P["all"] = allobjs
    return P


def club_local(s, sy=1):
    th = T.lerp(REST, STRIKE_OUT, s)
    return V((0.95 + ELBOW * math.cos(th), sy * 0.14, 0.10 - ELBOW * math.sin(th)))


def pose_shrimp(P, t, strike=0.0, seed=0.0):
    for piv, sy in P["arms"]:
        th = T.lerp(REST, STRIKE_OUT, strike) + (0.03 * math.sin(t * 2.1 + seed) if strike < 0.01 else 0.0)
        key(piv, "rotation_euler", (0, th, 0))
    for k, (piv, sy) in enumerate(P["eyes"]):          # independent, curious eye movement
        key(piv, "rotation_euler", (0.25 * math.sin(t * 1.3 + 2.1 * k + seed), 0.15 * math.sin(t * 0.9 + 1.3 * k),
                                   0.35 * math.sin(t * 0.7 + 3.0 * k + seed)))
    for k, (piv, sy) in enumerate(P["ants"]):
        key(piv, "rotation_euler", (0.12 * math.sin(t * 1.7 + k), 0.06 * math.sin(t * 1.1 + k), 0.1 * math.sin(t * 1.4 + k)))
    key(P["tail"], "rotation_euler", (0, 0.05 * math.sin(t * 1.2 + seed), 0))


# ================================================================= shared: sand with moving caustics
SAND, nt_s, out_s = new_mat("Sand")
ps = node(nt_s, "ShaderNodeBsdfPrincipled", Roughness=0.9)
tcs = node(nt_s, "ShaderNodeTexCoord")
nzs = node(nt_s, "ShaderNodeTexNoise", Scale=3.0, Detail=8.0)
nt_s.links.new(tcs.outputs["Object"], nzs.inputs["Vector"])
crs = ramp(nt_s, [(0.3, (0.16, 0.14, 0.11)), (0.7, (0.30, 0.26, 0.20))])
nt_s.links.new(nzs.outputs["Fac"], crs.inputs[0])
nt_s.links.new(crs.outputs[0], ps.inputs["Base Color"])
nzg = node(nt_s, "ShaderNodeTexNoise", Scale=60.0, Detail=4.0)
nt_s.links.new(tcs.outputs["Object"], nzg.inputs["Vector"])
mxb = node(nt_s, "ShaderNodeMath")
mxb.operation = "ADD"
nt_s.links.new(nzg.outputs["Fac"], mxb.inputs[0])
nt_s.links.new(nzs.outputs["Fac"], mxb.inputs[1])
bps = node(nt_s, "ShaderNodeBump", Strength=0.35, Distance=0.03)
nt_s.links.new(mxb.outputs[0], bps.inputs["Height"])
nt_s.links.new(bps.outputs["Normal"], ps.inputs["Normal"])
vcs = nt_s.nodes.new("ShaderNodeTexVoronoi")
vcs.voronoi_dimensions = "4D"
vcs.feature = "DISTANCE_TO_EDGE"
vcs.inputs["Scale"].default_value = 3.2
CAUSTIC_W = vcs.inputs["W"]
nzw = node(nt_s, "ShaderNodeTexNoise", Scale=1.2, Detail=2.0)
nt_s.links.new(tcs.outputs["Object"], nzw.inputs["Vector"])
dv = nt_s.nodes.new("ShaderNodeVectorMath")
dv.operation = "MULTIPLY_ADD"
dv.inputs[1].default_value = (0.35, 0.35, 0.35)
nt_s.links.new(nzw.outputs["Color"], dv.inputs[0])
nt_s.links.new(tcs.outputs["Object"], dv.inputs[2])
nt_s.links.new(dv.outputs[0], vcs.inputs["Vector"])
crc = ramp(nt_s, [(0.0, (0.55, 0.85, 1.0)), (0.025, (0, 0, 0))])
nt_s.links.new(vcs.outputs["Distance"], crc.inputs[0])
nt_s.links.new(crc.outputs[0], ps.inputs["Emission Color"])
ps.inputs["Emission Strength"].default_value = 0.0   # no caustic web (read as tiles)
nt_s.links.new(ps.outputs[0], out_s.inputs[0])

M_ROCK = pmat("Rock", (0.07, 0.06, 0.055), rough=0.8, coat=0.0, bump=0.6, bump_scale=6.0)
M_SNOW, _ = emit_mat("Snow", (0.75, 0.9, 1.0), 0.5)
CORALS = [pmat("CoralA", (0.55, 0.06, 0.12), rough=0.6, coat=0.2, bump=0.5, bump_scale=9.0),
          pmat("CoralB", (0.6, 0.25, 0.03), rough=0.6, coat=0.2, bump=0.5, bump_scale=9.0),
          pmat("CoralC", (0.15, 0.06, 0.4), rough=0.6, coat=0.2, bump=0.5, bump_scale=9.0)]
rnd = random.Random(7)


def ground(name, origin, st, size=60):
    bpy.ops.mesh.primitive_plane_add(size=size, location=origin)
    g = bpy.context.active_object
    g.name = name
    g.data.materials.append(SAND)
    SETS[st].append(g)
    return g


def rocks(name, origin, st, items):
    b = Builder()
    vv, ff = sphere_vf(12, 8)
    for (x, y, s) in items:
        jitter = vv * (1 + 0.18 * np.sin(vv * (3 + rnd.random() * 4) + rnd.random() * 6).sum(axis=1, keepdims=True) / 3)
        b.add(jitter, ff, Matrix.Translation(V(origin) + V((x, y, s * 0.25))) @ Euler((rnd.random(), rnd.random(), rnd.random())).to_matrix().to_4x4()
              @ Matrix.Diagonal((s, s * rnd.uniform(0.7, 1.1), s * 0.6, 1)))
    o = b.build(name, M_ROCK)
    SETS[st].append(o)
    return o


def corals(name, origin, st, items):
    out = []
    for k, (x, y, s) in enumerate(items):
        b = Builder()
        for j in range(18):                         # branching blob coral
            a = rnd.uniform(0, 2 * math.pi)
            h = rnd.uniform(0.2, 1.0)
            b.sphere(V(origin) + V((x + math.cos(a) * 0.35 * s * h, y + math.sin(a) * 0.35 * s * h, s * (0.25 + 0.7 * h))),
                     (0.16 * s, 0.16 * s, 0.32 * s), (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 0))
        o = b.build(f"{name}{k}", CORALS[k % 3])
        SETS[st].append(o)
        out.append(o)
    return out


def marine_snow(name, origin, st, box, n=160):
    b = Builder()
    vv, ff = sphere_vf(6, 4)
    for _ in range(n):
        p = V(origin) + V((rnd.uniform(*box[0]), rnd.uniform(*box[1]), rnd.uniform(*box[2])))
        r = rnd.uniform(0.003, 0.008)
        b.add(vv, ff, Matrix.Translation(p) @ Matrix.Diagonal((r, r, r, 1)))
    o = b.build(name, M_SNOW)
    SETS[st].append(o)
    return o


# ================================================================= TANK set: shrimp behind aquarium glass
K0 = V(T.TANK)
GLASS_X = 1.33
ground("TankSand", K0, "tank")
rocks("TankRocks", K0, "tank", [(-1.6, 1.2, 0.7), (-0.6, 1.8, 0.45), (0.2, -1.6, 0.4), (-2.6, -0.8, 0.8), (0.9, 1.4, 0.3)])
corals("TankCoral", K0, "tank", [(-3.5, 2.2, 1.6), (-2.2, 3.0, 1.2), (-4.5, -1.5, 1.8), (-1.2, -2.8, 1.0)])
tank_snow = marine_snow("TankSnow", K0, "tank", ((-3, 1.3), (-3, 3), (0, 2.5)))
shrimp_tank = make_shrimp("ShrimpTank", K0, 1.0, sets=("tank",))

GLASS, nt_g, out_g = new_mat("Glass")
fr = node(nt_g, "ShaderNodeFresnel", IOR=1.5)
tr = node(nt_g, "ShaderNodeBsdfTransparent", Color=(0.92, 0.98, 1.0, 1))
gl = node(nt_g, "ShaderNodeBsdfGlossy", Roughness=0.03)
mxg = nt_g.nodes.new("ShaderNodeMixShader")
nt_g.links.new(fr.outputs[0], mxg.inputs[0])
nt_g.links.new(tr.outputs[0], mxg.inputs[1])
nt_g.links.new(gl.outputs[0], mxg.inputs[2])
nt_g.links.new(mxg.outputs[0], out_g.inputs[0])
bpy.ops.mesh.primitive_cube_add(size=1, location=K0 + V((GLASS_X + 0.02, 0, 1.4)))
glass = bpy.context.active_object
glass.scale = (0.04, 8, 2.8)
glass.data.materials.append(GLASS)
M_FRAME = pmat("Frame", (0.02, 0.02, 0.025), rough=0.4, coat=0.3, bump=0.0)
bpy.ops.mesh.primitive_cube_add(size=1, location=K0 + V((GLASS_X + 0.02, 0, -0.03)))
frame_bot = bpy.context.active_object
frame_bot.scale = (0.12, 8, 0.14)
frame_bot.data.materials.append(M_FRAME)
SETS["tank"] += [glass, frame_bot]

# crack: spokes + rings as thin strips just outside the glass, revealed by radius
CRACK_C = V((GLASS_X + 0.045, 0.0, 0.20))
crnd = random.Random(3)
segs = []
NSP = 17
spoke_pts = []
for i in range(NSP):
    a = 2 * math.pi * i / NSP + crnd.uniform(-0.15, 0.15)
    r, pts = 0.0, [(0.0, 0.0)]
    rmax = crnd.uniform(0.6, 1.2)
    while r < rmax:
        r += crnd.uniform(0.05, 0.12)
        a += crnd.uniform(-0.12, 0.12)
        pts.append((r * math.cos(a), r * math.sin(a)))
    spoke_pts.append(pts)
    segs += list(zip(pts[:-1], pts[1:]))
    if crnd.random() < 0.6:                       # side branch
        j = crnd.randrange(2, max(3, len(pts) - 2))
        b0 = pts[j]
        ba = math.atan2(b0[1], b0[0]) + crnd.choice((-0.6, 0.6))
        bl = crnd.uniform(0.15, 0.4)
        segs.append((b0, (b0[0] + bl * math.cos(ba), b0[1] + bl * math.sin(ba))))
for rr in (0.09, 0.2, 0.36, 0.58):
    for i in range(NSP):
        if crnd.random() < 0.72:
            p0 = min(spoke_pts[i], key=lambda p: abs(math.hypot(*p) - rr))
            p1 = min(spoke_pts[(i + 1) % NSP], key=lambda p: abs(math.hypot(*p) - rr))
            mid = ((p0[0] + p1[0]) / 2 * 1.04, (p0[1] + p1[1]) / 2 * 1.04)
            segs += [(p0, mid), (mid, p1)]
cv, cf = [], []
for (y0, z0), (y1, z1) in segs:
    if CRACK_C.z + min(z0, z1) < 0.13:           # below the frame
        continue
    d = V((0, y1 - y0, z1 - z0))
    if d.length < 1e-6:
        continue
    n = V((0, -d.z, d.y)).normalized() * (0.0017 * max(0.45, 1 - 0.6 * math.hypot(y0, z0)))
    base = len(cv)
    cv += [(0, y0 + n.y, z0 + n.z), (0, y0 - n.y, z0 - n.z), (0, y1 - n.y, z1 - n.z), (0, y1 + n.y, z1 + n.z)]
    cf.append([base, base + 1, base + 2, base + 3])
CRACK_M, nt_c, out_c = new_mat("Crack")
tcc = node(nt_c, "ShaderNodeTexCoord")
vl = nt_c.nodes.new("ShaderNodeVectorMath")
vl.operation = "LENGTH"
nt_c.links.new(tcc.outputs["Object"], vl.inputs[0])
rv = node(nt_c, "ShaderNodeValue")
CRACK_R = rv.outputs[0]
lt = nt_c.nodes.new("ShaderNodeMath")
lt.operation = "LESS_THAN"
nt_c.links.new(vl.outputs["Value"], lt.inputs[0])
nt_c.links.new(rv.outputs[0], lt.inputs[1])
trc = node(nt_c, "ShaderNodeBsdfTransparent")
emc = node(nt_c, "ShaderNodeEmission", Color=(0.85, 0.95, 1.0, 1), Strength=0.9)
mxc = nt_c.nodes.new("ShaderNodeMixShader")
nt_c.links.new(lt.outputs[0], mxc.inputs[0])
nt_c.links.new(trc.outputs[0], mxc.inputs[1])
nt_c.links.new(emc.outputs[0], mxc.inputs[2])
nt_c.links.new(mxc.outputs[0], out_c.inputs[0])
crack_o = obj_from("Crack", cv, cf, CRACK_M, smooth=False)
crack_o.location = K0 + CRACK_C
SETS["tank"].append(crack_o)
area("TankKey", K0 + V((0.5, -1.0, 5.0)), K0 + V((0.6, 0, 0.3)), 450, 3.5, (0.85, 0.95, 1.0), "tank")
area("TankRim", K0 + V((-3.0, 2.5, 2.2)), K0 + V((0.6, 0, 0.3)), 420, 2.0, (0.4, 0.75, 1.0), "tank")
area("TankFill", K0 + V((5.0, -2.5, 1.5)), K0 + V((0.6, 0, 0.3)), 110, 3.0, (1.0, 0.9, 0.8), "tank").visible_glossy = False

# ================================================================= REEF set: side view, snail, eye close-up, ending
R0 = V(T.REEF)
ground("ReefSand", R0, "reef")
rocks("ReefRocks", R0, "reef", [(-1.4, 1.3, 0.6), (-0.4, 2.0, 0.5), (0.3, 1.5, 0.35), (-2.4, -1.4, 0.7),
                                (2.4, 1.6, 0.5), (3.4, -0.6, 0.3), (-0.6, -1.9, 0.35)])
corals("ReefCoral", R0, "reef", [(-3.2, 2.6, 1.7), (-1.6, 3.6, 1.3), (1.5, 3.8, 1.5), (3.6, 2.6, 1.1), (-4.2, -2.2, 1.6)])
marine_snow("ReefSnow", R0, "reef", ((-3, 4), (-4, 4), (0, 2.5)), n=220)
shrimp_reef = make_shrimp("ShrimpReef", R0, 1.0, sets=("reef",))

# snail shell (log spiral tube) + its fragments
M_SNAILSHELL, nt_sh, out_sh = new_mat("SnailShell")
psh = shell_bsdf(nt_sh, (0.5, 0.36, 0.2), rough=0.3, coat=0.6)
tsh = node(nt_sh, "ShaderNodeTexCoord")
wv = node(nt_sh, "ShaderNodeTexWave", Scale=4.0, Distortion=4.0, Detail=3.0)
wv.wave_type = "RINGS"
nt_sh.links.new(tsh.outputs["Object"], wv.inputs["Vector"])
rsh = ramp(nt_sh, [(0.35, (0.62, 0.48, 0.3)), (0.55, (0.16, 0.07, 0.025)), (0.75, (0.62, 0.48, 0.3))])
nt_sh.links.new(wv.outputs["Fac"], rsh.inputs[0])
nt_sh.links.new(rsh.outputs[0], psh.inputs["Base Color"])
nt_sh.links.new(psh.outputs[0], out_sh.inputs[0])
SNAIL_C = R0 + V((1.52, 0.0, 0.0))
nu, nv, umax = 260, 18, 7.0 * math.pi
sv, sf = [], []
for i in range(nu):
    u = umax * i / (nu - 1)
    g = math.exp(0.2 * (u - umax))
    c = V((0.12 * g * math.cos(u), 0.12 * g * math.sin(u), 0.17 * (1 - g) + 0.1))
    rad = V((math.cos(u), math.sin(u), 0))
    a = 0.11 * g + 0.002
    for k in range(nv):
        w = 2 * math.pi * k / nv
        sv.append((c + a * (math.cos(w) * rad + math.sin(w) * V((0, 0, 1))))[:])
for i in range(nu - 1):
    for k in range(nv):
        sf.append([i * nv + k, i * nv + (k + 1) % nv, (i + 1) * nv + (k + 1) % nv, (i + 1) * nv + k])
snail = obj_from("Snail", sv, sf, M_SNAILSHELL)
snail.location = SNAIL_C
snail.rotation_euler = (0.5, 0.2, 2.6)
SETS["reef"].append(snail)
frags = []
fv, ff_ = sphere_vf(5, 3)
frnd = random.Random(5)
IMPACT = SNAIL_C + V((-0.17, 0, 0.17))
for k in range(46):
    jit = fv * np.array([frnd.uniform(0.6, 1.4) for _ in range(len(fv))])[:, None]
    s = frnd.uniform(0.025, 0.07)
    p0 = SNAIL_C + V((frnd.uniform(-0.15, 0.15), frnd.uniform(-0.17, 0.17), frnd.uniform(0.04, 0.33)))
    o = obj_from(f"Frag{k}", jit * np.array([s, s * frnd.uniform(0.6, 1.2), s * 0.35]), ff_, M_SNAILSHELL, smooth=False)
    vel = (p0 - IMPACT).normalized() * frnd.uniform(0.6, 1.6) + V((0, 0, frnd.uniform(0.3, 1.0)))
    spin = V((frnd.uniform(-8, 8), frnd.uniform(-8, 8), frnd.uniform(-8, 8)))
    frags.append((o, p0, vel, spin, s * 0.35))
    SETS["reef"].append(o)
area("ReefKey", R0 + V((0.8, -1.5, 5.0)), R0 + V((0.8, 0, 0.3)), 500, 3.5, (0.85, 0.95, 1.0), "reef")
area("ReefRim", R0 + V((-2.5, 3.0, 2.0)), R0 + V((0.8, 0, 0.3)), 480, 2.0, (0.35, 0.7, 1.0), "reef")
area("ReefFill", R0 + V((4.0, -3.0, 1.2)), R0 + V((0.8, 0, 0.3)), 120, 3.0, (1.0, 0.88, 0.78), "reef")

# ================================================================= MACRO set: club vs. shell in ultra slow motion
C0 = V(T.MACRO)
M_BIGSHELL, nt_bs, out_bs = new_mat("BigShell")
pbs = shell_bsdf(nt_bs, (0.5, 0.36, 0.22), rough=0.35, coat=0.5)
tbs = node(nt_bs, "ShaderNodeTexCoord")
wbs = node(nt_bs, "ShaderNodeTexWave", Scale=0.6, Distortion=3.0, Detail=4.0)
nt_bs.links.new(tbs.outputs["Object"], wbs.inputs["Vector"])
rbs = ramp(nt_bs, [(0.3, (0.55, 0.42, 0.26)), (0.55, (0.18, 0.08, 0.03)), (0.8, (0.55, 0.42, 0.26))])
nt_bs.links.new(wbs.outputs["Fac"], rbs.inputs[0])
nt_bs.links.new(rbs.outputs[0], pbs.inputs["Base Color"])
nzb = node(nt_bs, "ShaderNodeTexNoise", Scale=8.0, Detail=6.0)
nt_bs.links.new(tbs.outputs["Object"], nzb.inputs["Vector"])
bpb = node(nt_bs, "ShaderNodeBump", Strength=0.3, Distance=0.05)
nt_bs.links.new(nzb.outputs["Fac"], bpb.inputs["Height"])
nt_bs.links.new(bpb.outputs["Normal"], pbs.inputs["Normal"])
nt_bs.links.new(pbs.outputs[0], out_bs.inputs[0])
bigshell = sph("BigShell", C0 + V((30.0, 0, 0)), 30.0, M_BIGSHELL, u=128, v=64)
SETS["macro"].append(bigshell)
club_rig = empty("MacroClub", C0 + V((-3.0, 0, 0)))
BIG_CLUB_R = 0.6
for o in (sph("MacroBulb", (0, 0, 0), BIG_CLUB_R, M_CLUB, u=64, v=32, scale=(1.0, 0.85, 1.0)),
          sph("MacroFore", (-1.25, 0, 0.75), 1.0, M_ARM, u=48, v=24, scale=(1.5, 0.42, 0.46), rot=(0, 0.55, 0)),
          sph("MacroDact", (-0.55, 0, 0.62), 1.0, M_ARM, u=24, v=12, scale=(0.9, 0.14, 0.12), rot=(0, 0.5, 0))):
    o.parent = club_rig
    SETS["macro"].append(o)
SETS["macro"].append(club_rig)
GAP = C0 + V((-0.07, 0, 0))

M_BUBBLE, nt_bb, out_bb = new_mat("Bubble")
lwb = node(nt_bb, "ShaderNodeLayerWeight", Blend=0.35)
trb = node(nt_bb, "ShaderNodeBsdfTransparent")
glb = node(nt_bb, "ShaderNodeBsdfGlossy", Roughness=0.05)
emb = node(nt_bb, "ShaderNodeEmission", Color=(0.6, 0.85, 1.0, 1), Strength=0.6)
adb = nt_bb.nodes.new("ShaderNodeAddShader")
nt_bb.links.new(glb.outputs[0], adb.inputs[0])
nt_bb.links.new(emb.outputs[0], adb.inputs[1])
mxbb = nt_bb.nodes.new("ShaderNodeMixShader")
nt_bb.links.new(lwb.outputs["Facing"], mxbb.inputs[0])
nt_bb.links.new(trb.outputs[0], mxbb.inputs[1])
nt_bb.links.new(adb.outputs[0], mxbb.inputs[2])
nt_bb.links.new(mxbb.outputs[0], out_bb.inputs[0])
brnd = random.Random(9)
bubble_objs = []
for k in range(70):
    a = brnd.uniform(0, 2 * math.pi)
    rr = brnd.uniform(0.0, 0.75) ** 0.8
    off = V((brnd.uniform(-0.12, -0.01), rr * math.cos(a), rr * math.sin(a)))
    if k > 50:                                     # a few in the wake around the club's rim
        off = V((brnd.uniform(-0.45, -0.15), 0.62 * math.cos(a), 0.62 * math.sin(a)))
    r = brnd.uniform(0.02, 0.09)
    o = sph(f"Bub{k}", GAP + off, r, M_BUBBLE, u=24, v=12)
    bubble_objs.append((o, off, r, brnd.uniform(0, 1)))
    SETS["macro"].append(o)
FLASH_M, FLASH_A, FLASH_S = fade_emit_mat("Flash", (1.0, 0.93, 0.8), 40.0)
_nt = FLASH_M.node_tree
_lw = node(_nt, "ShaderNodeLayerWeight", Blend=0.5)
_pw = _nt.nodes.new("ShaderNodeMath")
_pw.operation = "POWER"
_pw.inputs[1].default_value = 3.0
_nt.links.new(_lw.outputs["Facing"], _pw.inputs[0])
_inv = _nt.nodes.new("ShaderNodeMath")
_inv.operation = "SUBTRACT"
_inv.inputs[0].default_value = 1.0
_nt.links.new(_pw.outputs[0], _inv.inputs[1])
_mul = _nt.nodes.new("ShaderNodeMath")
_mul.operation = "MULTIPLY"
_mix = next(n for n in _nt.nodes if n.type == "MIX_SHADER")
_val = next(n for n in _nt.nodes if n.type == "VALUE")
_nt.links.new(_val.outputs[0], _mul.inputs[0])
_nt.links.new(_inv.outputs[0], _mul.inputs[1])
_nt.links.new(_mul.outputs[0], _mix.inputs[0])
flash_o = sph("FlashCore", GAP, 1.0, FLASH_M, u=32, v=16)
no_bounce([flash_o])
RING_M, RING_A, RING_S = fade_emit_mat("Ring", (0.6, 0.85, 1.0), 6.0)
bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.02, major_segments=96, minor_segments=8,
                                 location=GAP, rotation=(0, math.pi / 2, 0))
ring_o = bpy.context.active_object
ring_o.data.materials.append(RING_M)
no_bounce([ring_o])
fl = bpy.data.lights.new("FlashLight", "POINT")
fl.color, fl.shadow_soft_size = (1.0, 0.9, 0.8), 0.1
flash_l = bpy.data.objects.new("FlashLight", fl)
flash_l.location = GAP + V((-0.05, 0, 0))
col.objects.link(flash_l)
SETS["macro"] += [flash_o, ring_o, flash_l]
marine_snow("MacroSnow", C0, "macro", ((-5, 0), (-3, 3), (-3, 3)), n=140)
area("MacroKey", C0 + V((-2.0, -3.0, 4.5)), C0 + V((-1.0, 0, 0)), 700, 3.0, (0.85, 0.95, 1.0), "macro")
area("MacroRim", C0 + V((-3.5, 4.0, 1.0)), C0 + V((-1.0, 0, 0)), 900, 2.0, (0.3, 0.6, 1.0), "macro")

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


SNAIL_SHOT = 4
prev_q = None
for f in range(T.NFRAMES):
    t = f / T.FPS
    CUR[0] = f
    st = T.shot_set(t)
    si = T.shot_index(t)
    for name, objs in SETS.items():
        for o in objs:
            key(o, "hide_render", name != st)
    key_socket(WORLD_STRENGTH, 0.8 if st == "macro" else 1.0)
    key_socket(CAUSTIC_W, t * 0.45)
    # tank
    pose_shrimp(shrimp_tank, t, strike=T.strike_tank(t))
    key_socket(CRACK_R, 1.8 * T.crack(t) + (0.0 if T.crack(t) > 0 else -1.0))
    # reef: which strike depends on the shot
    if si == 2:
        s_reef = T.strike_slowmo(t)
    elif si == 3:
        s_reef = T.strike_blink(t)
    elif si == 4:
        s_reef = T.strike_snail(t)
    else:
        s_reef = T.strike_loop(t)
    pose_shrimp(shrimp_reef, t, strike=s_reef, seed=1.0)
    tau = T.shatter(t)
    key(snail, "hide_render", st != "reef" or si < SNAIL_SHOT or tau >= 0)
    for o, p0, vel, spin, half in frags:
        if tau < 0:
            p, rot = p0, V((0, 0, 0))
        else:
            dr = (1 - math.exp(-3.0 * tau)) / 3.0
            p = p0 + vel * dr - V((0, 0, 1.4 * tau * tau))
            p.z = max(p.z, half + 0.005)
            rot = spin * dr
        key(o, "location", p)
        key(o, "rotation_euler", rot[:])
        key(o, "hide_render", st != "reef" or tau < 0)
    # macro
    mc = T.macro_club(t)
    key(club_rig, "location", C0 + V((T.lerp(-3.2, -0.07 - BIG_CLUB_R - 0.06, mc), 0, 0)))
    bb = T.bubbles(t)
    for o, off, r, ph in bubble_objs:
        g = T.clamp(bb * 1.3 - ph * 0.3)
        wob = 1 + 0.08 * math.sin(t * 9 + ph * 20)
        key(o, "scale", (max(1e-3, g * wob),) * 3)
        key(o, "location", GAP + off * (0.6 + 0.4 * g))
        key(o, "hide_render", st != "macro" or g <= 0.002)
    fv_ = T.flash(t)
    key(flash_o, "scale", (max(1e-3, 0.03 + 0.16 * fv_),) * 3)
    key_socket(FLASH_A, min(1.0, fv_ * 1.5))
    key_socket(FLASH_S, 6.0 + 30.0 * fv_)
    key(flash_o, "hide_render", st != "macro" or fv_ <= 0.003)
    fl.energy = 9000.0 * fv_
    fl.keyframe_insert("energy", frame=f)
    rg = T.ring(t)
    key(ring_o, "scale", (max(1e-3, 0.15 + 3.2 * T.ease_out(rg)),) * 3)
    key_socket(RING_A, (1 - rg) ** 1.5 if 0 < rg < 1 else 0.0)
    key(ring_o, "hide_render", st != "macro" or rg <= 0 or rg >= 1)
    # camera
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
    base = K0 if st == "tank" else R0
    fp = {"hero": base + V((0.85, 0, 0.32)), "glass": K0 + CRACK_C, "eye": R0 + V((0.96, 0.08, 0.55)),
          "club": (C0 + V((T.lerp(-3.2, -0.73, mc), 0, 0))) if st == "macro" else R0 + club_local(s_reef),
          "snail": SNAIL_C + V((-0.1, 0, 0.15)), "gap": GAP}[focus]
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
c.transparent_max_bounces = 8
c.transmission_bounces = 2
c.caustics_reflective = False
c.caustics_refractive = False
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.3
except Exception:
    pass
SPP = {"tank": 12, "reef": 12, "macro": 14}
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
