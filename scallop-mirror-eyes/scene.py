"""Original Cycles reconstruction of a scallop mantle and the crystal mirror in its eye."""
import math, os, random
from pathlib import Path
import bpy
from mathutils import Vector
from math import sin, cos, pi
rng=random.Random(81031)
out=Path(os.environ['SCALLOP_ASSETS']);out.mkdir(exist_ok=True,parents=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene
s.render.engine='CYCLES';s.cycles.samples=12;s.cycles.use_denoising=True
s.cycles.adaptive_threshold=.08;s.cycles.max_bounces=4
s.render.threads_mode='FIXED';s.render.threads=4
s.render.resolution_x=1280;s.render.resolution_y=2280;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.use_motion_blur=False
s.world=bpy.data.worlds.new('Filtered seawater');s.world.use_nodes=True
bg=s.world.node_tree.nodes.get('Background');bg.inputs[0].default_value=(.13,.23,.25,1);bg.inputs[1].default_value=.34
s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast';s.view_settings.exposure=-.12
def material(name,color,rough=.38,metal=0,noise=0,colors=None):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    tree=m.node_tree;bs=tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metal
    if noise:
        n=tree.nodes.new('ShaderNodeTexNoise');n.inputs['Scale'].default_value=noise;n.inputs['Detail'].default_value=3.5
        b=tree.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.19;b.inputs['Distance'].default_value=.018
        tree.links.new(n.outputs['Fac'],b.inputs['Height']);tree.links.new(b.outputs['Normal'],bs.inputs['Normal'])
        if colors:
            ramp=tree.nodes.new('ShaderNodeValToRGB');r=ramp.color_ramp;r.elements[0].position=.19;r.elements[0].color=(*colors[0],1);r.elements[1].position=.82;r.elements[1].color=(*colors[1],1)
            tree.links.new(n.outputs['Fac'],ramp.inputs[0]);tree.links.new(ramp.outputs[0],bs.inputs['Base Color'])
    return m
def mesh(name,verts,faces,mats,ids=None,smooth=True):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(name,me);s.collection.objects.link(o)
    for m in mats:me.materials.append(m)
    for j,p in enumerate(me.polygons):p.use_smooth=smooth;p.material_index=ids[j] if ids else 0
    return o
def ball(name,pos,scale,mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=28,ring_count=18,location=pos);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(mat)
    for p in o.data.polygons:p.use_smooth=True
    return o
def tube(name,pts,radii,mat):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=3;c.bevel_depth=1;c.bevel_resolution=3
    sp=c.splines.new('BEZIER');sp.bezier_points.add(len(pts)-1)
    for p,co,rad in zip(sp.bezier_points,pts,radii):
        p.co=co;p.radius=rad;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
    o=bpy.data.objects.new(name,c);s.collection.objects.link(o);o.data.materials.append(mat);return o
def area(name,pos,power,color,size,target):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.color=color;d.shape='DISK';d.size=size
    o=bpy.data.objects.new(name,d);s.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
def shellpos(a,r,upper):
    ribs=cos(42*a+.18*sin(3*a));edge=1+.013*cos(42*a)
    y=1.00-3.30*r*cos(a)*edge;x=2.56*r*sin(a)*edge
    ridge=.074*(.5+.5*ribs)**2*r**.55
    wave=.009*sin(r*205+1.8*sin(a*5))*r
    if upper:z=.20+.38*r+.52*sin(pi*r)**.82+ridge+wave
    else:z=-.15-.20*r-.29*sin(pi*r)**.85-ridge*.65
    return (x,y,z)
shell=[]
for j,col in enumerate([(.54,.205,.116),(.71,.358,.199),(.61,.274,.158),(.75,.436,.279),(.47,.17,.100)]):
    shell.append(material('Shell mineral '+str(j),col,.44,.04,65,[tuple(c*.69 for c in col),tuple(min(1,c*1.19) for c in col)]))
cream=material('Mother of pearl lip',(.76,.54,.34),.27,.18,48)
for upper in (True,False):
    V=[];F=[];ids=[];na=210;nr=70
    for j in range(nr+1):
        r=.004+.996*j/nr
        for i in range(na+1):V.append(shellpos(-1.23+2.46*i/na,r,upper))
    for j in range(nr):
        for i in range(na):
            ix=j*(na+1)+i;F.append((ix,ix+1,ix+na+2,ix+na+1) if upper else (ix+na+1,ix+na+2,ix+1,ix))
            a=-1.23+2.46*(i+.5)/na;r=(j+.5)/nr
            v=.42*sin(20*a+.25*sin(12*r))+.34*sin(15*r+.8*sin(5*a))+.22*cos(30*r-6*a)
            ids.append(5 if r>.983 else (0 if v<-.37 else 1 if v>.58 else 2 if v<.15 else 3))
    mesh('Fluted upper valve' if upper else 'Lower valve',V,F,shell+[cream],ids)
    edge=[shellpos(-1.23+2.46*i/120,1,upper) for i in range(121)]
    tube('Calcified lip',edge,[.020]*len(edge),cream)
flesh=material('Mantle coral',(.53,.186,.105),.35,0,10,[(.37,.095,.054),(.68,.31,.176)])
tent=material('Mantle feelers',(.73,.42,.22),.34,0,26)
stem=material('Eye stalk',(.46,.22,.145),.32)
azure=material('Cobalt eye',(.009,.115,.27),.19,.36)
iris=material('Iridescent iris',(.016,.42,.66),.22,.40)
pupil=material('Optical aperture',(.002,.009,.018),.095,.16)
edge=[]
for i in range(115):
    a=-1.23+2.46*i/114;x,y,_=shellpos(a,.970,True);edge.append((x,y,.10+.024*sin(24*a)))
tube('Fleshy mantle beneath shell',edge,[.185]*len(edge),flesh)
ball('Inner mantle',(0,-.29,.055),(2.08,1.84,.29),flesh)
for i in range(97):
    a=-1.23+2.46*i/96;x,y,_=shellpos(a,.972,True);v=Vector((.91*sin(a),-cos(a),0));p=Vector((x,y,.12+.035*sin(a*18)))
    length=.15+rng.random()*.22
    tube('Sensory fringe',[p,p+v*.11+Vector((0,0,.025)),p+v*length+Vector((.016*sin(i),.01,.06*sin(i*2.3)))],[.038,.026,.004],tent)
for i in range(36):
    a=-1.205+2.41*(i+.30)/36;x,y,_=shellpos(a,.979,True);v=Vector((.87*sin(a),-cos(a),0)).normalized()
    base=Vector((x,y,.125));pos=base+v*(.15+.029*sin(i*9))+Vector((0,0,.10+.024*cos(i*2.5)))
    tube('Short eye stalk',[base,pos-v*.045,pos],[.055,.042,.049],stem)
    ball('Blue mantle eye',pos,(.068,.063,.067),azure)
    n=(v+Vector((0,0,.54))).normalized()
    for name,dist,sc,ma in [('Azure rim',.045,(.052,.052,.020),iris),('Dark aperture',.058,(.035,.035,.015),pupil)]:
        o=ball(name,pos+n*dist,sc,ma);o.rotation_euler=n.to_track_quat('Z','Y').to_euler()
sand=material('Submerged sand',(.125,.16,.12),.87,0,84,[(.045,.089,.083),(.23,.244,.163)])
bpy.ops.mesh.primitive_plane_add(size=90,location=(0,0,-.65));bpy.context.object.data.materials.append(sand)
stones=[material('Pebble '+str(i),c,.69,0,12) for i,c in enumerate([(.22,.21,.16),(.15,.202,.17),(.30,.25,.16),(.11,.13,.12)])]
for i in range(105):
    x=rng.uniform(-7,7);y=rng.uniform(-6,8)
    if abs(x)<2.1 and -2.25<y<1.3:continue
    r=rng.uniform(.025,.145);o=ball('Worn gravel',(x,y,-.65+r*.23),(r*1.45,r,.66*r),rng.choice(stones));o.rotation_euler.z=rng.uniform(0,pi)
area('Cool surface light',(-3,-3,6),650,(.77,.92,1),4,(0,0,0));area('Warm rake',(3,1,4.1),490,(1,.73,.45),3,(0,0,0));area('Eye catchlight',(-1.1,-4,.85),115,(.65,.88,1),1.0,(0,-2,0))
camd=bpy.data.cameras.new('Macro lens');cam=bpy.data.objects.new('Macro lens',camd);s.collection.objects.link(cam);s.camera=cam
def render(name,pos,target,framing,aperture=0):
    cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    camd.type='ORTHO';camd.ortho_scale=framing;camd.dof.use_dof=False
    s.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
render('animal',(.9,-8.1,4.45),(0,-.47,.16),10.4)
render('mantle',(.53,-5.7,.91),(0,-2.20,.19),3.2)
a=-1.205+2.41*(17+.30)/36;x,y,_=shellpos(a,.979,True)
render('single',(x-.025,y-2.7,.93),(x,y-.15,.23),.89)
# Isolated multilayer crystal mosaic. Each top face is a square tile, with a visible dark joint.
origin=Vector((32,0,0))
tilem=[material('Guanine platelet '+str(i),c,.22,.71) for i,c in enumerate([(.47,.68,.72),(.55,.76,.73),(.36,.57,.63),(.62,.72,.71),(.40,.62,.67)])]
sid=material('Layer edge',(.115,.24,.285),.32,.43)
V=[];F=[];I=[]
for j in range(-15,16):
    for i in range(-15,16):
        x=.206*i;y=.206*j
        if x*x+y*y>8.4:continue
        rot=rng.uniform(-.045,.045);r=.097+rng.uniform(-.002,.003);k=len(V)
        for layer in (0,1):
            for ax,ay in [(-r,-r),(r,-r),(r,r),(-r,r)]:
                xx=x+ax*cos(rot)-ay*sin(rot);yy=y+ax*sin(rot)+ay*cos(rot)
                zz=.10*(x*x+y*y)+.20*x*(xx-x)+.20*y*(yy-y)-.055*(1-layer)
                V.append(tuple(origin+Vector((xx,yy,zz))))
        F.append((k+4,k+5,k+6,k+7));I.append(rng.randrange(5))
        for h in range(4):F.append((k+h,k+(h+1)%4,k+(h+1)%4+4,k+h+4));I.append(5)
obj=mesh('Square platelet mosaic',V,F,tilem+[sid],I,False)
bev=obj.modifiers.new('Crystal edge','BEVEL');bev.width=.006;bev.segments=2
area('Mosaic key',(30,-1,5),780,(.66,.9,1),3,(32,0,0));area('Mosaic glancing rim',(34.5,2,2),480,(1,.74,.45),2,(32,0,.2))
render('crystals',(32.38,-3.7,3.9),(32,.14,.20),4.55)
