"""Native Cycles reconstruction of a white-spotted pufferfish and its spawning nest."""
import math, os, random, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from timeline import FPS, DUR, NFRAMES, camera_state, puffer_state, shot
from math import sin, cos, pi
rng=random.Random(527)
root=Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.device='CPU'
sc.cycles.samples=8; sc.cycles.use_adaptive_sampling=True; sc.cycles.adaptive_threshold=.08
sc.cycles.adaptive_min_samples=1; sc.cycles.use_denoising=True
sc.cycles.max_bounces=2; sc.cycles.diffuse_bounces=1; sc.cycles.glossy_bounces=1
sc.render.use_persistent_data=True; sc.render.use_motion_blur=False
sc.render.resolution_x=1080; sc.render.resolution_y=1920; sc.render.resolution_percentage=100
sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGB'
sc.render.image_settings.compression=30;sc.render.fps=30
sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast'
sc.view_settings.exposure=-.3
def mesh(name,verts,faces,mat=None,parent=None,smooth=True):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    obj=bpy.data.objects.new(name,data);sc.collection.objects.link(obj)
    if parent:obj.parent=parent
    if mat:data.materials.append(mat)
    if smooth: data.polygons.foreach_set('use_smooth',np.ones(len(data.polygons),dtype=np.bool_))
    return obj
def empty(name):
    ob=bpy.data.objects.new(name,None);sc.collection.objects.link(ob);return ob
def material(name,col,rough=.5,metal=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*col,1)
    p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    return m,p
def ramp(nodes,points):
    n=nodes.new('ShaderNodeValToRGB');r=n.color_ramp
    for j,(v,col) in enumerate(points):
        el=r.elements[j] if j<2 else r.elements.new(v)
        el.position=v;el.color=(*col,1)
    return n
