"""Blender scene for 'This Sugar Cube Weighs More Than Every Human on Earth'.

Builds everything procedurally (studio + balance scale + sugar cube + figurine pile, and a space set with
a red giant, supernova, neutron star and pulsar beams), keyframes every frame from timeline.py
(so Cycles renders real motion blur), then renders the requested frames.

Usage: python3 scene.py <out_dir> [--frames a,b,c | --range a b] [--res 720x1280] [--quality 1.0]
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
RES = (540, 960)
if "--res" in args:
    RES = tuple(int(v) for v in args[args.index("--res") + 1].split("x"))
QUALITY = float(args[args.index("--quality") + 1]) if "--quality" in args else 1.0
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = T.FPS
scene.frame_start, scene.frame_end = 0, T.NFRAMES - 1
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


def principled_mat(name, base, rough=0.5, metal=0.0, sss=0.0, coat=0.0):
    m, nt, out = new_mat(name)
    p = node(nt, "ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (*base, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if sss:
        p.inputs["Subsurface Weight"].default_value = sss
        p.inputs["Subsurface Radius"].default_value = (0.4, 0.3, 0.25)
        p.inputs["Subsurface Scale"].default_value = 0.01
    if coat:
        p.inputs["Coat Weight"].default_value = coat
    nt.links.new(p.outputs[0], out.inputs[0])
    return m, p


def glow_mat(name, color, strength, fresnel_power=None, alpha=1.0):
    """Emission (optionally edge-weighted) mixed with transparency. Returns (material, alpha_input)."""
    m, nt, out = new_mat(name)
    L = nt.links
    em = node(nt, "ShaderNodeEmission", Color=(*color, 1), Strength=strength)
    tr = node(nt, "ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    a = node(nt, "ShaderNodeValue")
    a.outputs[0].default_value = alpha
    fac = a.outputs[0]
    if fresnel_power:
        lw = node(nt, "ShaderNodeLayerWeight", Blend=0.5)
        pw = node(nt, "ShaderNodeMath")
        pw.operation = "POWER"
        pw.inputs[1].default_value = fresnel_power
        L.new(lw.outputs["Facing"], pw.inputs[0])
        mul = node(nt, "ShaderNodeMath")
        mul.operation = "MULTIPLY"
        L.new(pw.outputs[0], mul.inputs[0])
        L.new(a.outputs[0], mul.inputs[1])
        fac = mul.outputs[0]
    L.new(fac, mix.inputs[0])
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs[0])
    return m, a.outputs[0]


def mesh_obj(name, bm, mat=None, parent=None, smooth=True):
    me = bpy.data.meshes.new(name)
    for f in bm.faces:
        f.smooth = smooth
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    if mat:
        ob.data.materials.append(mat)
    col.objects.link(ob)
    if parent:
        ob.parent = parent
    return ob


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    col.objects.link(e)
    if parent:
        e.parent = parent
    return e


def uvsphere(bm, r, loc=(0, 0, 0), scale=(1, 1, 1), u=32, v=16, rot=None):
    res = bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)
    m = Matrix.Translation(loc) @ (rot.to_matrix().to_4x4() if rot else Matrix()) @ Matrix.Diagonal((*scale, 1))
    bmesh.ops.transform(bm, matrix=m, verts=res["verts"])


def cylinder(bm, r, z0, z1, seg=48, loc=(0, 0, 0)):
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=z1 - z0)
    bmesh.ops.translate(bm, vec=(loc[0], loc[1], loc[2] + (z0 + z1) / 2), verts=res["verts"])


def bevel_mod(ob, width, seg=3):
    b = ob.modifiers.new("Bevel", "BEVEL")
    b.width = width
    b.segments = seg
    b.limit_method = "ANGLE"


# ================================================================= materials
brass, _ = principled_mat("Brass", (0.80, 0.55, 0.24), rough=0.22, metal=1.0)
stone, _ = principled_mat("Stone", (0.02, 0.02, 0.022), rough=0.35, coat=0.6)
floor_m, _ = principled_mat("Floor", (0.012, 0.013, 0.016), rough=0.16)
dome_m, _ = principled_mat("Dome", (0.035, 0.04, 0.05), rough=1.0)
porcelain, _ = principled_mat("Porcelain", (0.86, 0.85, 0.82), rough=0.3, coat=0.4)

# sugar: grainy subsurface white, glows ice-blue when it turns out to be neutron-star matter
sugar, nt_s, out_s = None, None, None
sugar, nt_s, out_s = new_mat("Sugar")
p_s = node(nt_s, "ShaderNodeBsdfPrincipled")
p_s.inputs["Base Color"].default_value = (0.78, 0.77, 0.76, 1)
p_s.inputs["Roughness"].default_value = 0.42
p_s.inputs["Subsurface Weight"].default_value = 0.0
p_s.inputs["Subsurface Radius"].default_value = (0.5, 0.5, 0.5)
p_s.inputs["Subsurface Scale"].default_value = 0.004
p_s.inputs["Emission Color"].default_value = (0.1, 0.42, 1.0, 1)
SUGAR_GLOW = p_s.inputs["Emission Strength"]
tc = node(nt_s, "ShaderNodeTexCoord")
vor = node(nt_s, "ShaderNodeTexVoronoi", Scale=140.0)
nt_s.links.new(tc.outputs["Object"], vor.inputs["Vector"])
bump = node(nt_s, "ShaderNodeBump", Strength=1.0, Distance=0.0015)
nt_s.links.new(vor.outputs["Distance"], bump.inputs["Height"])
nt_s.links.new(bump.outputs["Normal"], p_s.inputs["Normal"])
rgr = ramp(nt_s, [(0.0, (0.15, 0.15, 0.15)), (1.0, (0.7, 0.7, 0.7))])
nt_s.links.new(vor.outputs["Color"], rgr.inputs[0])
nt_s.links.new(rgr.outputs[0], p_s.inputs["Roughness"])
nt_s.links.new(p_s.outputs[0], out_s.inputs[0])

# red giant: boiling plasma
star_m, nt_st, out_st = new_mat("Star")
tc = node(nt_st, "ShaderNodeTexCoord")
nz = nt_st.nodes.new("ShaderNodeTexNoise")
nz.noise_dimensions = "4D"
nz.inputs["Scale"].default_value = 2.6
nz.inputs["Detail"].default_value = 12
nz.inputs["Roughness"].default_value = 0.62
STAR_W = nz.inputs["W"]
nt_st.links.new(tc.outputs["Object"], nz.inputs["Vector"])
cr = ramp(nt_st, [(0.30, (0.18, 0.01, 0.0)), (0.46, (0.75, 0.08, 0.01)), (0.6, (1.0, 0.3, 0.03)), (0.74, (1.0, 0.62, 0.2))])
nt_st.links.new(nz.outputs["Fac"], cr.inputs[0])
lw = node(nt_st, "ShaderNodeLayerWeight", Blend=0.35)
limb = ramp(nt_st, [(0.0, (1, 1, 1)), (1.0, (0.25, 0.25, 0.25))])
nt_st.links.new(lw.outputs["Facing"], limb.inputs[0])
mx = nt_st.nodes.new("ShaderNodeMix")
mx.data_type = "RGBA"
mx.blend_type = "MULTIPLY"
mx.inputs["Factor"].default_value = 1.0
nt_st.links.new(cr.outputs[0], mx.inputs["A"])
nt_st.links.new(limb.outputs[0], mx.inputs["B"])
em = node(nt_st, "ShaderNodeEmission", Strength=1.8)
STAR_STRENGTH = em.inputs["Strength"]
nt_st.links.new(mx.outputs["Result"], em.inputs["Color"])
nt_st.links.new(em.outputs[0], out_st.inputs[0])

corona_m, CORONA_A = glow_mat("Corona", (1.0, 0.25, 0.04), 2.0, fresnel_power=3.0, alpha=0.7)
shell_m, SHELL_A = glow_mat("NovaShell", (0.35, 0.6, 1.0), 2.2, fresnel_power=4.0, alpha=0.0)
ring_m, RING_A = glow_mat("Shockwave", (0.5, 0.75, 1.0), 4.0, alpha=0.0)
ns_m, _ = glow_mat("NeutronStar", (0.55, 0.8, 1.0), 4.0, alpha=1.0)
ns_m, nt_ns, out_ns = new_mat("NeutronStarSurface")
tcn = node(nt_ns, "ShaderNodeTexCoord")
nzn = node(nt_ns, "ShaderNodeTexNoise", Scale=7.0, Detail=8.0)
nt_ns.links.new(tcn.outputs["Object"], nzn.inputs["Vector"])
crn = ramp(nt_ns, [(0.3, (0.1, 0.3, 1.0)), (0.5, (0.45, 0.7, 1.0)), (0.68, (0.9, 0.95, 1.0))])
nt_ns.links.new(nzn.outputs["Fac"], crn.inputs[0])
emn = node(nt_ns, "ShaderNodeEmission", Strength=1.6)
nt_ns.links.new(crn.outputs[0], emn.inputs["Color"])
nt_ns.links.new(emn.outputs[0], out_ns.inputs[0])
nsglow_m, NSGLOW_A = glow_mat("NSGlow", (0.25, 0.55, 1.0), 1.6, fresnel_power=5.0, alpha=0.8)
field_m, FIELD_A = glow_mat("FieldLines", (0.3, 0.6, 1.0), 1.6, alpha=0.0)

# pulsar beam: bright near the star, fading with distance and towards the edges
beam_m, nt_b, out_b = new_mat("Beam")
Lb = nt_b.links
tc = node(nt_b, "ShaderNodeTexCoord")
sep = nt_b.nodes.new("ShaderNodeSeparateXYZ")
Lb.new(tc.outputs["Object"], sep.inputs[0])
fade = ramp(nt_b, [(0.0, (1, 1, 1)), (0.35, (0.55, 0.55, 0.55)), (1.0, (0, 0, 0))])
mr = nt_b.nodes.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value = 0.0
mr.inputs["From Max"].default_value = 14.0
Lb.new(sep.outputs["Z"], mr.inputs["Value"])
Lb.new(mr.outputs["Result"], fade.inputs[0])
lwb = node(nt_b, "ShaderNodeLayerWeight", Blend=0.5)
edge = ramp(nt_b, [(0.0, (1, 1, 1)), (0.8, (0, 0, 0))])
Lb.new(lwb.outputs["Facing"], edge.inputs[0])
m1 = node(nt_b, "ShaderNodeMath")
m1.operation = "MULTIPLY"
Lb.new(fade.outputs[0], m1.inputs[0])
Lb.new(edge.outputs[0], m1.inputs[1])
BEAM_A = node(nt_b, "ShaderNodeValue")
BEAM_A.outputs[0].default_value = 0.0
m2 = node(nt_b, "ShaderNodeMath")
m2.operation = "MULTIPLY"
Lb.new(m1.outputs[0], m2.inputs[0])
Lb.new(BEAM_A.outputs[0], m2.inputs[1])
emb = node(nt_b, "ShaderNodeEmission", Color=(0.45, 0.75, 1.0, 1), Strength=2.6)
trb = node(nt_b, "ShaderNodeBsdfTransparent")
mxb = nt_b.nodes.new("ShaderNodeMixShader")
Lb.new(m2.outputs[0], mxb.inputs[0])
Lb.new(trb.outputs[0], mxb.inputs[1])
Lb.new(emb.outputs[0], mxb.inputs[2])
Lb.new(mxb.outputs[0], out_b.inputs[0])
BEAM_A = BEAM_A.outputs[0]

# ================================================================= world (space: stars + faint nebula)
world = bpy.data.worlds.new("Space")
scene.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    if n.type != "OUTPUT_WORLD":
        wn.nodes.remove(n)
tcw = node(wn, "ShaderNodeTexCoord")
vor = node(wn, "ShaderNodeTexVoronoi", Scale=260.0)
wn.links.new(tcw.outputs["Generated"], vor.inputs["Vector"])
stars = ramp(wn, [(0.0, (1, 1, 1)), (0.03, (0, 0, 0))])
wn.links.new(vor.outputs["Distance"], stars.inputs[0])
neb = node(wn, "ShaderNodeTexNoise", Scale=1.6, Detail=6.0)
wn.links.new(tcw.outputs["Generated"], neb.inputs["Vector"])
nebc = ramp(wn, [(0.45, (0.0, 0.0, 0.0)), (0.7, (0.03, 0.015, 0.05)), (0.85, (0.02, 0.03, 0.07))])
wn.links.new(neb.outputs["Fac"], nebc.inputs[0])
add = wn.nodes.new("ShaderNodeMix")
add.data_type = "RGBA"
add.blend_type = "ADD"
add.inputs["Factor"].default_value = 1.0
wn.links.new(nebc.outputs[0], add.inputs["A"])
wn.links.new(stars.outputs[0], add.inputs["B"])
bg = node(wn, "ShaderNodeBackground", Strength=1.0)
wn.links.new(add.outputs["Result"], bg.inputs[0])
wn.links.new(bg.outputs[0], wn.nodes["World Output"].inputs[0])

# ================================================================= studio
studio = []
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=22)
bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
studio.append(mesh_obj("Dome", bm, dome_m))
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=20)
studio.append(mesh_obj("Floor", bm, floor_m, smooth=False))

# balance scale
bm = bmesh.new()
cylinder(bm, 0.34, 0.0, 0.07, seg=96)
base = mesh_obj("Base", bm, stone)
bevel_mod(base, 0.01)
bm = bmesh.new()
cylinder(bm, 0.03, 0.07, T.PIVOT[2] - 0.05, seg=48)
cylinder(bm, 0.065, 0.07, 0.12, seg=48)
uvsphere(bm, 0.055, loc=T.PIVOT)
pillar = mesh_obj("Pillar", bm, brass)
bevel_mod(pillar, 0.004)
beam_e = empty("BeamPivot", T.PIVOT)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(2 * T.ARM + 0.06, 0.035, 0.035), verts=bm.verts)
for sx in (-1, 1):
    uvsphere(bm, 0.03, loc=(sx * T.ARM, 0, 0))
beam = mesh_obj("Beam", bm, brass, parent=beam_e)
bevel_mod(beam, 0.008)
pans, rods = {}, {}
for side in (-1, 1):
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=96, radius1=0.36, radius2=0.42, depth=0.035)
    bmesh.ops.translate(bm, vec=(0, 0, 0.0175), verts=res["verts"])
    pan = mesh_obj(f"Pan{side}", bm, brass)
    bevel_mod(pan, 0.006)
    pans[side] = pan
    rods[side] = []
    for k in range(3):
        bm = bmesh.new()
        cylinder(bm, 0.004, -0.5, 0.5, seg=12)
        rods[side].append(mesh_obj(f"Rod{side}{k}", bm, brass))
studio += [base, pillar, beam] + list(pans.values()) + [r for v in rods.values() for r in v]

# sugar cube (on the left pan)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=T.CUBE)
cube = mesh_obj("SugarCube", bm, sugar, parent=pans[-1], smooth=False)
bevel_mod(cube, 0.006, seg=4)
cube.rotation_euler = (0, 0, 0.35)
cube_light = bpy.data.lights.new("CubeGlow", "POINT")
cube_light.color = (0.5, 0.8, 1.0)
cube_light.shadow_soft_size = 0.05
cube_light_o = bpy.data.objects.new("CubeGlow", cube_light)
cube_light_o.parent = cube
col.objects.link(cube_light_o)
studio += [cube, cube_light_o]

# "every human on Earth": a hill crowded with standing porcelain figurines (on the right pan)
def figure_template():
    """One tiny person, feet at z=0, ~6.5 cm tall: legs, torso, arms, head. Returns (verts Nx3, faces)."""
    parts = [((-0.0052, 0, 0.0145), (0.0046, 0.0046, 0.0150)), ((0.0052, 0, 0.0145), (0.0046, 0.0046, 0.0150)),
             ((0, 0, 0.0375), (0.0100, 0.0070, 0.0165)),
             ((-0.0130, 0, 0.0365), (0.0036, 0.0036, 0.0140)), ((0.0130, 0, 0.0365), (0.0036, 0.0036, 0.0140)),
             ((0, 0, 0.0600), (0.0076, 0.0076, 0.0080))]
    bm = bmesh.new()
    for loc, sc in parts:
        res = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=7, radius=1.0)
        bmesh.ops.transform(bm, matrix=Matrix.Translation(loc) @ Matrix.Diagonal((*sc, 1)), verts=res["verts"])
    bm.verts.index_update()
    v = np.array([vv.co[:] for vv in bm.verts])
    f = [[vv.index for vv in face.verts] for face in bm.faces]
    bm.free()
    return v, f


def hill_h(r):
    return 0.15 * math.sqrt(max(0.0, 1 - (r / 0.34) ** 2))


rnd = random.Random(8)
FV, FF = figure_template()
verts, faces = [], []
bm_h = bmesh.new()
res = bmesh.ops.create_uvsphere(bm_h, u_segments=48, v_segments=24, radius=1.0)
bmesh.ops.transform(bm_h, matrix=Matrix.Translation((0, 0, 0.035)) @ Matrix.Diagonal((0.34, 0.34, 0.15, 1)), verts=res["verts"])
bm_h.verts.index_update()
hv = np.array([vv.co[:] for vv in bm_h.verts])
hv[:, 2] = np.maximum(hv[:, 2], 0.03)              # dome only, flat underside
verts.append(hv)
faces += [[vv.index for vv in face.verts] for face in bm_h.faces]
off = len(bm_h.verts)
bm_h.free()
placed = []
tries = 0
while len(placed) < 560 and tries < 20000:
    tries += 1
    r = 0.32 * math.sqrt(rnd.random())
    th = rnd.uniform(0, 2 * math.pi)
    x, y = r * math.cos(th), r * math.sin(th)
    if any((x - px) ** 2 + (y - py) ** 2 < 0.026 ** 2 for px, py in placed):
        continue
    placed.append((x, y))
    z = 0.035 + hill_h(r) - 0.004
    s_ = rnd.uniform(1.25, 1.5)
    m = (Matrix.Translation((x, y, z)) @ Euler((rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12),
                                                  rnd.uniform(0, 6.3))).to_matrix().to_4x4() @ Matrix.Scale(s_, 4))
    M = np.array(m)
    verts.append(FV @ M[:3, :3].T + M[:3, 3])
    faces += [[i + off for i in fc] for fc in FF]
    off += len(FV)
me = bpy.data.meshes.new("People")
me.from_pydata(np.concatenate(verts).tolist(), [], faces)
me.shade_smooth()
pile = bpy.data.objects.new("People", me)
pile.data.materials.append(porcelain)
pile.parent = pans[1]
col.objects.link(pile)
studio.append(pile)

# lights
def area(name, loc, target, power, size, color):
    lt = bpy.data.lights.new(name, "AREA")
    lt.energy, lt.size, lt.color = power, size, color
    o = bpy.data.objects.new(name, lt)
    o.location = loc
    o.rotation_euler = (Vector(loc) - Vector(target)).to_track_quat("Z", "Y").to_euler()
    col.objects.link(o)
    return o


studio += [
    area("Key", (-2.2, -2.6, 3.2), (0, 0, 1.0), 750, 1.6, (1.0, 0.86, 0.7)),
    area("Rim", (2.6, 2.4, 2.6), (0, 0, 1.0), 900, 1.2, (0.55, 0.75, 1.0)),
    area("Fill", (2.8, -2.4, 1.2), (0, 0, 1.0), 90, 2.5, (0.9, 0.9, 1.0)),
    area("Backdrop", (0, 3.0, 4.5), (0, 9.0, 1.0), 900, 4.0, (0.45, 0.55, 0.85)),
]

# ================================================================= space set
space = []
S = Vector(T.STAR)
bm = bmesh.new()
uvsphere(bm, 6.0, u=128, v=64)
giant = mesh_obj("Giant", bm, star_m)
giant.location = S
bm = bmesh.new()
uvsphere(bm, 6.9, u=96, v=48)
corona = mesh_obj("Corona", bm, corona_m)
corona.location = S
bm = bmesh.new()
uvsphere(bm, 1.0, u=96, v=48)
shell = mesh_obj("NovaShell", bm, shell_m)
shell.location = S
bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.012, major_segments=128, minor_segments=12)
ring = bpy.context.active_object
ring.name = "Shockwave"
ring.data.materials.append(ring_m)
ring.location = S
ring.rotation_euler = (math.radians(72), math.radians(12), 0)
bm = bmesh.new()
uvsphere(bm, 0.42, u=64, v=32)
ns = mesh_obj("NeutronStar", bm, ns_m)
ns.location = S
bm = bmesh.new()
uvsphere(bm, 1.1, u=64, v=32)
nsglow = mesh_obj("NSGlow", bm, nsglow_m)
nsglow.location = S
space += [giant, corona, shell, ring, ns, nsglow]

# pulsar: spin axis (z) + tilted magnetic axis carrying beams and field lines
spin_e = empty("Spin", T.STAR)
mag_e = empty("MagneticAxis", parent=spin_e)
mag_e.rotation_euler = (math.radians(28), 0, 0)
for k, rx in enumerate((0.0, math.pi)):
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=False, segments=48, radius1=0.04, radius2=0.85, depth=14.0)
    bmesh.ops.translate(bm, vec=(0, 0, 7.0 + 0.35), verts=res["verts"])
    b = mesh_obj(f"Beam{k}", bm, beam_m, parent=mag_e)
    b.rotation_euler = (rx, 0, 0)
    space.append(b)
for Lsh in (1.9, 3.1):
    for j in range(6):
        cu = bpy.data.curves.new(f"Field{Lsh}{j}", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.006
        sp = cu.splines.new("POLY")
        pts = []
        for i in range(61):
            th = 0.18 + (math.pi - 0.36) * i / 60
            rr = Lsh * math.sin(th) ** 2
            pts.append((rr * math.sin(th), 0, rr * math.cos(th)))
        sp.points.add(len(pts) - 1)
        for p, c in zip(sp.points, pts):
            p.co = (*c, 1)
        o = bpy.data.objects.new(f"Field{Lsh}{j}", cu)
        o.data.materials.append(field_m)
        o.parent = mag_e
        o.rotation_euler = (0, 0, j * math.pi / 3)
        col.objects.link(o)
        space.append(o)


# ================================================================= squeeze set: our Sun crushed into a tiny ball
squeeze_set = []
SUNV = Vector(T.SUN)
sun_m, nt_su, out_su = new_mat("Sun")
tcs = node(nt_su, "ShaderNodeTexCoord")
nzs = nt_su.nodes.new("ShaderNodeTexNoise")
nzs.noise_dimensions = "4D"
nzs.inputs["Scale"].default_value = 3.0
nzs.inputs["Detail"].default_value = 10
SUN_W = nzs.inputs["W"]
nt_su.links.new(tcs.outputs["Object"], nzs.inputs["Vector"])
crs = ramp(nt_su, [(0.35, (0.6, 0.12, 0.0)), (0.55, (1.0, 0.42, 0.03)), (0.72, (1.0, 0.75, 0.25))])
nt_su.links.new(nzs.outputs["Fac"], crs.inputs[0])
crb = ramp(nt_su, [(0.35, (0.35, 0.6, 1.0)), (0.6, (0.75, 0.88, 1.0)), (0.75, (1.0, 1.0, 1.0))])
nt_su.links.new(nzs.outputs["Fac"], crb.inputs[0])
mxs = nt_su.nodes.new("ShaderNodeMix")
mxs.data_type = "RGBA"
SUN_SHIFT = mxs.inputs["Factor"]
nt_su.links.new(crs.outputs[0], mxs.inputs["A"])
nt_su.links.new(crb.outputs[0], mxs.inputs["B"])
ems = node(nt_su, "ShaderNodeEmission", Strength=1.3)
SUN_STRENGTH = ems.inputs["Strength"]
nt_su.links.new(mxs.outputs["Result"], ems.inputs["Color"])
nt_su.links.new(ems.outputs[0], out_su.inputs[0])
bm = bmesh.new()
uvsphere(bm, 6.0, u=128, v=64)
sun_o = mesh_obj("Sun", bm, sun_m)
sun_o.location = SUNV
suncor_m, SUNCOR_A = glow_mat("SunCorona", (1.0, 0.6, 0.15), 2.0, fresnel_power=3.0, alpha=0.8)
bm = bmesh.new()
uvsphere(bm, 6.9, u=96, v=48)
suncor = mesh_obj("SunCorona", bm, suncor_m)
suncor.location = SUNV
squeeze_set += [sun_o, suncor]
sq_rings = []
for k, (rot, mult) in enumerate((((1.2, 0.2, 0), 1.35), ((0.3, 1.1, 0.4), 1.6), ((1.9, -0.6, 0.9), 1.9))):
    rm, ra = glow_mat(f"SqueezeRing{k}", (1.0, 0.85, 0.55), 3.0, alpha=0.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.01, major_segments=128, minor_segments=8)
    ro = bpy.context.active_object
    ro.name = f"SqueezeRing{k}"
    ro.data.materials.append(rm)
    ro.location = SUNV
    ro.rotation_euler = rot
    sq_rings.append((ro, ra, mult))
    squeeze_set.append(ro)

# ================================================================= city set: a neutron star as wide as a city
city_set = []
CITYV = Vector(T.CITY)
ground_m, _ = principled_mat("Ground", (0.012, 0.013, 0.016), rough=0.35)
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=120)
ground = mesh_obj("Ground", bm, ground_m, smooth=False)
ground.location = CITYV
city_set.append(ground)
bld_m, nt_bl, out_bl = new_mat("Buildings")
Lc = nt_bl.links
pb = node(nt_bl, "ShaderNodeBsdfPrincipled")
pb.inputs["Base Color"].default_value = (0.03, 0.032, 0.04, 1)
pb.inputs["Roughness"].default_value = 0.5
tcb = node(nt_bl, "ShaderNodeTexCoord")
# window grid: u along the facade (x + y), v up the building; per-cell random decides if a light is on
sepo = nt_bl.nodes.new("ShaderNodeSeparateXYZ")
Lc.new(tcb.outputs["Object"], sepo.inputs[0])


def mnode(op, a=None, b=None, va=None, vb=None):
    n = node(nt_bl, "ShaderNodeMath")
    n.operation = op
    if a is not None:
        Lc.new(a, n.inputs[0])
    elif va is not None:
        n.inputs[0].default_value = va
    if b is not None:
        Lc.new(b, n.inputs[1])
    elif vb is not None:
        n.inputs[1].default_value = vb
    return n.outputs[0]


u = mnode("MULTIPLY", mnode("ADD", sepo.outputs["X"], sepo.outputs["Y"]), vb=11.0)
v = mnode("MULTIPLY", sepo.outputs["Z"], vb=16.0)
fu, fv = mnode("FRACT", u), mnode("FRACT", v)
rect = mnode("MULTIPLY", mnode("MULTIPLY", mnode("GREATER_THAN", fu, vb=0.22), mnode("LESS_THAN", fu, vb=0.78)),
             mnode("MULTIPLY", mnode("GREATER_THAN", fv, vb=0.3), mnode("LESS_THAN", fv, vb=0.75)))
cell = nt_bl.nodes.new("ShaderNodeCombineXYZ")
Lc.new(mnode("FLOOR", u), cell.inputs["X"])
Lc.new(mnode("FLOOR", v), cell.inputs["Y"])
wn_ = nt_bl.nodes.new("ShaderNodeTexWhiteNoise")
wn_.noise_dimensions = "3D"
Lc.new(cell.outputs[0], wn_.inputs["Vector"])
on = mnode("GREATER_THAN", wn_.outputs["Value"], vb=0.62)
window_mask = mnode("MULTIPLY", rect, on)
geo = nt_bl.nodes.new("ShaderNodeNewGeometry")
sepn = nt_bl.nodes.new("ShaderNodeSeparateXYZ")
Lc.new(geo.outputs["Normal"], sepn.inputs[0])
absz = node(nt_bl, "ShaderNodeMath")
absz.operation = "ABSOLUTE"
Lc.new(sepn.outputs["Z"], absz.inputs[0])
walls = node(nt_bl, "ShaderNodeMath")
walls.operation = "LESS_THAN"
walls.inputs[1].default_value = 0.5
Lc.new(absz.outputs[0], walls.inputs[0])
m2c = node(nt_bl, "ShaderNodeMath")
m2c.operation = "MULTIPLY"
Lc.new(window_mask, m2c.inputs[0])
Lc.new(walls.outputs[0], m2c.inputs[1])
m3c = node(nt_bl, "ShaderNodeMath")
m3c.operation = "MULTIPLY"
m3c.inputs[1].default_value = 2.2
Lc.new(m2c.outputs[0], m3c.inputs[0])
pb.inputs["Emission Color"].default_value = (1.0, 0.62, 0.28, 1)
Lc.new(m3c.outputs[0], pb.inputs["Emission Strength"])
Lc.new(pb.outputs[0], out_bl.inputs[0])
# buildings: one mesh built with numpy from a unit cube
crnd = random.Random(21)
cube_v = np.array([(x, y, z) for x in (-0.5, 0.5) for y in (-0.5, 0.5) for z in (0.0, 1.0)])
cube_f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
bverts, bfaces = [], []
off = 0
g = 0.95
for ix in range(-13, 14):
    for iy in range(-13, 14):
        x, y = ix * g + crnd.uniform(-0.12, 0.12), iy * g + crnd.uniform(-0.12, 0.12)
        r = math.hypot(x, y)
        if r > 11.5 or ix % 5 == 0 or iy % 6 == 0:          # city edge + avenues
            continue
        for _ in range(2 if r < 6 else 1):
            w, d = crnd.uniform(0.3, 0.42), crnd.uniform(0.3, 0.42)
            hgt = crnd.uniform(0.25, 0.9) + 3.2 * math.exp(-(r / 3.2) ** 2) * crnd.uniform(0.4, 1.3)
            ox, oy = crnd.uniform(-0.2, 0.2), crnd.uniform(-0.2, 0.2)
            v = cube_v * np.array([w, d, hgt]) + np.array([x + ox, y + oy, 0])
            bverts.append(v)
            bfaces += [[i + off for i in f] for f in cube_f]
            off += 8
me = bpy.data.meshes.new("Buildings")
me.from_pydata(np.concatenate(bverts).tolist(), [], bfaces)
bld = bpy.data.objects.new("Buildings", me)
bld.data.materials.append(bld_m)
bld.location = CITYV
col.objects.link(bld)
city_set.append(bld)
bm = bmesh.new()
uvsphere(bm, 10.0, u=128, v=64)
nsc_m, nt_nc, out_nc = new_mat("NSCitySurface")
tcc = node(nt_nc, "ShaderNodeTexCoord")
nzc = node(nt_nc, "ShaderNodeTexNoise", Scale=1.4, Detail=10.0)
nt_nc.links.new(tcc.outputs["Object"], nzc.inputs["Vector"])
crc = ramp(nt_nc, [(0.3, (0.04, 0.12, 0.6)), (0.5, (0.25, 0.55, 1.0)), (0.66, (0.75, 0.9, 1.0))])
nt_nc.links.new(nzc.outputs["Fac"], crc.inputs[0])
emc = node(nt_nc, "ShaderNodeEmission", Strength=0.9)
nt_nc.links.new(crc.outputs[0], emc.inputs["Color"])
nt_nc.links.new(emc.outputs[0], out_nc.inputs[0])
ns_city = mesh_obj("NSCity", bm, nsc_m)
ns_city.location = Vector(T.NS_CITY)
cityglow_m, _ = glow_mat("NSCityGlow", (0.3, 0.6, 1.0), 1.0, fresnel_power=5.0, alpha=0.45)
bm = bmesh.new()
uvsphere(bm, 12.5, u=96, v=48)
ns_city_glow = mesh_obj("NSCityGlow", bm, cityglow_m)
ns_city_glow.location = Vector(T.NS_CITY)
moon = bpy.data.lights.new("CityMoon", "SUN")
moon.energy = 0.25
moon.color = (0.5, 0.65, 1.0)
moon_o = bpy.data.objects.new("CityMoon", moon)
moon_o.rotation_euler = (math.radians(50), 0, math.radians(30))
col.objects.link(moon_o)
ns_city.visible_shadow = False
ns_city_glow.visible_shadow = False
nsl = bpy.data.lights.new("NSCityLight", "POINT")
nsl.energy = 60000
nsl.color = (0.45, 0.65, 1.0)
nsl.shadow_soft_size = 9.0
nsl_o = bpy.data.objects.new("NSCityLight", nsl)
nsl_o.location = Vector(T.NS_CITY)
col.objects.link(nsl_o)
city_set += [ns_city, ns_city_glow, moon_o, nsl_o]

# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.sensor_width = 36
cam_d.clip_start = 0.01
cam_d.clip_end = 400
cam_d.dof.use_dof = True
cam = bpy.data.objects.new("Cam", cam_d)
col.objects.link(cam)
scene.camera = cam
cam.rotation_mode = "QUATERNION"
PILE_PT = Vector((T.pan_pos(1, T.TILT_CUBE)[0], 0.0, T.pan_pos(1, T.TILT_CUBE)[2] + 0.15))
prev_q = None

# ================================================================= keyframe everything
CUR = [0]   # frame being keyed (keyframe_insert with an explicit frame: no per-frame scene evaluation)


def key(obj, path, value=None):
    if value is not None:
        setattr(obj, path, value)
    obj.keyframe_insert(path, frame=CUR[0])


def key_socket(sock, value):
    sock.default_value = value
    sock.keyframe_insert("default_value", frame=CUR[0])


studio_set = set(o.name for o in studio)
for f in range(T.NFRAMES):
    t = f / T.FPS
    CUR[0] = f
    shot = T.shot(t)
    in_space = shot in ("star", "pulsar")
    elsewhere = shot in ("star", "pulsar", "squeeze", "city")
    for o in studio:
        key(o, "hide_render", elsewhere)
    for o in squeeze_set:
        key(o, "hide_render", shot != "squeeze")
    for o in city_set:
        key(o, "hide_render", shot != "city")
    # the Sun being squeezed
    q = T.squeeze(t) if shot == "squeeze" else 0.0
    ssc = 1.0 - 0.93 * q
    key(sun_o, "scale", (ssc,) * 3)
    key(suncor, "scale", (ssc,) * 3)
    key_socket(SUN_SHIFT, T.smoother((q - 0.6) / 0.4))      # stay orange, then turn blue-white at the end
    key_socket(SUN_STRENGTH, 1.3 + 1.6 * q)
    key_socket(SUN_W, t * 0.15)
    for ro, ra, mult in sq_rings:
        key(ro, "scale", (6.0 * ssc * mult,) * 3)
        key_socket(ra, 0.0 if shot != "squeeze" else min(1.0, q * 4) * (1 - q * 0.3))
    for o in space:
        if o.parent is None or o.parent.name != "MagneticAxis":
            key(o, "hide_render", not in_space)
    # scale
    tilt = T.scale_tilt(t)
    key(beam_e, "rotation_euler", (0, tilt, 0))
    for side in (-1, 1):
        pp = Vector(T.pan_pos(side, tilt))
        key(pans[side], "location", pp)
        end = pp + Vector((0, 0, T.HANG))
        for k, ang in enumerate((90, 210, 330)):
            a = math.radians(ang)
            rim = pp + Vector((0.39 * math.cos(a), 0.39 * math.sin(a), 0.03))
            d = end - rim
            key(rods[side][k], "location", (end + rim) / 2)
            key(rods[side][k], "rotation_euler", d.to_track_quat("Z", "Y").to_euler())
            key(rods[side][k], "scale", (1, 1, d.length))
    drop = T.cube_drop(t) if shot == "end" else 0.0
    key(cube, "location", (0, 0, 0.035 + T.CUBE / 2 + drop))
    g = T.cube_glow(t)
    key_socket(SUGAR_GLOW, 1.8 * g)
    key_socket(p_s.inputs["Base Color"], tuple(a + (b - a) * g for a, b in zip((0.78, 0.77, 0.76, 1), (0.04, 0.14, 0.45, 1))))
    cube_light.energy = 5.0 * g
    cube_light.keyframe_insert("energy", frame=f)
    # space
    ss = T.star_scale(t)
    key(giant, "scale", (max(ss, 1e-4),) * 3)
    key(corona, "scale", (max(ss, 1e-4),) * 3)
    key_socket(STAR_W, t * 0.12)
    nv = T.nova(t)
    key(shell, "scale", (0.5 + 17 * (1 - (1 - nv) ** 2.2),) * 3)
    key_socket(SHELL_A, 0.0 if nv <= 0 else 0.8 * (1 - nv) ** 1.2)
    key(ring, "scale", (0.5 + 22 * T.ease_out(nv),) * 3)
    key_socket(RING_A, 0.0 if nv <= 0 else (1 - nv) ** 1.5)
    nsv = T.ns_visible(t)
    key(ns, "scale", (max(nsv, 1e-4),) * 3)
    key(nsglow, "scale", (max(nsv, 1e-4) * (1 + 0.04 * math.sin(t * 9)),) * 3)
    pa = T.clamp((t - T.T_PULSAR) / 0.35) if shot == "pulsar" else 0.0
    key_socket(BEAM_A, pa)
    key_socket(FIELD_A, 0.35 * pa)
    key(spin_e, "rotation_euler", (0, 0, T.pulsar_spin(t) if shot == "pulsar" else 0.0))
    # camera
    loc, target, lens, fstop, focus, roll = T.camera(t)
    q = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y") @ Quaternion((0, 0, 1), math.radians(roll))
    if prev_q is not None and prev_q.dot(q) < 0:
        q.negate()
    prev_q = q.copy()
    key(cam, "location", loc)
    key(cam, "rotation_quaternion", q)
    cam_d.lens = lens
    cam_d.keyframe_insert("lens", frame=f)
    cam_d.dof.aperture_fstop = fstop
    cam_d.dof.keyframe_insert("aperture_fstop", frame=f)
    fp = {"cube": Vector(T.CUBE_POS), "pile": PILE_PT}.get(focus, Vector(target))
    cam_d.dof.focus_distance = (Vector(loc) - fp).length
    cam_d.dof.keyframe_insert("focus_distance", frame=f)

# linear interpolation everywhere (values are already eased per frame)
for idblock in list(bpy.data.objects) + list(bpy.data.materials) + list(bpy.data.cameras) + list(bpy.data.lights):
    ad = getattr(idblock, "animation_data", None)
    nts = [idblock] + ([idblock.node_tree] if getattr(idblock, "node_tree", None) else [])
    for owner in nts:
        ad = getattr(owner, "animation_data", None)
        if not ad or not ad.action:
            continue
        for fc in getattr(ad.action, "fcurves", []):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT" if fc.data_path == "hide_render" else "LINEAR"

# ================================================================= render settings
r = scene.render
r.engine = "CYCLES"
r.resolution_x, r.resolution_y = RES
r.resolution_percentage = 100
r.image_settings.file_format = "PNG"
r.use_motion_blur = True
r.motion_blur_shutter = 0.5
r.motion_blur_position = "START"     # blur only looks forward: the first frame of a shot never mixes in the previous shot
r.use_persistent_data = False
c = scene.cycles
c.device = "CPU"
c.use_adaptive_sampling = True
c.adaptive_threshold = 0.05
c.use_denoising = True
c.max_bounces = 4
c.transparent_max_bounces = 16
c.caustics_reflective = False
c.caustics_refractive = False
c.blur_glossy = 1.0
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass

SPP = {"studio": 12, "end": 12, "macro": 16, "macro2": 16, "star": 8, "pulsar": 8, "squeeze": 8, "city": 16}
proj_path = os.path.join(OUT, "projections.json")
proj = json.load(open(proj_path)) if os.path.exists(proj_path) else {}
for f in FRAMES:
    t = f / T.FPS
    scene.frame_set(f)
    sh = T.shot(t)
    r.use_motion_blur = T.shot_index((f + 1) / T.FPS) == T.shot_index(t)   # no blur smear across a cut
    c.samples = max(4, int(SPP[sh] * QUALITY))
    bpy.context.view_layer.update()
    v = world_to_camera_view(scene, cam, Vector(T.STAR))
    vc = world_to_camera_view(scene, cam, cube.matrix_world.translation)
    proj[str(f)] = {"star": [round(v.x, 4), round(1 - v.y, 4), round(v.z, 2)],
                    "cube": [round(vc.x, 4), round(1 - vc.y, 4), round(vc.z, 2)]}
    path = os.path.join(OUT, f"f_{f:04d}.png")
    if not os.path.exists(path):
        r.filepath = path
        bpy.ops.render.render(write_still=True)
        print(f"rendered {f} ({sh})", flush=True)
json.dump(proj, open(proj_path, "w"))
print("done")
