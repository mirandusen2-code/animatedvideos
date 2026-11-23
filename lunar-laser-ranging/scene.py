"""Three native Cycles plates: lunar globe, Apollo-style array and a ranging dome."""
import bpy,math,random,os
from pathlib import Path
from mathutils import Vector
from math import sin,cos,pi
rng=random.Random(721)
OUT=Path(os.environ['PLATES']);OUT.mkdir(exist_ok=True,parents=True)
def start(world):
    bpy.ops.wm.read_factory_settings(use_empty=True);s=bpy.context.scene
    s.render.engine='CYCLES';s.cycles.samples=12;s.cycles.use_denoising=True;s.cycles.adaptive_threshold=.075;s.cycles.max_bounces=4
    s.render.resolution_x=1320;s.render.resolution_y=2360;s.render.resolution_percentage=100;s.render.use_motion_blur=False
    s.render.threads_mode='FIXED';s.render.threads=4;s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
    s.world=bpy.data.worlds.new('Environment');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(*world,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.27
    return s
def mat(name,col,rough=.4,metal=0,noise=0):
    m=bpy.data.materials.new(name);m.use_nodes=True;nt=m.node_tree;b=nt.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=(*col,1);b.inputs['Roughness'].default_value=rough;b.inputs['Metallic'].default_value=metal
    if noise:
        n=nt.nodes.new('ShaderNodeTexNoise');n.inputs['Scale'].default_value=noise;n.inputs['Detail'].default_value=4
        ramp=nt.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.24;ramp.color_ramp.elements[0].color=(*[v*.44 for v in col],1);ramp.color_ramp.elements[1].position=.76;ramp.color_ramp.elements[1].color=(*[min(1,v*1.45) for v in col],1)
        bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.23;bump.inputs['Distance'].default_value=.022
        nt.links.new(n.outputs['Fac'],ramp.inputs[0]);nt.links.new(ramp.outputs[0],b.inputs['Base Color']);nt.links.new(n.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs[0],b.inputs['Normal'])
    return m
def mesh(name,V,F,ma):
    me=bpy.data.meshes.new(name);me.from_pydata(V,[],F);me.update();o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o);o.data.materials.append(ma);return o
def box(name,p,dim,m,parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1);o=bpy.context.object;o.name=name;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m);o.parent=parent;o.location=p
    mod=o.modifiers.new('Machined edges','BEVEL');mod.width=min(dim)*.08;mod.segments=2
    return o
def rod(a,b,r,m):
    v=Vector(b)-Vector(a);bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=r,depth=v.length,location=(Vector(a)+Vector(b))/2)
    o=bpy.context.object;o.rotation_euler=v.to_track_quat('Z','Y').to_euler();o.data.materials.append(m)
def sun(pos,power,color):
    d=bpy.data.lights.new('Collimated sunlight','SUN');d.energy=power;d.angle=.034;d.color=color;o=bpy.data.objects.new('Sun',d);bpy.context.collection.objects.link(o);o.rotation_euler=(-Vector(pos)).to_track_quat('-Z','Y').to_euler()
def area(p,target,power,col,size):
    d=bpy.data.lights.new('Fill','AREA');d.energy=power;d.color=col;d.size=size;o=bpy.data.objects.new('Fill',d);bpy.context.collection.objects.link(o);o.location=p;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
def camera(name,p,target,lens):
    s=bpy.context.scene;d=bpy.data.cameras.new('Documentary camera');o=bpy.data.objects.new('View',d);bpy.context.collection.objects.link(o);o.location=p;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.lens=lens;s.camera=o;s.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
def ground(m,terrain,scale):
    V=[];F=[];n=95
    for j in range(n+1):
        for i in range(n+1):
            x=(i/n-.5)*scale;y=(j/n-.5)*scale;V.append((x,y,terrain(x,y)))
    for j in range(n):
        for i in range(n):
            k=j*(n+1)+i;F.append((k,k+1,k+n+2,k+n+1))
    o=mesh('Terrain',V,F,m)
    for p in o.data.polygons:p.use_smooth=True
