"""Builds the 'hole through the Earth' scene in Blender and renders every frame (Cycles).

Usage:  python3 blender_scene.py <frames_dir> [--frames 0,90,450] [--res 720x1280] [--samples 12]
Writes <frames_dir>/f_0000.png ... and <frames_dir>/projections.json (screen positions for overlays).
"""
import json
import math
import os
import sys

import bpy  # noqa: I001  (bpy must be imported before bmesh)
import bmesh
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timeline as TL  # noqa: E402

args = sys.argv[1:]
OUT = args[0]
FRAMES = list(range(TL.NFRAMES))
RES = (720, 1280)
SAMPLES = 12
if "--frames" in args:
    FRAMES = [int(v) for v in args[args.index("--frames") + 1].split(",")]
if "--res" in args:
    RES = tuple(int(v) for v in args[args.index("--res") + 1].split("x"))
THREADS = int(args[args.index("--threads") + 1]) if "--threads" in args else 0
if "--samples" in args:
    SAMPLES = int(args[args.index("--samples") + 1])
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


# ---------------------------------------------------------------- node helpers
def mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    return m, nt, nt.nodes["Material Output"]


def principled(nt, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = strength
    return p


def ramp(nt, stops, interp="LINEAR"):
    r = nt.nodes.new("ShaderNodeValToRGB")
    cr = r.color_ramp
    cr.interpolation = interp
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position = stops[0][0]
    cr.elements[0].color = (*stops[0][1], 1)
    for pos, col in stops[1:]:
        e = cr.elements.new(pos)
        e.color = (*col, 1)
    return r


def simple_mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m, nt, out = mat(name)
    p = principled(nt, color, rough, metal, emit, strength)
    nt.links.new(p.outputs[0], out.inputs[0])
    return m


# ---------------------------------------------------------------- materials
def earth_surface_mat():
    m, nt, out = mat("EarthSurface")
    L = nt.links
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.2
    noise.inputs["Detail"].default_value = 8
    L.new(tc.outputs["Object"], noise.inputs["Vector"])
    land = ramp(nt, [(0.0, (0.02, 0.12, 0.42)), (0.52, (0.03, 0.22, 0.55)), (0.535, (0.75, 0.68, 0.45)),
                     (0.56, (0.12, 0.42, 0.10)), (0.75, (0.30, 0.38, 0.12))])
    L.new(noise.outputs["Fac"], land.inputs[0])
    # polar ice
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    ab = nt.nodes.new("ShaderNodeMath")
    ab.operation = "ABSOLUTE"
    L.new(sep.outputs["Z"], ab.inputs[0])
    ice = ramp(nt, [(0.0, (0, 0, 0)), (0.90, (0, 0, 0)), (0.93, (1, 1, 1))])
    L.new(ab.outputs[0], ice.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L.new(ice.outputs[0], mix.inputs["Factor"])
    L.new(land.outputs[0], mix.inputs["A"])
    mix.inputs["B"].default_value = (0.92, 0.95, 1.0, 1)
    p = principled(nt, (1, 1, 1), rough=0.55)
    L.new(mix.outputs["Result"], p.inputs["Base Color"])
    L.new(p.outputs[0], out.inputs[0])
    return m


def interior_mat():
    """Radial layers: inner core / outer core / mantle / crust, with glow."""
    m, nt, out = mat("Interior")
    L = nt.links
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9
    noise.inputs["Detail"].default_value = 6
    L.new(tc.outputs["Object"], noise.inputs["Vector"])
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    L.new(tc.outputs["Object"], ln.inputs[0])
    wob = nt.nodes.new("ShaderNodeMath")
    wob.operation = "MULTIPLY_ADD"
    wob.inputs[1].default_value = 0.025
    wob.inputs[2].default_value = -0.0125
    L.new(noise.outputs["Fac"], wob.inputs[0])
    r = nt.nodes.new("ShaderNodeMath")
    r.operation = "ADD"
    L.new(ln.outputs["Value"], r.inputs[0])
    L.new(wob.outputs[0], r.inputs[1])
    col = ramp(nt, [(0.0, (1.0, 0.85, 0.35)), (0.19, (1.0, 0.32, 0.02)), (0.55, (0.55, 0.08, 0.02)),
                    (0.80, (0.48, 0.10, 0.03)), (0.965, (0.42, 0.30, 0.20))], interp="CONSTANT")
    L.new(r.outputs[0], col.inputs[0])
    # subtle gradient inside each band
    grad = ramp(nt, [(0.0, (1.0, 1.0, 1.0)), (1.0, (0.55, 0.55, 0.55))])
    L.new(ln.outputs["Value"], grad.inputs[0])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 0.3
    L.new(col.outputs[0], mul.inputs["A"])
    L.new(grad.outputs[0], mul.inputs["B"])
    strength = ramp(nt, [(0.0, (2.2, 2.2, 2.2)), (0.19, (0.9, 0.9, 0.9)), (0.55, (0.32, 0.32, 0.32)),
                         (0.96, (0.0, 0.0, 0.0))], interp="CONSTANT")
    L.new(r.outputs[0], strength.inputs[0])
    p = principled(nt, (1, 1, 1), rough=0.8)
    L.new(mul.outputs["Result"], p.inputs["Base Color"])
    L.new(mul.outputs["Result"], p.inputs["Emission Color"])
    L.new(strength.outputs[0], p.inputs["Emission Strength"])
    L.new(p.outputs[0], out.inputs[0])
    return m


def atmosphere_mat():
    m, nt, out = mat("Atmosphere")
    L = nt.links
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.25
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 2.0
    L.new(lw.outputs["Facing"], pw.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.25, 0.55, 1.0, 1)
    em.inputs["Strength"].default_value = 1.6
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    L.new(pw.outputs[0], mix.inputs[0])
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs[0])
    m.blend_method = "BLEND" if hasattr(m, "blend_method") else None
    return m


def tunnel_mat():
    m, nt, out = mat("Tunnel")
    L = nt.links
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.15
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.35, 0.75, 1.0, 1)
    em.inputs["Strength"].default_value = 3.0
    dark = nt.nodes.new("ShaderNodeBsdfPrincipled")
    dark.inputs["Base Color"].default_value = (0.01, 0.012, 0.02, 1)
    dark.inputs["Roughness"].default_value = 0.25
    mix = nt.nodes.new("ShaderNodeMixShader")
    L.new(lw.outputs["Fresnel"], mix.inputs[0])
    L.new(dark.outputs[0], mix.inputs[1])
    L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs[0])
    return m


