"""Blender scene for 'This Fluffy Cloud Weighs Half a Million Kilos' (procedural, Cycles).

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


# ================================================================= world: daytime sky
world = bpy.data.worlds.new("Sky")
scene.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    if n.type != "OUTPUT_WORLD":
        wn.nodes.remove(n)
tc = node(wn, "ShaderNodeTexCoord")
sep = wn.nodes.new("ShaderNodeSeparateXYZ")
wn.links.new(tc.outputs["Generated"], sep.inputs[0])
sky = ramp(wn, [(0.45, (0.80, 0.86, 0.92)), (0.53, (0.55, 0.72, 0.92)), (0.75, (0.18, 0.42, 0.85)), (1.0, (0.08, 0.25, 0.7))])
wn.links.new(sep.outputs["Z"], sky.inputs[0])
bg = node(wn, "ShaderNodeBackground", Strength=1.0)
wn.links.new(sky.outputs[0], bg.inputs[0])
wn.links.new(bg.outputs[0], wn.nodes["World Output"].inputs[0])

sun = bpy.data.lights.new("Sun", "SUN")
sun.energy = 4.0
sun.angle = math.radians(1.5)
sun.color = (1.0, 0.93, 0.82)
sun_o = bpy.data.objects.new("Sun", sun)
sun_o.rotation_euler = Vector((-0.6, -0.8, 0.55)).to_track_quat("Z", "Y").to_euler()
col.objects.link(sun_o)

# ================================================================= sky set
sky_set = []
# rolling green hills
grass_m, nt_g, out_g = new_mat("Grass")
pg = node(nt_g, "ShaderNodeBsdfPrincipled")
pg.inputs["Roughness"].default_value = 0.9
tcg = node(nt_g, "ShaderNodeTexCoord")
nzg = node(nt_g, "ShaderNodeTexNoise", Scale=0.05, Detail=6.0)
nt_g.links.new(tcg.outputs["Object"], nzg.inputs["Vector"])
crg = ramp(nt_g, [(0.35, (0.10, 0.28, 0.06)), (0.6, (0.22, 0.48, 0.12)), (0.75, (0.36, 0.55, 0.16))])
nt_g.links.new(nzg.outputs["Fac"], crg.inputs[0])
nt_g.links.new(crg.outputs[0], pg.inputs["Base Color"])
nt_g.links.new(pg.outputs[0], out_g.inputs[0])
n = 160
xs = np.linspace(-500, 500, n)
X, Y = np.meshgrid(xs, xs)
Z = (3.5 * np.sin(X / 37.0) * np.cos(Y / 53.0) + 2.0 * np.sin(X / 17.0 + 1) * np.sin(Y / 23.0)
     + 0.0005 * (X ** 2 + (Y - 120) ** 2) * (np.hypot(X, Y) > 120))
Z[np.hypot(X, Y) < 40] *= 0.3                          # flatter field where the herd stands
gv = np.stack([X.ravel(), Y.ravel(), Z.ravel() - 1.0], 1)
gf = [[i * n + j, i * n + j + 1, (i + 1) * n + j + 1, (i + 1) * n + j] for i in range(n - 1) for j in range(n - 1)]
sky_set.append(obj_from("Hills", gv, gf, grass_m))

# trees on the hills for scale (low-poly, two greens)
tree_m, _ = pmat("TreeLeaves", (0.1, 0.3, 0.08), rough=0.8)
trunk_m, _ = pmat("TreeTrunk", (0.25, 0.15, 0.08), rough=0.9)
rnd = random.Random(3)
bl, bt = Builder(), Builder()
for _ in range(260):
    x, y = rnd.uniform(-300, 300), rnd.uniform(-60, 400)
    if math.hypot(x, y) < 50:
        continue
    z = (3.5 * math.sin(x / 37.0) * math.cos(y / 53.0) + 2.0 * math.sin(x / 17.0 + 1) * math.sin(y / 23.0) - 1.0
         + (0.0005 * (x * x + (y - 120) ** 2) if math.hypot(x, y) > 120 else 0))
    s = rnd.uniform(1.6, 3.2)
    cylinder(bt, (x, y, z), (x, y, z + 1.4 * s), 0.18 * s, seg=8)
    bl.sphere((x, y, z + 2.2 * s), (1.0 * s, 1.0 * s, 1.25 * s))
    bl.sphere((x + 0.4 * s, y, z + 2.9 * s), (0.7 * s, 0.7 * s, 0.8 * s))
sky_set += [bl.build("TreeTops", tree_m), bt.build("Trunks", trunk_m)]
for o in sky_set:                       # grass/trees don't bounce green light into the white cloud
    o.visible_diffuse = False
    o.visible_glossy = False

# hero cumulus: metaball cluster (flat bottom, billowing top)
cloud_m, nt_c, out_c = new_mat("Cloud")
pc = node(nt_c, "ShaderNodeBsdfPrincipled")
pc.inputs["Base Color"].default_value = (0.95, 0.96, 0.98, 1)
pc.inputs["Roughness"].default_value = 1.0
pc.inputs["Subsurface Weight"].default_value = 0.65
pc.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.05)
pc.inputs["Subsurface Scale"].default_value = 0.6
pc.inputs["Sheen Weight"].default_value = 0.4
nt_c.links.new(pc.outputs[0], out_c.inputs[0])
mb = bpy.data.metaballs.new("CloudMeta")
mb.resolution = 0.25
mb.render_resolution = 0.12
mb.threshold = 0.6
crnd = random.Random(12)
for i in range(70):
    a = crnd.uniform(0, 2 * math.pi)
    r = 7.0 * math.sqrt(crnd.random())
    x, y = r * math.cos(a), 0.55 * r * math.sin(a)
    hmax = 5.5 * (1 - (r / 8.0) ** 2)
    z = crnd.uniform(-0.5, hmax * 0.8)
    el = mb.elements.new()
    el.co = (x, y, z)
    el.radius = crnd.uniform(1.8, 3.2) * (1.15 - z / 12)
for i in range(18):                                        # flat base
    el = mb.elements.new()
    el.type = "ELLIPSOID"
    el.co = (crnd.uniform(-6, 6), crnd.uniform(-2, 2), -0.6)
    el.size_x, el.size_y, el.size_z = 2.4, 1.6, 0.7
    el.radius = 2.0
mb.resolution = 0.16
cloud = bpy.data.objects.new("Cloud", mb)
cloud.location = Vector(T.CLOUD) - Vector((0, 0, 2.5))
col.objects.link(cloud)
bpy.context.view_layer.objects.active = cloud
cloud.select_set(True)
bpy.ops.object.convert(target="MESH")
cloud = bpy.context.view_layer.objects.active
cloud.data.materials.clear()
cloud.data.materials.append(cloud_m)
tex = bpy.data.textures.new("Puffs", "CLOUDS")
tex.noise_scale = 0.9
tex.noise_depth = 3
disp = cloud.modifiers.new("Puffs", "DISPLACE")
disp.texture = tex
disp.strength = 0.55
disp.mid_level = 0.45
for poly in cloud.data.polygons:
    poly.use_smooth = True
sky_set.append(cloud)

# small distant clouds for depth
for k, (bx, by, bz, sc) in enumerate(((-90, 260, 55, 0.9), (70, 320, 70, 1.2), (160, 220, 48, 0.7),
                                       (-170, 340, 80, 1.4), (20, 420, 95, 1.6), (-40, 180, 40, 0.6))):
    mb2 = bpy.data.metaballs.new(f"FarMeta{k}")
    mb2.resolution = 0.5
    r2 = random.Random(30 + k)
    for i in range(16):
        el = mb2.elements.new()
        a_ = r2.uniform(0, 6.28)
        rr = 6.0 * math.sqrt(r2.random())
        el.co = (rr * math.cos(a_), 0.5 * rr * math.sin(a_), r2.uniform(0, 3.5 * (1 - rr / 7)))
        el.radius = r2.uniform(2.0, 3.0)
    fo = bpy.data.objects.new(f"FarCloud{k}", mb2)
    fo.location = (bx, by, bz)
    fo.scale = (sc, sc, sc)
    col.objects.link(fo)
    bpy.context.view_layer.objects.active = fo
    fo.select_set(True)
    bpy.ops.object.convert(target="MESH")
    fo = bpy.context.view_layer.objects.active
    fo.data.materials.clear()
    fo.data.materials.append(cloud_m)
    for poly in fo.data.polygons:
        poly.use_smooth = True
    sky_set.append(fo)

# giant crane scale above the cloud: hook, dial housing, face, ticks, needle, cables
brass_m, _ = pmat("Brass", (0.82, 0.58, 0.26), rough=0.25, metal=1.0)
steel_m, _ = pmat("Steel", (0.6, 0.62, 0.65), rough=0.3, metal=1.0)
face_m, _ = pmat("DialFace", (0.95, 0.94, 0.9), rough=0.4, emit=(1, 1, 1), strength=0.15)
ink_m, _ = pmat("DialInk", (0.03, 0.03, 0.04), rough=0.5)
needle_m, _ = pmat("Needle", (0.9, 0.12, 0.08), rough=0.35)
D = Vector(T.DIAL)
b = Builder()
cylinder(b, D + Vector((0, 0.35, 0)), D + Vector((0, -0.35, 0)), 3.0, seg=96)           # housing
dial_house = b.build("DialHousing", brass_m)
b = Builder()
cylinder(b, D + Vector((0, -0.36, 0)), D + Vector((0, -0.38, 0)), 2.6, seg=96)
dial_face = b.build("DialFace", face_m)
b = Builder()
for k in range(31):                                          # ticks over 300 degrees
    ang = math.radians(-150 + 10 * k)
    big = k % 5 == 0
    r0, r1 = (1.95 if big else 2.2), 2.45
    p0 = D + Vector((r0 * math.sin(ang), -0.39, r0 * math.cos(ang)))
    p1 = D + Vector((r1 * math.sin(ang), -0.39, r1 * math.cos(ang)))
    cylinder(b, p0, p1, 0.06 if big else 0.035, seg=6)
ticks = b.build("Ticks", ink_m, smooth=False)
FONT = bpy.data.fonts.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viral-hooks", "fonts",
                                        "Montserrat-ExtraBold.otf"))
dial_labels = []
for k, (txt, size) in enumerate([(f"{v:,}", 0.38) for v in range(0, 1400, 200)] + [("×1000 LB", 0.34)]):
    cu = bpy.data.curves.new(f"DialText{k}", "FONT")
    cu.body, cu.font, cu.size = txt, FONT, size
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    o = bpy.data.objects.new(f"DialText{k}", cu)
    if k < 7:
        ang = math.radians(-150 + 50 * k)
        o.location = D + Vector((1.55 * math.sin(ang), -0.4, 1.55 * math.cos(ang)))
    else:
        o.location = D + Vector((0, -0.4, -1.05))
    o.rotation_euler = (math.pi / 2, 0, 0)
    o.data.materials.append(ink_m)
    col.objects.link(o)
    dial_labels.append(o)
b = Builder()
cylinder(b, (0, 0, -0.35), (0, 0, 2.15), 0.07, seg=8)
b.sphere((0, 0, 0), (0.22, 0.12, 0.22))
needle = b.build("Needle", needle_m)
needle.location = D + Vector((0, -0.45, 0))
b = Builder()
cylinder(b, D + Vector((0, 0, 3.0)), D + Vector((0, 0, 60.0)), 0.12, seg=12)              # cable up
cylinder(b, D - Vector((0, 0, 3.0)), Vector(T.HOOK) + Vector((0, 0, 1.6)), 0.14, seg=12)  # shank
hook_parts = b.build("Cable", steel_m)
bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.22, major_segments=48, minor_segments=12,
                                 location=Vector(T.HOOK) + Vector((0, 0, 0.4)), rotation=(math.pi / 2, 0, 0))
hook = bpy.context.active_object
hook.data.materials.append(steel_m)
sky_set += [dial_house, dial_face, ticks, needle, hook_parts, hook] + dial_labels

# herd of 100 porcelain elephants under the cloud
porcelain_m, _ = pmat("Porcelain", (0.36, 0.36, 0.39), rough=0.35, coat=0.4)


def elephant(b, m):
    """Toy elephant ~3 units long, feet at z=0, facing -y."""
    parts = [((0, 0, 1.75), (1.0, 1.45, 0.95), (0, 0, 0)),             # body
             ((0, -1.55, 2.25), (0.72, 0.68, 0.72), (0, 0, 0)),          # head
             ((-0.72, -1.25, 2.3), (0.12, 0.6, 0.7), (0, 0, 0.25)),      # ears
             ((0.72, -1.25, 2.3), (0.12, 0.6, 0.7), (0, 0, -0.25))]
    for i in range(5):                                                   # trunk
        u = i / 4
        parts.append(((0, -2.05 - 0.15 * u, 1.85 - 0.45 * u - 0.1 * u * u), (0.24 - 0.08 * u,) * 3, (0, 0, 0)))
    for sx, sy in ((-0.55, -0.75), (0.55, -0.75), (-0.55, 0.75), (0.55, 0.75)):   # legs
        parts.append(((sx, sy, 0.6), (0.33, 0.33, 0.75), (0, 0, 0)))
    for loc, sc, rot in parts:
        b.add(SPH_V, SPH_F, m @ Matrix.Translation(loc) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*sc, 1)))


b = Builder()
elephant(b, Matrix())
ele_mesh = b.build("ElephantMesh", porcelain_m)
ele_mesh.hide_render = True
hrnd = random.Random(4)
herd = []
for ix in range(10):
    for iy in range(10):
        x = (ix - 4.5) * 4.2 + hrnd.uniform(-0.6, 0.6)
        y = (iy - 4.5) * 5.0 + hrnd.uniform(-0.6, 0.6)
        o = bpy.data.objects.new(f"Elephant{ix}{iy}", ele_mesh.data)
        o.location = (x, y, -1.0)
        o.rotation_euler = (0, 0, hrnd.uniform(-0.35, 0.35))
        col.objects.link(o)
        herd.append((o, math.hypot(x, y + 30)))            # rank: front rows (towards camera) first
herd.sort(key=lambda e: e[1])
sky_set += [o for o, _ in herd]

# glass air-cube around the cloud: glowing edges + faint glass faces
edge_m, EDGE_A = glow_mat("CubeEdges", (0.55, 0.85, 1.0), 6.0, alpha=0.0)
glass_m, GLASS_A = glow_mat("CubeGlass", (0.6, 0.8, 1.0), 0.15, alpha=0.0)
C = Vector(T.CLOUD) + Vector((0, 0, 1.0))
hs = 10.0
corners = [C + Vector((sx * hs, sy * hs, sz * hs)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
edges = [(a, b2) for a in range(8) for b2 in range(a + 1, 8) if bin(a ^ b2).count("1") == 1]
edge_objs = []
for k, (a, b2) in enumerate(edges):
    bb = Builder()
    L_ = (corners[b2] - corners[a]).length
    cylinder(bb, (0, 0, 0), (0, 0, L_), 0.09, seg=8)
    o = bb.build(f"CubeEdge{k}", edge_m)
    o.location = corners[a]
    o.rotation_euler = (corners[b2] - corners[a]).to_track_quat("Z", "Y").to_euler()
    edge_objs.append(o)
    sky_set.append(o)
bpy.ops.mesh.primitive_cube_add(size=2 * hs, location=C)
glass = bpy.context.active_object
glass.data.materials.append(glass_m)
glass.visible_shadow = False
sky_set.append(glass)

# feather (vane from a curved strip + quill)
feather_m, _ = pmat("Feather", (0.98, 0.95, 0.9), rough=0.6, emit=(1.0, 0.97, 0.92), strength=0.35)
fv, ff = [], []
N = 24
for i in range(N + 1):
    u = i / N
    w = 0.55 * math.sin(math.pi * min(1.0, u * 1.05)) ** 0.7
    yy = u * 3.2
    bend = 0.25 * u * u
    fv += [(-w, yy, bend), (0.0, yy, bend + 0.03), (w * 0.85, yy, bend)]
for i in range(N):
    a, c2 = 3 * i, 3 * (i + 1)
    ff += [[a, a + 1, c2 + 1, c2], [a + 1, a + 2, c2 + 2, c2 + 1]]
feather = obj_from("Feather", fv, ff, feather_m)
feather.scale = (2.2, 2.2, 2.2)
quill_m, _ = pmat("Quill", (0.75, 0.68, 0.58), rough=0.4)
bq = Builder()
cylinder(bq, (0, -0.55, 0.0), (0, 3.25, 0.29), 0.035, seg=10)
quill = bq.build("Quill", quill_m)
quill.parent = feather
feather.data.materials[0].use_backface_culling = False
sky_set.append(feather)

# ================================================================= drops set (inside the cloud)
drops_set = []
fog_m, nt_f, out_f = new_mat("CloudInside")
tcf = node(nt_f, "ShaderNodeTexCoord")
sepf = nt_f.nodes.new("ShaderNodeSeparateXYZ")
nt_f.links.new(tcf.outputs["Generated"], sepf.inputs[0])
crf = ramp(nt_f, [(0.3, (0.42, 0.52, 0.68)), (0.55, (0.78, 0.84, 0.92)), (0.75, (1.0, 0.96, 0.88))])
nt_f.links.new(sepf.outputs["Z"], crf.inputs[0])
emf = node(nt_f, "ShaderNodeEmission", Strength=0.9)
nt_f.links.new(crf.outputs[0], emf.inputs["Color"])
nt_f.links.new(emf.outputs[0], out_f.inputs[0])
bpy.ops.mesh.primitive_uv_sphere_add(radius=40, location=T.DROPS)
fog = bpy.context.active_object
fog.data.materials.append(fog_m)
drops_set.append(fog)
drop_m, _ = pmat("Droplet", (0.85, 0.93, 1.0), rough=0.0, transmission=1.0, ior=1.33)
b = Builder()
drnd = random.Random(9)
DROP_LIST = []
for i in range(520):
    p = (drnd.uniform(-3.2, 3.2), drnd.uniform(-1.0, 6.0), drnd.uniform(-3.0, 3.6))
    r = drnd.uniform(0.04, 0.12)
    DROP_LIST.append((p, r, drnd.uniform(0, 6.28)))
drop_objs = []
for k in range(4):                                  # 4 groups so they can bob with different phases
    bb = Builder()
    for p, r, ph in DROP_LIST[k::4]:
        bb.sphere(Vector(T.DROPS) + Vector(p), (r, r, r))
    o = bb.build(f"Drops{k}", drop_m)
    drop_objs.append(o)
    drops_set.append(o)
air_m, AIR_A = glow_mat("WarmAir", (1.0, 0.62, 0.3), 3.0, alpha=0.0)
streaks = []
for k in range(14):
    x, y = drnd.uniform(-2.6, 2.6), drnd.uniform(0.0, 4.5)
    cu = bpy.data.curves.new(f"Streak{k}", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.022
    sp = cu.splines.new("POLY")
    pts = [(0.12 * math.sin(j * 0.6 + k), 0, j * 0.18) for j in range(12)]
    sp.points.add(len(pts) - 1)
    for pp, c3 in zip(sp.points, pts):
        pp.co = (*c3, 1)
    o = bpy.data.objects.new(f"Streak{k}", cu)
    o.data.materials.append(air_m)
    col.objects.link(o)
    streaks.append((o, x, y, drnd.uniform(0, 1)))
    drops_set.append(o)
fill = bpy.data.lights.new("DropKey", "AREA")
fill.energy, fill.size, fill.color = 2500, 1.5, (1.0, 0.95, 0.85)
fill_o = bpy.data.objects.new("DropKey", fill)
fill_o.location = Vector(T.DROPS) + Vector((3, -4, 4))
fill_o.rotation_euler = Vector((3, -4, 4)).to_track_quat("Z", "Y").to_euler()
col.objects.link(fill_o)
drops_set.append(fill_o)

# ================================================================= camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.sensor_fit = "AUTO"
cam_d.sensor_width = 36
cam_d.clip_start = 0.01
cam_d.clip_end = 2000
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


prev_q = None
for f in range(T.NFRAMES):
    t = f / T.FPS
    CUR[0] = f
    st = T.shot_set(t)
    for o in sky_set:
        key(o, "hide_render", st != "sky")
    for o in drops_set:
        key(o, "hide_render", st != "drops")
    # cloud gently breathing, needle, cube, feather
    key(cloud, "rotation_euler", (0, 0, 0.02 * math.sin(t * 0.4)))
    key(cloud, "location", Vector(T.CLOUD) - Vector((0, 0, 2.5 - T.cloud_dz(t))))
    for rank, (o, _) in enumerate(herd):
        sc = T.herd_scale(t, rank)
        key(o, "scale", (max(sc, 1e-3),) * 3)
        key(o, "hide_render", st != "sky" or sc < 0.01)
    for k, o in enumerate(edge_objs):
        g = T.edge_draw(t, k, len(edge_objs))
        key(o, "scale", (1, 1, max(g, 1e-3)))
        key(o, "hide_render", st != "sky" or g < 0.01)
    key(needle, "rotation_euler", (0, T.needle(t), 0))
    cd = T.cube_draw(t)
    key_socket(EDGE_A, 1.0)
    key_socket(GLASS_A, 0.18 * cd)
    key(feather, "hide_render", T.shot_index(t) != len(T.SHOTS) - 1)
    key(quill, "hide_render", T.shot_index(t) != len(T.SHOTS) - 1)
    fp, fr = T.feather_pos(t)
    key(feather, "location", fp)
    key(feather, "rotation_euler", fr)
    # droplets bob, warm air rises
    for k, o in enumerate(drop_objs):
        key(o, "location", (0.02 * math.sin(t * 1.3 + k), 0, 0.06 * math.sin(t * 0.9 + k * 1.7) + 0.05 * t))
    aa = T.clamp((t - T.L["light"][0]) / 0.4)
    key_socket(AIR_A, 0.9 * aa)
    for o, x, y, ph in streaks:
        cyc = (t * 0.9 + ph * 4) % 4.0
        z = cyc - 2.6
        env = math.sin(math.pi * cyc / 4.0) ** 0.6          # grows in at the bottom, shrinks out at the top
        key(o, "location", Vector(T.DROPS) + Vector((x, y, z)))
        key(o, "scale", (max(env, 1e-3),) * 3)
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
    fp_ = {"dial": Vector(T.DIAL), "drop": Vector(T.DROPS) + Vector((0, 0, 0.3)),
           "feather": Vector(T.feather_pos(t)[0])}.get(focus, Vector(tgt))
    cam_d.dof.focus_distance = (Vector(loc) - fp_).length
    cam_d.dof.keyframe_insert("focus_distance", frame=f)

for idb in list(bpy.data.objects) + list(bpy.data.materials) + list(bpy.data.cameras):
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
r.use_motion_blur = False              # no motion blur at all: every frame is a clean, sharp image
r.use_persistent_data = False
c = scene.cycles
c.device = "CPU"
c.use_adaptive_sampling = True
c.adaptive_threshold = 0.05
c.use_denoising = True
c.max_bounces = 6
c.transparent_max_bounces = 8
c.transmission_bounces = 6
c.caustics_reflective = False
c.caustics_refractive = False
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
SPP = {"sky": 8, "drops": 12}
proj_path = os.path.join(OUT, "projections.json")
proj = json.load(open(proj_path)) if os.path.exists(proj_path) else {}
for f in FRAMES:
    t = f / T.FPS
    scene.frame_set(f)
    c.samples = max(4, int(SPP[T.shot_set(t)] * QUALITY))
    bpy.context.view_layer.update()
    pts = {"cloud": T.CLOUD, "dial": T.DIAL, "herd": (0, 0, 2.5)}
    proj[str(f)] = {k: [round(v, 4) for v in (lambda w: (w.x, 1 - w.y, w.z))(world_to_camera_view(scene, cam, Vector(p)))]
                    for k, p in pts.items()}
    path = os.path.join(OUT, f"f_{f:04d}.png")
    if not os.path.exists(path):
        r.filepath = path
        bpy.ops.render.render(write_still=True)
        print(f"rendered {f} ({T.shot_set(t)})", flush=True)
json.dump(proj, open(proj_path, "w"))
print("done")