s=start((.002,.003,.006))
bpy.ops.mesh.primitive_uv_sphere_add(segments=192,ring_count=96,radius=1)
o=bpy.context.object;o.rotation_euler.z=-pi/2
for p in o.data.polygons:p.use_smooth=True
m=mat('LROC global mosaic',(.5,.5,.5),.96)
nt=m.node_tree;tex=nt.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(os.environ['MOON_MAP']);nt.links.new(tex.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color']);o.data.materials.append(m)
sun((-4,-6,3),3.1,(1,.97,.92));camera('moon',(0,-5.6,.16),(0,0,0),51)
s=start((.002,.002,.003))
reg=mat('Lunar regolith',(.21,.20,.185),.94,0,93)
def regz(x,y):
    return .032*sin(1.27*x+.3*y)*cos(.86*y)+.008*sin(x*4+y*3)+max(y-4,0)*.025*(1+.65*sin(x*1.1))
ground(reg,regz,36)
rock=mat('Ejecta',(.24,.23,.21),.9,0,7)
for i in range(110):
    x=rng.uniform(-4,4);y=rng.uniform(-3,7)
    if abs(x)<.85 and abs(y)<.8:continue
    r=rng.uniform(.015,.10);bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=r,location=(x,y,regz(x,y)+.16*r));o=bpy.context.object;o.scale=(1.6,.8,.7);o.rotation_euler=(rng.random(),rng.random(),rng.random()*pi);o.data.materials.append(rock)
gold=mat('Anodized rim',(.60,.48,.29),.3,.65);silver=mat('Mount',(.55,.54,.49),.28,.66);dark=mat('Recesses',(.026,.037,.042),.38,.46)
holder=bpy.data.objects.new('Tilted array',None);bpy.context.collection.objects.link(holder);holder.location=(0,0,.73);holder.rotation_euler.x=math.radians(45)
box('Array chassis',(0,0,0),(1.02,1.02,.095),gold,holder);box('Face',(0,0,.054),(.97,.97,.025),dark,holder)
colors=[mat('Glass facet '+str(i),c,.19,.58) for i,c in enumerate([(.30,.40,.41),(.62,.69,.64),(.113,.19,.20),(.66,.61,.47)])]
for j in range(10):
    for i in range(10):
        x=(i-4.5)*.093;y=(j-4.5)*.093
        bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=.041,depth=.009);o=bpy.context.object;o.parent=holder;o.location=(x,y,.073);o.data.materials.append(silver)
        R=.035;verts=[(x,y,.082)]+[(x+R*cos(h*2*pi/18),y+R*sin(h*2*pi/18),.083) for h in range(18)]
        ob=mesh('Three reflective sectors',verts,[(0,h+1,(h+1)%18+1) for h in range(18)],colors[0]);ob.parent=holder
        for matl in colors[1:]:ob.data.materials.append(matl)
        for h,pol in enumerate(ob.data.polygons):pol.material_index=(h//6+(i//4+j//7))%4
for x in (-.4,.4):
    rod((x,-.38,.02),(x,-.17,.49),.022,silver);rod((x,.46,.02),(x,.21,.87),.022,silver);rod((x,-.38,.03),(x,.46,.03),.021,gold)
sun((-4,-3,4),3.3,(1,.98,.91));area((0,-3,2),(0,0,.6),50,(.8,.91,1),2.5)
camera('array',(1.14,-2.70,1.64),(0,.02,.64),46)
s=start((.031,.059,.109))
ground(mat('Mountain silhouette',(.047,.072,.095),.9,0,34),lambda x,y:.045*sin(x*.9)*cos(y*.45)+max(0,y-3)*(.30+.13*sin(x*1.0)+.12*cos(x*.61)),75)
skin=mat('Painted steel',(.37,.44,.48),.42,.37);rim=mat('Dome ribs',(.18,.25,.29),.33,.54);inside=mat('Open slit',(.012,.019,.027),.62)
bpy.ops.mesh.primitive_cylinder_add(vertices=96,radius=1.0,depth=.91,location=(0,0,.465));bpy.context.object.data.materials.append(skin)
for j in range(32):
    a=2*pi*j/32
    rod((cos(a),sin(a),.03),(cos(a),sin(a),.90),.009,rim)
for i in range(40):
    a=i*2*pi/40;b=(i+1)*2*pi/40;V=[];F=[]
    for j in range(21):
        elev=j/20*pi/2
        for az in (a,b):V.append((1.045*cos(az)*cos(elev),1.045*sin(az)*cos(elev),.93+1.045*sin(elev)))
    for j in range(20):F.append((2*j,2*j+1,2*j+3,2*j+2))
    mesh('Observatory shutter',V,F,inside if i in (29,30,31,32) else (rim if i%6==0 else skin))
sun((-3,-5,2),1.4,(.48,.62,1));area((-1.5,-2,1),(0,0,.8),55,(1,.61,.34),1.4)
camera('station',(2.75,-6.50,2.22),(0,0,1.02),51)