# ---------------------------------------------------------------- geometry
def cut_sphere(name, radius, mats, segs=128, rings=64, caps=True):
    """Sphere with the (x>0, y>0) wedge removed; cut faces get material index 1."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=radius)
    for no in ((1, 0, 0), (0, 1, 0)):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, 0), plane_no=no)
    bad = [f for f in bm.faces if f.calc_center_median().x > 1e-6 and f.calc_center_median().y > 1e-6]
    bmesh.ops.delete(bm, geom=bad, context="FACES")
    for f in bm.faces:
        f.smooth = True
    if caps:
        for axis in ("x", "y"):
            res = bmesh.ops.create_circle(bm, cap_ends=True, radius=radius, segments=segs)
            vs = res["verts"]
            # circle lies in XY; rotate into the cut plane
            for v in vs:
                x, y, _ = v.co
                v.co = (0.0, x, y) if axis == "x" else (x, 0.0, y)
            faces = list({f for v in vs for f in v.link_faces})
            no = (0, 1, 0) if axis == "x" else (1, 0, 0)
            geom = vs + list({e for v in vs for e in v.link_edges}) + faces
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, 0), plane_no=no, clear_inner=True)
            for f in bm.faces:
                c = f.calc_center_median()
                if (axis == "x" and abs(c.x) < 1e-7 and f.normal.length > 0) or \
                   (axis == "y" and abs(c.y) < 1e-7 and f.normal.length > 0):
                    if abs(f.normal.x if axis == "x" else f.normal.y) > 0.99:
                        f.material_index = 1
                        f.smooth = False
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f.material_index == 0])
    for f in bm.faces:
        if f.material_index == 1:
            want = (1, 0, 0) if abs(f.normal.x) > 0.99 else (0, 1, 0)
            if f.normal.dot(want) < 0:
                f.normal_flip()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    for m in mats:
        ob.data.materials.append(m)
    scene.collection.objects.link(ob)
    return ob


earth = cut_sphere("Earth", TL.R, [earth_surface_mat(), interior_mat()])
atm_m = atmosphere_mat()
atm = cut_sphere("Atmosphere", TL.R * 1.02, [atm_m, atm_m], segs=96, rings=48, caps=False)
atm.visible_shadow = False

bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.015, depth=2 * TL.R + 0.006, location=(0, 0, 0))
tunnel = bpy.context.active_object
tunnel.name = "Tunnel"
tunnel.data.materials.append(tunnel_mat())
bpy.ops.object.shade_smooth()

# person: an empty with children (body, head, eyes, backpack light)
person = bpy.data.objects.new("Person", None)
scene.collection.objects.link(person)
suit = simple_mat("Suit", (1.0, 0.32, 0.05), rough=0.35)
skin = simple_mat("Skin", (0.95, 0.70, 0.55), rough=0.5)
black = simple_mat("Eye", (0.01, 0.01, 0.01), rough=0.1)
visor = simple_mat("Visor", (0.6, 0.9, 1.0), rough=0.05, emit=(0.4, 0.8, 1.0), strength=0.6)


def part(prim, mat_, loc, scale, **kw):
    getattr(bpy.ops.mesh, prim)(location=loc, **kw)
    o = bpy.context.active_object
    o.scale = scale
    o.data.materials.append(mat_)
    bpy.ops.object.shade_smooth()
    o.parent = person
    return o


h = TL.H
part("primitive_uv_sphere_add", suit, (0, 0, -h * 0.12), (0.0135, 0.0135, 0.022), segments=32, ring_count=16)
part("primitive_uv_sphere_add", skin, (0, 0, h * 0.28), (0.0115, 0.0115, 0.0115), segments=32, ring_count=16)
part("primitive_uv_sphere_add", suit, (0, 0, h * 0.30), (0.0128, 0.0128, 0.0128), segments=32, ring_count=16)
part("primitive_uv_sphere_add", visor, (0, 0.0055, h * 0.29), (0.0085, 0.0075, 0.0065), segments=24, ring_count=12)
for sx in (-1, 1):
    part("primitive_uv_sphere_add", suit, (sx * 0.0075, 0, -h * 0.40), (0.0055, 0.0055, 0.011),
         segments=16, ring_count=8)                       # legs
    part("primitive_uv_sphere_add", suit, (sx * 0.016, 0, -h * 0.02), (0.0045, 0.0045, 0.013),
         segments=16, ring_count=8, rotation=(0, sx * 0.5, 0))  # arms
glow = bpy.data.lights.new("PersonGlow", "POINT")
glow.energy = 0.25
glow.color = (1.0, 0.8, 0.55)
glow.shadow_soft_size = 0.01
gl = bpy.data.objects.new("PersonGlow", glow)
gl.parent = person
gl.location = (0, 0.04, 0.0)
scene.collection.objects.link(gl)

# lights
sun = bpy.data.lights.new("Sun", "SUN")
sun.energy = 3.2
sun.angle = math.radians(2)
sun_o = bpy.data.objects.new("Sun", sun)
sun_o.rotation_euler = Vector((0.15, 1.0, 0.75)).to_track_quat("Z", "Y").to_euler()
scene.collection.objects.link(sun_o)
rim = bpy.data.lights.new("Rim", "SUN")
rim.energy = 1.2
rim.color = (0.5, 0.7, 1.0)
rim_o = bpy.data.objects.new("Rim", rim)
rim_o.rotation_euler = Vector((-1.0, -0.3, 0.4)).to_track_quat("Z", "Y").to_euler()
scene.collection.objects.link(rim_o)

# world: deep space + stars
world = bpy.data.worlds.new("Space")
scene.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    if n.type != "OUTPUT_WORLD":
        wn.nodes.remove(n)
tc = wn.nodes.new("ShaderNodeTexCoord")
vor = wn.nodes.new("ShaderNodeTexVoronoi")
vor.inputs["Scale"].default_value = 220
wn.links.new(tc.outputs["Generated"], vor.inputs["Vector"])
star = ramp(wn, [(0.0, (1, 1, 1)), (0.035, (0, 0, 0))])
wn.links.new(vor.outputs["Distance"], star.inputs[0])
grad = wn.nodes.new("ShaderNodeSeparateXYZ")
wn.links.new(tc.outputs["Generated"], grad.inputs[0])
sky = ramp(wn, [(0.0, (0.004, 0.006, 0.02)), (1.0, (0.012, 0.02, 0.06))])
wn.links.new(grad.outputs["Z"], sky.inputs[0])
add = wn.nodes.new("ShaderNodeMix")
add.data_type = "RGBA"
add.blend_type = "ADD"
add.inputs["Factor"].default_value = 1.0
wn.links.new(sky.outputs[0], add.inputs["A"])
wn.links.new(star.outputs[0], add.inputs["B"])
bg = wn.nodes.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 1.0
wn.links.new(add.outputs["Result"], bg.inputs[0])
wn.links.new(bg.outputs[0], wn.nodes["World Output"].inputs[0])

# camera
cam_d = bpy.data.cameras.new("Cam")
cam_d.lens = 30
cam_d.sensor_fit = "AUTO"
cam_d.sensor_width = 36
cam_d.clip_start = 0.005
cam = bpy.data.objects.new("Cam", cam_d)
scene.collection.objects.link(cam)
scene.camera = cam
target = bpy.data.objects.new("CamTarget", None)
scene.collection.objects.link(target)
tt = cam.constraints.new("TRACK_TO")
tt.target = target
tt.track_axis = "TRACK_NEGATIVE_Z"
tt.up_axis = "UP_Y"

# render settings
r = scene.render
r.engine = "CYCLES"
r.resolution_x, r.resolution_y = RES
r.resolution_percentage = 100
r.image_settings.file_format = "PNG"
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.05
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 4
scene.cycles.transparent_max_bounces = 4
r.use_persistent_data = False  # long runs with persistent data rendered the astronaut black
if THREADS:
    r.threads_mode = "FIXED"
    r.threads = THREADS
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
except Exception:
    pass

# ---------------------------------------------------------------- per-frame
proj_path = os.path.join(OUT, "projections.json")
proj = json.load(open(proj_path)) if os.path.exists(proj_path) else {}


def to_screen(p):
    v = world_to_camera_view(scene, cam, Vector(p))
    return [round(v.x, 5), round(1 - v.y, 5), round(v.z, 4)]


for f in FRAMES:
    t = f / TL.FPS
    (px, py, pz), rx, rz = TL.person(t)
    person.location = (px, py, pz)
    person.rotation_euler = (rx, 0, rz)
    cp, ct = TL.camera(t)
    cam.location = cp
    target.location = ct
    bpy.context.view_layer.update()
    entry = {"person": to_screen((px, py, pz))}
    for name, p, *_ in TL.LABELS:
        entry[name] = to_screen(p)
    proj[str(f)] = entry
    path = os.path.join(OUT, f"f_{f:04d}.png")
    if not os.path.exists(path):
        r.filepath = path
        bpy.ops.render.render(write_still=True)
        print(f"rendered frame {f}", flush=True)
    if f % 30 == 0:
        json.dump(proj, open(proj_path, "w"))
json.dump(proj, open(proj_path, "w"))
print("done")
