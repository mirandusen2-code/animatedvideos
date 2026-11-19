"""Blender scene for 'This Tiny Animal Survived 10 Days in Open Space' (procedural, Cycles).

Usage: python3 scene.py <out_dir> [--frames a,b,c | --range a b] [--res 1080x1920] [--quality 1.0]
"""
import bpy  # noqa: I001  (bpy must be imported before bmesh)
import bmesh
import json
import math
import os
import random
import sys

import numpy as np
from bpy_extras.object_utils import world_to_camera_view
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


def pmat(name, base, rough=0.5, metal=0.0, coat=0.0, emit=None, strength=0.0, transmission=0.0, ior=1.45):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (*base, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Transmission Weight"].default_value = transmission
    p.inputs["IOR"].default_value = ior
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = strength
    nt.links.new(p.outputs[0], out.inputs[0])
    return m, p


def glow_mat(name, color, strength, alpha=1.0):
    m, nt, out = new_mat(name)
    em = node(nt, "ShaderNodeEmission", Color=(*color, 1), Strength=strength)
    tr = node(nt, "ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    a = node(nt, "ShaderNodeValue")
    a.outputs[0].default_value = alpha
    nt.links.new(a.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m, a.outputs[0]


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

    def sphere(self, loc, scale, rot=(0, 0, 0)):
        self.add(SPH_V, SPH_F, Matrix.Translation(loc) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*scale, 1)))

    def build(self, name, mat, smooth=True):
        return obj_from(name, np.concatenate(self.v), self.f, mat, smooth)


def cylinder(b, p0, p1, r, seg=16):
    """Cylinder between two points, added to a Builder."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=1.0)
    bm.verts.index_update()
    vv = np.array([x.co[:] for x in bm.verts])
    ff = [[x.index for x in f.verts] for f in bm.faces]
    bm.free()
    m = Matrix.Translation((p0 + p1) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Diagonal((1, 1, d.length, 1))
    b.add(vv, ff, m)



def sph(name, loc, r, mat, u=48, v=24, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    o = bpy.data.objects.new(name, me)
    o.location, o.scale = loc, scale
    o.data.materials.append(mat)
    col.objects.link(o)
    return o


def no_bounce(objs):
    for o in objs:
        o.visible_diffuse = False
        o.visible_glossy = False


V = Vector
SETS = {k: [] for k in ("space", "ruler", "moss", "drop", "moon")}

# ================================================================= world: deep space with stars
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    if n.type != "OUTPUT_WORLD":
        wn.nodes.remove(n)
tcw = node(wn, "ShaderNodeTexCoord")
vor = node(wn, "ShaderNodeTexVoronoi", Scale=420.0)
wn.links.new(tcw.outputs["Generated"], vor.inputs["Vector"])
stars = ramp(wn, [(0.0, (1, 1, 1)), (0.022, (0, 0, 0))])
wn.links.new(vor.outputs["Distance"], stars.inputs[0])
mixw = wn.nodes.new("ShaderNodeMix")
mixw.data_type = "RGBA"
mixw.blend_type = "ADD"
mixw.inputs["Factor"].default_value = 1.0
mixw.inputs["A"].default_value = (0.002, 0.003, 0.008, 1)
wn.links.new(stars.outputs[0], mixw.inputs["B"])
WORLD_MIX = mixw.inputs["Factor"]
bgw = node(wn, "ShaderNodeBackground", Strength=1.0)
WORLD_STRENGTH = bgw.inputs["Strength"]
wn.links.new(mixw.outputs["Result"], bgw.inputs[0])
wn.links.new(bgw.outputs[0], wn.nodes["World Output"].inputs[0])

sun = bpy.data.lights.new("Sun", "SUN")
sun.energy, sun.angle, sun.color = 5.0, math.radians(0.6), (1.0, 0.96, 0.9)
sun_o = bpy.data.objects.new("Sun", sun)
sun_o.rotation_euler = Vector((0.9, -0.5, 0.55)).to_track_quat("Z", "Y").to_euler()      # side-front: lit Earth, crisp hero
col.objects.link(sun_o)

# ================================================================= hero: tardigrade rig
bear_m, nt_b, out_b = new_mat("Tardigrade")
pb = node(nt_b, "ShaderNodeBsdfPrincipled")
pb.inputs["Base Color"].default_value = (1.0, 0.62, 0.38, 1)
pb.inputs["Roughness"].default_value = 0.35
pb.inputs["Subsurface Weight"].default_value = 0.75
pb.subsurface_method = "BURLEY"                          # faster than random walk, same gummy look
pb.inputs["Subsurface Radius"].default_value = (1.0, 0.55, 0.35)
pb.inputs["Subsurface Scale"].default_value = 0.25
pb.inputs["Coat Weight"].default_value = 0.6
pb.inputs["Coat Roughness"].default_value = 0.15
pb.inputs["Emission Color"].default_value = (1.0, 0.45, 0.2, 1)
pb.inputs["Emission Strength"].default_value = 0.08
tcb = node(nt_b, "ShaderNodeTexCoord")
nzb = node(nt_b, "ShaderNodeTexNoise", Scale=9.0, Detail=6.0)
nt_b.links.new(tcb.outputs["Object"], nzb.inputs["Vector"])
bmp = node(nt_b, "ShaderNodeBump", Strength=0.25, Distance=0.02)
nt_b.links.new(nzb.outputs["Fac"], bmp.inputs["Height"])
nt_b.links.new(bmp.outputs["Normal"], pb.inputs["Normal"])
nt_b.links.new(pb.outputs[0], out_b.inputs[0])
BEAR_COLOR = pb.inputs["Base Color"]
claw_m, _ = pmat("Claw", (0.05, 0.03, 0.02), rough=0.3)
eye_m, _ = pmat("Eye", (0.02, 0.01, 0.01), rough=0.15)

BODY = [(-0.38, 0.30, 0.27, 0.25), (-0.12, 0.33, 0.30, 0.28), (0.14, 0.32, 0.29, 0.27), (0.38, 0.26, 0.24, 0.23)]
LEGS = [(-0.40, 1), (-0.40, -1), (-0.13, 1), (-0.13, -1), (0.13, 1), (0.13, -1), (0.36, 1), (0.36, -1)]


def make_bear(name, loc, scale=1.0, sets=()):
    root = bpy.data.objects.new(name, None)
    root.location = loc
    root.scale = (scale,) * 3
    col.objects.link(root)
    parts = {"root": root, "body": [], "legs": []}
    for i, (x, rx, ry, rz) in enumerate(BODY):
        o = sph(f"{name}_b{i}", (x, 0, 0.3), 1.0, bear_m, scale=(rx, ry, rz))
        o.parent = root
        parts["body"].append(o)
    head = sph(f"{name}_head", (0.62, 0, 0.30), 1.0, bear_m, scale=(0.20, 0.19, 0.18))
    head.parent = root
    snout = sph(f"{name}_snout", (0.80, 0, 0.27), 1.0, bear_m, scale=(0.07, 0.07, 0.06))
    snout.parent = root
    for sy in (1, -1):
        e = sph(f"{name}_eye{sy}", (0.72, 0.09 * sy, 0.38), 0.022, eye_m, u=16, v=8)
        e.parent = root
        parts["body"].append(e)
    parts["body"] += [head, snout]
    for k, (x, side) in enumerate(LEGS):
        piv = bpy.data.objects.new(f"{name}_lp{k}", None)
        piv.location = (x, 0.22 * side, 0.20)
        piv.parent = root
        col.objects.link(piv)
        leg = sph(f"{name}_l{k}", (0, 0.05 * side, -0.10), 1.0, bear_m, u=24, v=12, scale=(0.085, 0.085, 0.13))
        leg.parent = piv
        for c in range(3):
            cl = sph(f"{name}_c{k}{c}", ((c - 1) * 0.035, 0.05 * side, -0.235), 1.0, claw_m, u=8, v=6,
                     scale=(0.012, 0.012, 0.03))
            cl.parent = piv
        parts["legs"].append((piv, side))
    allobjs = [root] + list(root.children_recursive)
    for st in sets:
        SETS[st].extend(allobjs)
    parts["all"] = allobjs
    parts["base"] = scale
    return parts


def pose_bear(p, t, tun=0.0, walk=0.0, wiggle=1.0):
    """tun 0..1 (legs in, curled, shrunk); walk = gait phase speed."""
    root = p["root"]
    s = p["base"]
    for k, (piv, side) in enumerate(p["legs"]):
        ph = t * walk * 6.0 + k * 1.7 + (0 if side > 0 else math.pi)
        swing = (0.35 * math.sin(ph) if walk else 0.12 * math.sin(t * 2.0 + k)) * (1 - tun)
        key(piv, "rotation_euler", (0.25 * side * (1 - tun), swing, 0))
        ls = max(1e-3, 1 - 0.85 * tun)
        key(piv, "scale", (ls, ls, ls))
    curl = tun
    key(root, "scale", (s * (1 - 0.25 * curl), s * (1 - 0.1 * curl), s * (1 - 0.3 * curl)))
    key(root, "rotation_euler", (0, -0.25 * curl + 0.03 * wiggle * math.sin(t * 1.7), root.rotation_euler[2]))


# ================================================================= SPACE set
S0 = V(T.SPACE)
earth_m, nt_e, out_e = new_mat("Earth")
tce = node(nt_e, "ShaderNodeTexCoord")
nze = node(nt_e, "ShaderNodeTexNoise", Scale=0.02, Detail=8.0)
nt_e.links.new(tce.outputs["Object"], nze.inputs["Vector"])
cre = ramp(nt_e, [(0.50, (0.01, 0.10, 0.42)), (0.54, (0.08, 0.30, 0.12)), (0.64, (0.50, 0.44, 0.28))], interp="LINEAR")
nt_e.links.new(nze.outputs["Fac"], cre.inputs[0])
nzc = node(nt_e, "ShaderNodeTexNoise", Scale=0.035, Detail=6.0)
nt_e.links.new(tce.outputs["Object"], nzc.inputs["Vector"])
crc = ramp(nt_e, [(0.55, (0, 0, 0)), (0.7, (1, 1, 1))])
nt_e.links.new(nzc.outputs["Fac"], crc.inputs[0])
mxe = nt_e.nodes.new("ShaderNodeMix")
mxe.data_type = "RGBA"
nt_e.links.new(crc.outputs[0], mxe.inputs["Factor"])
nt_e.links.new(cre.outputs[0], mxe.inputs["A"])
mxe.inputs["B"].default_value = (0.95, 0.97, 1.0, 1)
pe = node(nt_e, "ShaderNodeBsdfPrincipled", Roughness=0.6)
nt_e.links.new(mxe.outputs["Result"], pe.inputs["Base Color"])
nt_e.links.new(pe.outputs[0], out_e.inputs[0])
earth = sph("Earth", S0 + V(T.EARTH_C), 230.0, earth_m, u=256, v=128)
atm_m, _ = glow_mat("Atmosphere", (0.35, 0.65, 1.0), 2.5, alpha=1.0)
m_, nt_a, out_a = new_mat("AtmosphereRim")
lw = node(nt_a, "ShaderNodeLayerWeight", Blend=0.5)
pw = node(nt_a, "ShaderNodeMath")
pw.operation = "POWER"
pw.inputs[1].default_value = 6.0                      # glow only at the limb, clear over the disc
nt_a.links.new(lw.outputs["Facing"], pw.inputs[0])
ema = node(nt_a, "ShaderNodeEmission", Color=(0.35, 0.68, 1.0, 1), Strength=6.0)
tra = node(nt_a, "ShaderNodeBsdfTransparent")
mxa = nt_a.nodes.new("ShaderNodeMixShader")
nt_a.links.new(pw.outputs[0], mxa.inputs[0])
nt_a.links.new(tra.outputs[0], mxa.inputs[1])
nt_a.links.new(ema.outputs[0], mxa.inputs[2])
nt_a.links.new(mxa.outputs[0], out_a.inputs[0])
atm = sph("Atmosphere", S0 + V(T.EARTH_C), 234.0, m_, u=256, v=128)
atm.visible_shadow = False
moon_m, nt_mo, out_mo = new_mat("MoonSurface")
tcm = node(nt_mo, "ShaderNodeTexCoord")
nzm = node(nt_mo, "ShaderNodeTexNoise", Scale=3.0, Detail=10.0)
nt_mo.links.new(tcm.outputs["Object"], nzm.inputs["Vector"])
crm = ramp(nt_mo, [(0.35, (0.18, 0.18, 0.19)), (0.6, (0.55, 0.55, 0.56))])
nt_mo.links.new(nzm.outputs["Fac"], crm.inputs[0])
pmo = node(nt_mo, "ShaderNodeBsdfPrincipled", Roughness=0.95)
nt_mo.links.new(crm.outputs[0], pmo.inputs["Base Color"])
bmm = node(nt_mo, "ShaderNodeBump", Strength=0.6)
nt_mo.links.new(nzm.outputs["Fac"], bmm.inputs["Height"])
nt_mo.links.new(bmm.outputs["Normal"], pmo.inputs["Normal"])
nt_mo.links.new(pmo.outputs[0], out_mo.inputs[0])
moon_sph = sph("MoonSphere", S0 + V(T.MOON_SPHERE), 24.0, moon_m, u=128, v=64)
SETS["space"] += [earth, atm, moon_sph]
bear_space = make_bear("BearSpace", S0, 1.0, sets=("space",))

# ================================================================= RULER set (steel ruler, mm ticks)
R0 = V(T.RULER)
steel_m, _ = pmat("Steel", (0.82, 0.84, 0.88), rough=0.35, metal=1.0)
ink_m, _ = pmat("Ink", (0.02, 0.02, 0.03), rough=0.5)
bpy.ops.mesh.primitive_cube_add(size=1, location=R0 + V((0, 0.0, -0.05)))
ruler = bpy.context.active_object
ruler.scale = (16, 4, 0.1)
ruler.data.materials.append(steel_m)
b = Builder()
for k in range(-14, 15):                      # 1 mm = 2 units; half-mm ticks
    x = k * 1.0
    long = k % 2 == 0
    cylinder(b, R0 + V((x, -1.4, 0.006)), R0 + V((x, -1.4 + (1.2 if long else 0.7), 0.006)), 0.045, seg=6)
ticks = b.build("RulerTicks", ink_m, smooth=False)
FONT = bpy.data.fonts.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viral-hooks", "fonts",
                                        "Montserrat-ExtraBold.otf"))
ruler_txt = []
for k, mm in enumerate(range(-7, 8)):
    cu = bpy.data.curves.new(f"RulerNum{k}", "FONT")
    cu.body, cu.font, cu.size = str(mm + 7), FONT, 0.45
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    o = bpy.data.objects.new(f"RulerNum{k}", cu)
    o.location = R0 + V((mm * 2.0, -1.7, 0.008))
    o.data.materials.append(ink_m)
    col.objects.link(o)
    ruler_txt.append(o)
cu = bpy.data.curves.new("RulerMM", "FONT")
cu.body, cu.font, cu.size = "mm", FONT, 0.4
o = bpy.data.objects.new("RulerMM", cu)
o.location = R0 + V((-13.5, -1.7, 0.008))
o.data.materials.append(ink_m)
col.objects.link(o)
ruler_txt.append(o)
bg_m, nt_rb, out_rb = new_mat("RulerBG")
tcrb = node(nt_rb, "ShaderNodeTexCoord")
seprb = nt_rb.nodes.new("ShaderNodeSeparateXYZ")
nt_rb.links.new(tcrb.outputs["Generated"], seprb.inputs[0])
crrb = ramp(nt_rb, [(0.45, (0.02, 0.03, 0.06)), (0.6, (0.10, 0.18, 0.32))])
nt_rb.links.new(seprb.outputs["Y"], crrb.inputs[0])
emrb = node(nt_rb, "ShaderNodeEmission", Strength=1.0)
nt_rb.links.new(crrb.outputs[0], emrb.inputs["Color"])
nt_rb.links.new(emrb.outputs[0], out_rb.inputs[0])
bpy.ops.mesh.primitive_plane_add(size=200, location=R0 + V((0, 40, 0)), rotation=(math.pi / 2, 0, 0))
ruler_bg = bpy.context.active_object
ruler_bg.data.materials.append(bg_m)
key_l = bpy.data.lights.new("RulerKey", "AREA")
key_l.energy, key_l.size, key_l.color = 700, 3.0, (1.0, 0.92, 0.82)
key_o = bpy.data.objects.new("RulerKey", key_l)
key_o.location = R0 + V((-3, -4, 5))
key_o.rotation_euler = V((-3, -4, 5)).to_track_quat("Z", "Y").to_euler()
col.objects.link(key_o)
rim_l = bpy.data.lights.new("RulerRim", "AREA")
rim_l.energy, rim_l.size, rim_l.color = 900, 2.0, (0.55, 0.75, 1.0)
rim_o = bpy.data.objects.new("RulerRim", rim_l)
rim_o.location = R0 + V((3, 4, 3))
rim_o.rotation_euler = V((3, 4, 3)).to_track_quat("Z", "Y").to_euler()
col.objects.link(rim_o)
SETS["ruler"] += [ruler, ticks, ruler_bg, key_o, rim_o] + ruler_txt
bear_ruler = make_bear("BearRuler", R0 + V((0, 0, 0)), 1.0, sets=("ruler",))

# ================================================================= MOSS set (moss forest, water drop)
M0 = V(T.MOSS)
moss_m, nt_ms, out_ms = new_mat("Moss")
pms = node(nt_ms, "ShaderNodeBsdfPrincipled", Roughness=0.6)
pms.inputs["Subsurface Weight"].default_value = 0.0
pms.inputs["Subsurface Radius"].default_value = (0.3, 1.0, 0.3)
tcs = node(nt_ms, "ShaderNodeTexCoord")
nzs = node(nt_ms, "ShaderNodeTexNoise", Scale=2.0)
nt_ms.links.new(tcs.outputs["Object"], nzs.inputs["Vector"])
crs = ramp(nt_ms, [(0.3, (0.05, 0.22, 0.05)), (0.7, (0.25, 0.55, 0.12))])
nt_ms.links.new(nzs.outputs["Fac"], crs.inputs[0])
nt_ms.links.new(crs.outputs[0], pms.inputs["Base Color"])
nt_ms.links.new(pms.outputs[0], out_ms.inputs[0])
bl = Builder()
rnd = random.Random(5)
for _ in range(650):                                   # moss: thin stems, small leaves spiralling up
    x, y = rnd.uniform(-8, 8), rnd.uniform(-1.5, 12)
    if (abs(x) < 1.6 and -1.4 < y < 1.4) or (y < 0.8 and abs(x) < 5.5):   # nothing between camera and bear
        continue
    h = rnd.uniform(0.6, 2.2) * (1 + 0.04 * y)
    tilt = rnd.uniform(-0.2, 0.2)
    cylinder(bl, M0 + V((x, y, -0.1)), M0 + V((x + tilt, y, h)), 0.025, seg=5)
    nl = 14
    for j in range(nl):
        z = h * (0.15 + 0.85 * j / nl)
        a_ = j * 2.4
        rr = 0.07 * (1.2 - 0.6 * j / nl)
        bl.sphere(M0 + V((x + tilt * z / h + rr * math.cos(a_), y + rr * math.sin(a_), z)),
                  (0.022, 0.012, 0.11 * (1.15 - 0.5 * j / nl)), rot=(0.75 * math.sin(a_), -0.75 * math.cos(a_), 0))
moss = bl.build("MossForest", moss_m)
bpy.ops.mesh.primitive_plane_add(size=60, location=M0 + V((0, 0, -0.05)))
moss_floor = bpy.context.active_object
moss_floor.data.materials.append(moss_m)
pad = sph("MossPad", M0 + V((0, 0, -0.35)), 1.0, moss_m, scale=(1.6, 1.4, 0.42))
water_m, _ = pmat("Water", (0.85, 0.95, 1.0), rough=0.02, transmission=1.0, ior=1.33)
drop = sph("Drop", M0 + V((0, 0, 3.0)), 0.55, water_m)
mbg_m, nt_mb, out_mb = new_mat("MossBG")
tcmb = node(nt_mb, "ShaderNodeTexCoord")
sepmb = nt_mb.nodes.new("ShaderNodeSeparateXYZ")
nt_mb.links.new(tcmb.outputs["Generated"], sepmb.inputs[0])
crmb = ramp(nt_mb, [(0.0, (0.02, 0.06, 0.02)), (1.0, (0.35, 0.55, 0.25))])
nt_mb.links.new(sepmb.outputs["Z"], crmb.inputs[0])
emmb = node(nt_mb, "ShaderNodeEmission", Strength=1.0)
nt_mb.links.new(crmb.outputs[0], emmb.inputs["Color"])
nt_mb.links.new(emmb.outputs[0], out_mb.inputs[0])
bpy.ops.mesh.primitive_plane_add(size=120, location=M0 + V((0, 30, 10)), rotation=(math.pi / 2, 0, 0))
moss_bg = bpy.context.active_object
moss_bg.data.materials.append(mbg_m)
mk = bpy.data.lights.new("MossKey", "AREA")
mk.energy, mk.size, mk.color = 900, 4.0, (1.0, 0.9, 0.75)
mk_o = bpy.data.objects.new("MossKey", mk)
mk_o.location = M0 + V((-4, -3, 6))
mk_o.rotation_euler = V((-4, -3, 6)).to_track_quat("Z", "Y").to_euler()
col.objects.link(mk_o)
mr = bpy.data.lights.new("MossRim", "AREA")
mr.energy, mr.size, mr.color = 1200, 2.5, (1.0, 0.7, 0.45)
mr_o = bpy.data.objects.new("MossRim", mr)
mr_o.location = M0 + V((3, 5, 2.5))
mr_o.rotation_euler = V((3, 5, 2.5)).to_track_quat("Z", "Y").to_euler()
col.objects.link(mr_o)
no_bounce([moss, moss_floor, moss_bg])
SETS["moss"] += [moss, moss_floor, pad, drop, moss_bg, mk_o, mr_o]
bear_moss = make_bear("BearMoss", M0 + V((0, 0, 0.0)), 1.0, sets=("moss",))

# ================================================================= DROP set (babies inside a water drop)
D0 = V(T.DROP)
dbg_m, nt_db, out_db = new_mat("DropBG")
tcd = node(nt_db, "ShaderNodeTexCoord")
sepd = nt_db.nodes.new("ShaderNodeSeparateXYZ")
nt_db.links.new(tcd.outputs["Generated"], sepd.inputs[0])
crd = ramp(nt_db, [(0.3, (0.0, 0.08, 0.14)), (0.55, (0.02, 0.32, 0.42)), (0.8, (0.45, 0.85, 0.95))])
nt_db.links.new(sepd.outputs["Z"], crd.inputs[0])
emd = node(nt_db, "ShaderNodeEmission", Strength=1.0)
nt_db.links.new(crd.outputs[0], emd.inputs["Color"])
nt_db.links.new(emd.outputs[0], out_db.inputs[0])
dome = sph("DropDome", D0, 14.0, dbg_m, u=96, v=48)
egg_m, _ = pmat("Egg", (1.0, 0.85, 0.6), rough=0.2, transmission=0.4)
eggs = []
erand = random.Random(3)
for k in range(7):
    a = k / 7 * 6.28
    eggs.append(sph(f"Egg{k}", D0 + V((-0.9 + 0.35 * math.cos(a), 0.35 * math.sin(a), -0.15 + 0.05 * erand.random())),
                    0.18, egg_m, u=24, v=12))
bub_m, _ = pmat("Bubble", (1, 1, 1), rough=0.0, transmission=1.0, ior=1.33)
bubbles = []
for k in range(40):
    p = D0 + V((erand.uniform(-4, 4), erand.uniform(-1, 6), erand.uniform(-2, 4)))
    bubbles.append(sph(f"Bub{k}", p, erand.uniform(0.03, 0.12), bub_m, u=16, v=8))
dk = bpy.data.lights.new("DropKey", "AREA")
dk.energy, dk.size, dk.color = 800, 3.0, (1.0, 0.9, 0.8)
dk_o = bpy.data.objects.new("DropKey", dk)
dk_o.location = D0 + V((-3, -4, 4))
dk_o.rotation_euler = V((-3, -4, 4)).to_track_quat("Z", "Y").to_euler()
col.objects.link(dk_o)
SETS["drop"] += [dome, dk_o] + eggs + bubbles
bear_drop = make_bear("BearDrop", D0 + V((0.4, 0, -0.3)), 1.0, sets=("drop",))
babies = [make_bear(f"Baby{k}", D0 + V((-0.9 + 0.5 * math.cos(k * 2.1), 0.5 * math.sin(k * 2.1), -0.25)), 0.3,
                    sets=("drop",)) for k in range(3)]

# ================================================================= MOON set
N0 = V(T.MOON)
n = 140
xs = np.linspace(-60, 60, n)
X, Y = np.meshgrid(xs, xs)
Z = 0.25 * np.sin(X / 3.1) * np.cos(Y / 4.3) + 0.15 * np.sin(X / 1.3 + Y / 2.1)
crng = np.random.default_rng(4)
for _ in range(40):                                   # craters: bowl + raised rim
    cx, cy, r = crng.uniform(-50, 50), crng.uniform(-10, 60), crng.uniform(1.5, 7)
    d = np.hypot(X - cx, Y - cy) / r
    Z += np.where(d < 1, -0.35 * r * (1 - d ** 2) * 0.3, 0.08 * r * np.exp(-((d - 1.05) / 0.15) ** 2))
Z[np.hypot(X, Y) < 4] *= 0.2
gv = np.stack([X.ravel() + N0.x, Y.ravel() + N0.y, Z.ravel() + N0.z], 1)
gf = [[i * n + j, i * n + j + 1, (i + 1) * n + j + 1, (i + 1) * n + j] for i in range(n - 1) for j in range(n - 1)]
regolith = obj_from("Regolith", gv, gf, moon_m)
earth_sky = sph("EarthInMoonSky", N0 + V((10, 160, 45)), 12.0, earth_m, u=96, v=48)
atm2 = sph("EarthInMoonSkyAtm", N0 + V((10, 160, 45)), 12.25, m_, u=96, v=48)
dust_m, DUST_A = glow_mat("Dust", (0.75, 0.73, 0.70), 0.0, alpha=0.0)
m_d, nt_du, out_du = new_mat("DustPlume")
pdu = node(nt_du, "ShaderNodeBsdfPrincipled", Roughness=1.0)
pdu.inputs["Base Color"].default_value = (0.55, 0.54, 0.52, 1)
tdu = node(nt_du, "ShaderNodeBsdfTransparent")
mdu = nt_du.nodes.new("ShaderNodeMixShader")
adu = node(nt_du, "ShaderNodeValue")
adu.outputs[0].default_value = 0.0
DUST_A = adu.outputs[0]
nt_du.links.new(adu.outputs[0], mdu.inputs[0])
nt_du.links.new(tdu.outputs[0], mdu.inputs[1])
nt_du.links.new(pdu.outputs[0], mdu.inputs[2])
nt_du.links.new(mdu.outputs[0], out_du.inputs[0])
pdu.inputs["Base Color"].default_value = (0.78, 0.76, 0.72, 1)
gold_m, _ = pmat("GoldFoil", (1.0, 0.72, 0.25), rough=0.25, metal=1.0)
lander = Builder()
lander.add(*sphere_vf(4, 2), Matrix.Translation((0, 0, 0)) @ Matrix.Diagonal((0.9, 0.9, 0.7, 1)))
for sx in (-1, 1):
    for sy in (-1, 1):
        cylinder(lander, (0.5 * sx, 0.5 * sy, -0.3), (1.0 * sx, 1.0 * sy, -1.0), 0.05, seg=6)
lander = lander.build("Lander", gold_m, smooth=False)
plume = []
prnd = random.Random(8)
for k in range(30):
    a = prnd.uniform(0, 6.28)
    plume.append((sph(f"Plume{k}", N0 + V((0, 25, 0)), 1.0, m_d, u=24, v=12),
                  V((math.cos(a) * prnd.uniform(0.4, 1), math.sin(a) * prnd.uniform(0.4, 1), prnd.uniform(0.3, 1.2))),
                  prnd.uniform(0.8, 2.0)))
SETS["moon"] += [regolith, earth_sky, atm2, lander] + [p[0] for p in plume]
moon_tuns = [make_bear(f"MoonTun{k}", N0 + V(pos), sc, sets=("moon",))
             for k, (pos, sc) in enumerate((((0, 0, 0.05), 1.0), ((-1.6, 2.5, 0.0), 0.8), ((1.9, 3.6, 0.0), 0.7)))]

# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.sensor_width = 36
cam_d.clip_start = 0.01
cam_d.clip_end = 5000
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


all_lights = {"ruler": [key_o, rim_o], "moss": [mk_o, mr_o], "drop": [dk_o]}
prev_q = None
for f in range(T.NFRAMES):
    t = f / T.FPS
    CUR[0] = f
    st = T.shot_set(t)
    for name, objs in SETS.items():
        for o in objs:
            key(o, "hide_render", name != st)
    key(sun_o, "hide_render", st not in ("space", "moon"))
    key_socket(WORLD_MIX, 1.0 if st in ("space", "moon") else 0.0)
    # hero poses
    pose_bear(bear_space, t, tun=1.0, wiggle=0)
    key(bear_space["root"], "rotation_euler", (0.35 * math.sin(t * 0.5), 0.25 * t, 0.6 + 0.3 * t))
    rx = T.lerp(-0.4, 0.9, T.clamp((t - T.SHOTS[2][0]) / (T.SHOTS[2][1] - T.SHOTS[2][0])))
    key(bear_ruler["root"], "location", V(T.RULER) + V((rx, 0, 0)))
    pose_bear(bear_ruler, t, tun=0.0, walk=1.0)
    tm = T.tun_moss(t)
    pose_bear(bear_moss, t, tun=tm)
    key_socket(BEAR_COLOR, tuple(a + (b2 - a) * (tm if st == "moss" else (1.0 if st in ("space", "moon") else 0.0))
                                 for a, b2 in zip((1.0, 0.62, 0.38, 1), (0.55, 0.32, 0.18, 1))))
    dz = T.drop_fall(t)
    sp_ = T.drop_spread(t)
    key(drop, "location", M0 + V((0, 0, 0.55 + dz - 0.1 * sp_)))
    key(drop, "scale", (1 + 0.55 * sp_, 1 + 0.4 * sp_, 1 - 0.12 * sp_))     # settles around the bear
    key(drop, "hide_render", st != "moss" or t < T.L["wakes"][0] - 0.4)
    pose_bear(bear_drop, t, tun=0.0)
    hb = T.babies(t)
    for k, e in enumerate(eggs):
        key(e, "scale", (max(1e-3, 1 - hb),) * 3)
    for k, bb in enumerate(babies):
        sc = 0.3 * T.ease_out((hb - 0.1 * k) / 0.6)
        bb["base"] = max(sc, 1e-3)
        pose_bear(bb, t + k, tun=0.0, walk=0.6)
    for p in moon_tuns:
        pose_bear(p, t, tun=1.0, wiggle=0)
    pl = T.plume(t)
    for o, dvec, spd in plume:
        g = T.ease_out(pl)
        key(o, "location", N0 + V((0, 25, 0.3)) + dvec * 5.0 * g * spd)
        key(o, "scale", (max(1e-3, (0.3 + 1.4 * g) * (1 if pl > 0 else 0.001)),) * 3)
        key(o, "hide_render", st != "moon" or pl <= 0 or pl >= 1)
    fall = T.clamp((t - (T.L["moon"][0] + 0.2)) / 0.7)
    key(lander, "location", N0 + V((-6 + 6 * fall, 25, 14 * (1 - fall) + 0.6)))
    key(lander, "rotation_euler", (0.3, 0.2 * (1 - fall), 0.8))
    key(lander, "hide_render", st != "moon" or fall >= 1)
    key_socket(DUST_A, 0.0 if pl <= 0 else 0.9 * (1 - pl) ** 1.4)
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
    fp = Vector(T.hero_pos(t)) if focus == "hero" else Vector(tgt)
    cam_d.dof.focus_distance = (Vector(loc) - fp).length
    cam_d.dof.keyframe_insert("focus_distance", frame=f)

for idb in list(bpy.data.objects) + list(bpy.data.materials) + list(bpy.data.cameras) + list(bpy.data.worlds):
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
c.transparent_max_bounces = 6
c.transmission_bounces = 4
c.caustics_reflective = False
c.caustics_refractive = False
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
SPP = {"space": 10, "ruler": 12, "moss": 12, "drop": 12, "moon": 10}
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