def sphere(name,loc,scale,mat,parent=None,sub=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=sub,ring_count=max(8,sub//2),radius=1,location=(0,0,0))
    ob=bpy.context.object;ob.name=name;ob.parent=parent;ob.location=loc;ob.scale=scale
    ob.data.materials.append(mat)
    for f in ob.data.polygons:f.use_smooth=True
    return ob
def line(name,pts,thick,mat,parent=None):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.bevel_depth=thick;data.bevel_resolution=1
    sp=data.splines.new('POLY');sp.points.add(len(pts)-1)
    for p,co in zip(sp.points,pts):p.co=(*co,1)
    ob=bpy.data.objects.new(name,data);sc.collection.objects.link(ob);ob.parent=parent;ob.data.materials.append(mat)
    return ob

# Shared object-space sand grains are baked into a tile once per worker.
sand,p=material('Subtidal quartz and calcareous sand',(.35,.31,.20),.83)
p.inputs['Specular IOR Level'].default_value=.18
nd=sand.node_tree.nodes;lk=sand.node_tree.links
anchor=empty('World-space grain origin')
tex=nd.new('ShaderNodeTexCoord');tex.object=anchor
v=nd.new('ShaderNodeVectorMath');v.operation='SCALE';v.inputs['Scale'].default_value=7.5
lk.new(tex.outputs['Object'],v.inputs[0])
N=512;rr=np.random.default_rng(197);g=rr.normal(0,1,(N,N))
g=(g*2.7+np.roll(g,1,0)+np.roll(g,1,1)+.5*np.roll(g,-1,1))/3.2
grain=np.clip(.5+.19*g,0,1)
im=bpy.data.images.new('Quartz grain microrelief',N,N,alpha=False,float_buffer=False)
im.colorspace_settings.name='Non-Color'
rgba=np.empty((N,N,4),np.float32);rgba[:,:,:3]=grain[:,:,None];rgba[:,:,3]=1;im.pixels.foreach_set(rgba.ravel());im.update()
img=nd.new('ShaderNodeTexImage');img.image=im;img.extension='REPEAT';lk.new(v.outputs['Vector'],img.inputs['Vector'])
cr=ramp(nd,[(0,(.13,.132,.097)),(.53,(.39,.325,.197)),(.90,(.61,.525,.347))]);lk.new(img.outputs['Color'],cr.inputs[0])
noise=nd.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=4.5;noise.inputs['Detail'].default_value=1.4;lk.new(tex.outputs['Object'],noise.inputs[0])
wash=ramp(nd,[(.12,(.54,.67,.61)),(.60,(.94,.93,.80)),(.82,(1.0,.99,.88))]);lk.new(noise.outputs['Fac'],wash.inputs[0])
mix=nd.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=.85;lk.new(cr.outputs[0],mix.inputs[1]);lk.new(wash.outputs[0],mix.inputs[2]);lk.new(mix.outputs[0],p.inputs['Base Color'])
# A broad, softly focused refracted light field drifts across the sand in world space.
ty,tx=np.mgrid[0:256,0:256].astype('f')*(2*pi/256)
field=np.sin(3*tx+.85*np.sin(2*ty)+.22*np.cos(3*tx+ty))+np.cos(3*ty+.72*np.cos(2*tx))+.33*np.sin(4*tx+2*ty)
light=.78+.22*np.exp(-(field/.29)**2)
ci=bpy.data.images.new('Soft refracted skylight',256,256,alpha=False);ci.colorspace_settings.name='Non-Color'
ca=np.ones((256,256,4),np.float32);ca[:,:,:3]=light[:,:,None];ci.pixels.foreach_set(ca.ravel());ci.update()
cu=nd.new('ShaderNodeVectorMath');cu.operation='SCALE';cu.inputs['Scale'].default_value=1.3;lk.new(tex.outputs['Object'],cu.inputs[0])
shift=nd.new('ShaderNodeVectorMath');shift.operation='ADD';lk.new(cu.outputs[0],shift.inputs[0])
ci_tex=nd.new('ShaderNodeTexImage');ci_tex.image=ci;lk.new(shift.outputs[0],ci_tex.inputs[0])
illum=nd.new('ShaderNodeMixRGB');illum.blend_type='MULTIPLY';illum.inputs[0].default_value=.63;lk.new(mix.outputs[0],illum.inputs[1]);lk.new(ci_tex.outputs[0],illum.inputs[2]);lk.new(illum.outputs[0],p.inputs['Base Color'])
bump=nd.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.22;bump.inputs['Distance'].default_value=.00038;lk.new(img.outputs['Color'],bump.inputs['Height']);lk.new(bump.outputs[0],p.inputs['Normal'])

def relief(x,y):
    r=np.hypot(x,y);a=np.arctan2(y,x)
    outer=np.clip((r-.235)/.19,0,1)*np.clip((1.045+.012*np.sin(5*a)-r)/.22,0,1)
    phase=26*a+.63*np.sin(4*a+5*r)+.45*np.sin(7*a-3*r)+1.3*(r-.56)**2+.25*np.sin(18*r+2*a)
    folds=(.5+.5*np.cos(phase))**1.6
    ring=outer*(.074*folds-.015)*(.9+.16*np.cos(4*a+2*r))
    maze=np.sin(44*x+3.3*np.sin(11*y)+1.9*np.cos(14*x+9*y))+np.sin(43*y+2.8*np.cos(11*x-6*y))+.53*np.cos(28*(x+y)+1.5*np.sin(19*x))
    center=.0057*(np.exp(-(maze/.32)**2)-.35)*np.clip((.37-r)/.09,0,1)
    bed=.0027*np.sin(11*x-8*y+1.8*np.sin(4*y))+.0017*np.sin(17*y+3*x)
    return ring+center+bed

def grid(name,xs,ys,z,mat,xoff=0):
    yy,xx=np.meshgrid(ys,xs,indexing='ij');h=np.broadcast_to(z(xx,yy),xx.shape)
    co=np.column_stack((xx.ravel()+xoff,yy.ravel(),h.ravel())).astype('f')
    ny,nx=xx.shape;idx=np.arange((ny-1)*nx).reshape(ny-1,nx)[:,:-1].ravel()
    face=np.stack((idx,idx+1,idx+nx+1,idx+nx),axis=-1)
    return mesh(name,co.tolist(),face.tolist(),mat),xx,yy,co

# Polar mesh follows the ridge crests; the surrounding bed extends beyond the camera.
rs=np.r_[np.linspace(.002,1.15,146),np.linspace(1.17,3.8,48)]
aa=np.linspace(0,2*pi,390,endpoint=False);rad,ang=np.meshgrid(rs,aa,indexing='ij')
xx=rad*np.cos(ang);yy=rad*np.sin(ang)
verts=np.column_stack((xx.ravel(),yy.ravel(),relief(xx,yy).ravel())).tolist()
nt=len(aa);nr=len(rs);faces=[(j*nt+i,(j+1)*nt+i,(j+1)*nt+(i+1)%nt,j*nt+(i+1)%nt) for j in range(nr-1) for i in range(nt)]
faces.append(tuple(reversed(range(nt))))
nest=mesh('Twenty-six radial ridges and fine central maze',verts,faces,sand)
def early_base(x,y):return .0014*np.sin(21*x+7*y)+.00065*np.sin(64*y+8*x)+.00055*np.sin(47*x-28*y)
early,X,Y,early_co=grid('Sand displaced behind paired fins',np.r_[np.linspace(-1.4,-.61,20),np.linspace(-.6,.6,181),np.linspace(.61,1.4,20)],np.r_[np.linspace(-2.6,-.39,60),np.linspace(-.38,.38,121),np.linspace(.39,2.6,60)],early_base,sand,4)
bed0=early_base(X,Y);cross=-.0065*np.exp(-(Y/.009)**2)+.0038*np.exp(-((np.abs(Y)-.017)/.0065)**2)
eggbed,_,_,_=grid('Fine central sand macro',np.linspace(-.065,.065,91),np.linspace(-.065,.065,91),lambda x,y:.00013*np.sin(x*680+y*150)*np.cos(y*615),sand,8)

calcium,_=material('Worn shell edges',(.69,.60,.39),.75)
pebble,_=material('Dark volcanic mineral',(.092,.093,.069),.88)
rose,_=material('Weathered coral grit',(.54,.35,.23),.82)
def fragments(name,points):
    vs=[];fs=[];inds=[]
    for x,y,z,l,w,h,turn,index in points:
        j=len(vs);n=7
        for i in range(n):
            a=2*pi*i/n;rad=rng.uniform(.73,1.13);u=l*rad*cos(a);v=w*rad*sin(a)
            vs.append((x+u*cos(turn)-v*sin(turn),y+u*sin(turn)+v*cos(turn),z+.30*h*sin(2*a)))
        vs.append((x+l*.18,y-w*.13,z+h));fs.extend((j+i,j+(i+1)%n,j+n) for i in range(n));inds.extend([index]*n)
    obj=mesh(name,vs,fs,None,smooth=False)
    for m in [calcium,pebble,rose]:obj.data.materials.append(m)
    obj.data.polygons.foreach_set('material_index',np.asarray(inds,dtype=np.int32))
    return obj
grits=[]
for i in range(850):
    a=rng.uniform(0,2*pi);r=rng.uniform(.29,1.45);x=r*cos(a);y=r*sin(a)
    l=rng.uniform(.0006,.005);grits.append((x,y,float(relief(x,y)),l,l*rng.uniform(.30,.70),l*.28,rng.uniform(0,pi),rng.randrange(3)))
for i in range(210):
    x=rng.uniform(-.4,.43);y=rng.uniform(-.22,.22)
    if abs(y)<.024:continue
    l=rng.uniform(.00035,.0017);grits.append((4+x,y,float(early_base(x,y)),l,.58*l,.32*l,rng.uniform(0,pi),rng.randrange(3)))
for i in range(280):
    x=rng.uniform(-.027,.027);y=rng.uniform(-.024,.024);l=rng.uniform(.00012,.00050)
    grits.append((8+x,y,.00013*sin(x*680+y*150)*cos(y*615),l,.77*l,.5*l,rng.uniform(0,pi),rng.randrange(3)))
fragments('Shell splinters and irregular coarse grains',grits)

# In-life, tapered form with a stout head and a narrow caudal peduncle.
skin,pr=material('Puffer dorsal reticulation fading to silvery belly',(.35,.30,.20),.42)
nd=skin.node_tree.nodes;lk=skin.node_tree.links;tc=nd.new('ShaderNodeTexCoord')
sep=nd.new('ShaderNodeSeparateXYZ');lk.new(tc.outputs['Generated'],sep.inputs[0])
v=nd.new('ShaderNodeVectorMath');v.operation='MULTIPLY';v.inputs[1].default_value=(2.5,1.,1.);lk.new(tc.outputs['Generated'],v.inputs[0])
vor=nd.new('ShaderNodeTexVoronoi');vor.inputs['Scale'].default_value=9.2;lk.new(v.outputs[0],vor.inputs[0])
spots=ramp(nd,[(.105,(.72,.65,.42)),(.28,(.30,.238,.128)),(.52,(.18,.144,.081)),(.80,(.32,.26,.14))]);lk.new(vor.outputs['Distance'],spots.inputs[0])
edge=nd.new('ShaderNodeTexVoronoi');edge.feature='DISTANCE_TO_EDGE';edge.inputs['Scale'].default_value=6.2;lk.new(v.outputs[0],edge.inputs[0])
nr=ramp(nd,[(.005,(.38,.32,.24)),(.065,(1,1,1))]);lk.new(edge.outputs[0],nr.inputs[0])
net=nd.new('ShaderNodeMixRGB');net.blend_type='MULTIPLY';net.inputs[0].default_value=.75;lk.new(spots.outputs[0],net.inputs[1]);lk.new(nr.outputs[0],net.inputs[2])
fade=ramp(nd,[(.32,(0,0,0)),(.60,(1,1,1))]);lk.new(sep.outputs['Z'],fade.inputs[0])
cm=nd.new('ShaderNodeMixRGB');cm.inputs[1].default_value=(.69,.61,.43,1);lk.new(fade.outputs[0],cm.inputs[0]);lk.new(net.outputs[0],cm.inputs[2]);lk.new(cm.outputs[0],pr.inputs['Base Color'])
bn=nd.new('ShaderNodeBump');bn.inputs['Strength'].default_value=.1;bn.inputs['Distance'].default_value=.00025;lk.new(vor.outputs['Distance'],bn.inputs['Height']);lk.new(bn.outputs[0],pr.inputs['Normal'])
hero=empty('Male Torquigener albomaculosus')
profile=np.array([[-.039,.0013,.0018,.0004],[-.034,.0023,.0025,.001],[-.027,.0047,.0050,.0005],[-.018,.0084,.0078,0],[-.008,.0121,.0114,.0001],[.005,.0149,.0141,.0005],[.016,.015,.0145,.0015],[.025,.0123,.0126,.0025],[.032,.0084,.0085,.003],[.037,.0041,.0043,.0023],[.039,.0012,.0019,.0025]])
vs=[];fs=[];ns=64
for j,x in enumerate(np.linspace(profile[0,0],profile[-1,0],85)):
    ry,rz,zc=[np.interp(x,profile[:,0],profile[:,k]) for k in (1,2,3)]
    for i in range(ns):
        a=2*pi*i/ns;vs.append((x,ry*cos(a),zc+rz*sin(a)))
        if j:fs.append(((j-1)*ns+i,(j-1)*ns+(i+1)%ns,j*ns+(i+1)%ns,j*ns+i))
fs+= [tuple(reversed(range(ns))),tuple(range(len(vs)-ns,len(vs)))]
mesh('Fine-spotted mantle and tapered caudal peduncle',vs,fs,skin,hero)
rim,_=material('Golden rim around the eye',(.53,.37,.11),.32,.12)
iris,_=material('Olive iris',(.18,.16,.055),.24,.26)
black,blackp=material('Wet pupil',(.004,.008,.007),.12,.10)
lip,_=material('Pale muzzle',(.56,.46,.3),.50)
crease,_=material('Gill and lip crease',(.11,.075,.040),.62)
for sg in (-1,1):
    sphere('Yellow orbital rim',(.019,.0121*sg,.0087),(.0046,.0032,.0046),rim,hero)
    sphere('Olive iris',(.0197,.0141*sg,.0090),(.00365,.0024,.0037),iris,hero)
    sphere('Dark pupil',(.0201,.0158*sg,.0091),(.0021,.00132,.00275),black,hero)
    sphere('Naris',(.033,.0055*sg,.0061),(.00085,.00059,.00053),crease,hero,12)
    line('Gill slit',[(.009+(.0018*sin(k*pi/8)),sg*(.0145+.00035*sin(k*pi/8)),.004-.001*k) for k in range(9)],.00032,crease,hero)
sphere('Upper lip',(.0374,0,.0030),(.0032,.0044,.0016),lip,hero)
sphere('Lower lip',(.0375,0,.00065),(.0024,.0039,.0014),lip,hero)
line('Mouth line',[(.0393-.0017*(i/6)**2,.0007*i,.0017+.00022*(i/6)**2) for i in range(-6,7)],.00023,crease,hero)
fin,fp=material('Translucent pale amber fin membrane',(.35,.285,.16),.38)
fp.inputs['Transmission Weight'].default_value=.25
finray,_=material('Fine fin rays',(.415,.337,.183),.42)
def makefin(name,base,direction,height,fan,side):
    o=empty(name+' joint');o.parent=hero;o.location=base
    edge=[];nrays=13
    for k in range(nrays):
        u=k/(nrays-1)*2-1;rad=1-.25*u*u
        edge.append(tuple(direction[j]*rad+height[j]*u+fan[j]*u*u for j in range(3)))
    verts=[(0,0,0)]+edge
    mesh(name,verts,[(0,k+1,k+2) for k in range(nrays-1)],fin,o)
    for k in range(0,nrays,2):
        e=edge[k];line(name+' ray',[(0,0,0),tuple(.53*v for v in e),e],.00010 if side else .000145,finray,o)
    return o
tail=makefin('Caudal fan',(-.037,0,.001),(-.022,0,0),(0,0,.0095),(.002,0,0),False)
fins=[]
for sg in (-1,1):
    fins.append(makefin('Pectoral fin',(.006,sg*.013,-.0005),(-.010,sg*.0090,-.005),(.004,sg*.002,.0055),(.001,0,0),True))
dorsal=makefin('Dorsal fin',(-.019,0,.007),(-.007,0,.009),(.005,0,0),(.0002,0,-.003),False)
anal=makefin('Anal fin',(-.023,0,-.005),(-.005,0,-.006),(.004,0,0),(.0001,0,.001),False)

# Small local scatter of grains rises outward from the working pectoral fins.
dustmat,_=material('Pale disturbed grains',(.58,.47,.27),.85)
dust=[]
for i in range(28):
    ob=sphere('A displaced grain',(0,0,0),(1,1,1),dustmat,hero,8)
    radius=rng.uniform(.00010,.00031);ob.scale=(radius,radius*.8,radius*.7)
    dust.append((ob,(-1 if i%2 else 1),rng.random(),rng.uniform(.75,1.3),radius))

egg,ep=material('Translucent egg casing',(.82,.73,.50),.25)
ep.inputs['Transmission Weight'].default_value=.21;ep.inputs['IOR'].default_value=1.36
yolk,_=material('Creamy yolk',(.69,.445,.195),.37)
for i in range(19):
    a=rng.uniform(0,2*pi);r=.0045*rng.random()**.6;x=.0002+r*cos(a);y=r*sin(a);rr=rng.uniform(.00039,.00053)
    z=.00013*sin(x*680+y*150)*cos(y*615)+rr*.78
    sphere('Egg envelope',(8+x,y,z),(rr,rr*.96,rr),egg,sub=16)
    sphere('Yolk',(8+x,y,z-.08*rr),(rr*.67,rr*.63,rr*.64),yolk,sub=12)

world=bpy.data.worlds.new('Blue-green underwater fill');world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.42,.70,.81,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.74;sc.world=world
sun=bpy.data.lights.new('Oblique filtered sunlight','SUN');sun.energy=3.25;sun.angle=.16;sun.color=(.98,.95,.80)
so=bpy.data.objects.new('Raking sunlight',sun);sc.collection.objects.link(so)
so.rotation_euler=Vector((.78,.27,-.68)).to_track_quat('-Z','Y').to_euler()
camdata=bpy.data.cameras.new('Documentary port');camdata.type='ORTHO';camdata.clip_start=.0006;camdata.clip_end=15
cam=bpy.data.objects.new('Camera',camdata);sc.collection.objects.link(cam);sc.camera=cam
def pose(i):
    t=i/FPS;name,u,_,_=shot(t)
    phase=2*pi*t/DUR;shift.inputs[1].default_value=(.044*sin(phase),.034*cos(phase),0)
    coords,h=puffer_state(t);x,y,z=coords
    isclose=name in ('portrait','fins','pass','trench')
    if not isclose:z+=float(relief(x,y))
    else:z+=float(early_base(x-4,y))-.0015
    hero.location=(x,y,z);hero.rotation_euler=(.025*sin(4*t),.02*cos(5.2*t),h+.018*sin(8.7*t))
    tail.rotation_euler.z=.28*sin(t*19)
    dorsal.rotation_euler.x=.15*sin(t*20)
    anal.rotation_euler.x=-.13*sin(t*20)
    for j,finobj in enumerate(fins):
        sg=(-1 if j==0 else 1);finobj.rotation_euler=(sg*.49*sin(t*24+j),.16*cos(t*24+j),sg*.28*cos(t*24+j))
    if isclose:
        xx=x-4-.01
        gate=np.clip((xx-X)/.022+.5,0,1);gate=gate*gate*(3-2*gate)
        early_co[:,2]=(bed0+gate*cross).ravel();early.data.vertices.foreach_set('co',early_co.ravel());early.data.update()
    for ob,sg,offset,freq,size in dust:
        v=(t*freq*2+offset)%1
        ob.hide_render=not isclose
        if isclose:
            ob.location=(.003-.021*v,sg*(.014+.019*v),-.014+.0104*sin(pi*v))
            k=.3+.7*sin(pi*v);ob.scale=(size*k,size*.8*k,size*.7*k)
    tg,off,width=camera_state(t);loc=Vector(tg)+Vector(off)
    cam.location=loc;cam.rotation_euler=(-Vector(off)).to_track_quat('-Z','Y').to_euler()
    camdata.ortho_scale=width*1.7777777778
def render(i,folder,preview=False):
    pose(i);folder.mkdir(exist_ok=True,parents=True);p=folder/f'{i:05}.png'
    if p.exists():return
    sc.render.resolution_percentage=25 if preview else 100
    sc.render.filepath=str(folder/f'{i:05}.part.png');bpy.ops.render.render(write_still=True)
    os.replace(sc.render.filepath,p)
if __name__=='__main__':
    if sys.argv[1]=='test':
        from timeline import CUTS
        for a,b in zip(CUTS,CUTS[1:]):render(min(NFRAMES-1,int((a+b)*15)),root/'qa'/'preview',True)
    elif sys.argv[1]=='save':
        pose(0);bpy.ops.wm.save_as_mainfile(filepath=str(root/'pufferfish-sand-circle.blend'))
    else:
        for i in range(int(sys.argv[1]),min(int(sys.argv[2]),NFRAMES)):render(i,Path(os.environ['FRAME_DIR']))
