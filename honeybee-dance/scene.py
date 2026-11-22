"""Original Cycles assets for a vertical-comb motion study of Apis mellifera."""
import bpy,math,random,sys,os
from pathlib import Path
from math import sin,cos,pi
from mathutils import Vector
rng=random.Random(704);out=Path(os.environ['BEE_ASSETS']);out.mkdir(exist_ok=True,parents=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=12
sc.cycles.use_denoising=True;sc.cycles.adaptive_threshold=.075;sc.cycles.max_bounces=3;sc.cycles.transparent_max_bounces=5
sc.render.use_motion_blur=False;sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGBA'
sc.render.image_settings.compression=38;sc.render.film_transparent=True;sc.render.use_persistent_data=True;sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=-.05
world=bpy.data.worlds.new('Soft hive fill');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.52,.60,.62,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.52;sc.world=world
def mat(name,c,rough=.5,metal=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    return m
def mesh(name,vs,fs,material,parent=None,smooth=True):
    me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update()
    o=bpy.data.objects.new(name,me);sc.collection.objects.link(o);o.parent=parent
    if material:me.materials.append(material)
    if smooth:
        for p in me.polygons:p.use_smooth=True
    return o
def group(name,parent=None,pos=(0,0,0)):
    o=bpy.data.objects.new(name,None);sc.collection.objects.link(o);o.parent=parent;o.location=pos;return o
def orb(name,pos,scale,m,parent=None,quality=36):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=quality,ring_count=quality//2,location=(0,0,0))
    o=bpy.context.object;o.name=name;o.parent=parent;o.location=pos;o.scale=scale;o.data.materials.append(m)
    for p in o.data.polygons:p.use_smooth=True
    return o
def tube(name,coords,radii,m,parent=None):
    vs=[];fs=[];points=[Vector(x) for x in coords];nr=7
    for j,p in enumerate(points):
        tangent=(points[min(j+1,len(points)-1)]-points[max(0,j-1)]).normalized()
        side=tangent.cross(Vector((0,0,1)))
        if side.length<.01:side=tangent.cross(Vector((1,0,0)))
        side.normalize();up=tangent.cross(side).normalized()
        for i in range(nr):
            v=p+radii[j]*(cos(2*pi*i/nr)*side+sin(2*pi*i/nr)*up);vs.append(v[:])
            if j:fs.append(((j-1)*nr+i,(j-1)*nr+(i+1)%nr,j*nr+(i+1)%nr,j*nr+i))
    return mesh(name,vs,fs,m,parent)
camdata=bpy.data.cameras.new('Macro lens');camdata.type='ORTHO';camdata.clip_start=.01;camdata.clip_end=70
camera=bpy.data.objects.new('Camera',camdata);sc.collection.objects.link(camera);sc.camera=camera
def aim(loc,tg,width,sx,sy):
    sc.render.resolution_x=sx;sc.render.resolution_y=sy;camera.location=loc
    camera.rotation_euler=(Vector(tg)-Vector(loc)).to_track_quat('-Z','Y').to_euler()
    camdata.ortho_scale=width*max(sx,sy)/sx
def area(name,loc,power,col,size):
    l=bpy.data.lights.new(name,'AREA');l.energy=power;l.color=col;l.shape='DISK';l.size=size
    o=bpy.data.objects.new(name,l);sc.collection.objects.link(o);o.location=loc;o.rotation_euler=(-Vector(loc)).to_track_quat('-Z','Y').to_euler()
    return o
area('Amber side softbox',(-4,3,6),560,(1,.81,.55),4)
area('Cool back rim',(3,-2,4),250,(.67,.80,1),3)
def render(name):
    sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
dark=mat('Espresso chitin',(.042,.029,.018),.38);darkband=mat('Dark sclerite margins',(.057,.035,.017),.43)
amber=mat('Burnished amber tergites',(.38,.205,.063),.43);gold=mat('Ochre band',(.54,.326,.093),.53)
fuzz=mat('Honey-blond setae',(.62,.437,.205),.77);silk=mat('Pale setae tips',(.70,.56,.32),.78)
bristle=mat('Umber setae',(.23,.135,.061),.77);legmat=mat('Segmented ochre-black legs',(.13,.077,.032),.38)
eye=mat('Chestnut compound eyes',(.042,.028,.022),.28,.15)
# Fine facets interrupt the glossy surface of the compound eye.
nd=eye.node_tree.nodes;links=eye.node_tree.links
vr=nd.new('ShaderNodeTexVoronoi');vr.feature='DISTANCE_TO_EDGE';vr.inputs['Scale'].default_value=63
bp=nd.new('ShaderNodeBump');bp.inputs['Distance'].default_value=.003;bp.inputs['Strength'].default_value=.22
links.new(vr.outputs[0],bp.inputs['Height']);links.new(bp.outputs[0],nd.get('Principled BSDF').inputs['Normal'])
root=group('Honeybee worker');abd=group('Mobile abdominal joint',root,(0,-.12,.38))
def envelope(y):return max(0,1-((y+.52)/.77)**2)**.65*(.40+.042*(y+.5))
vs=[];fs=[];rings=92;sectors=60;y0=-1.27;y1=.19
abdidx=[]
for j in range(rings):
    y=y0+(y1-y0)*j/(rings-1);r=envelope(y);phase=(y-y0)/.221
    lip=1-.045*(.5+.5*cos(2*pi*phase))**8
    for i in range(sectors):
        a=2*pi*i/sectors;vs.append((r*lip*cos(a),y,.031*cos((y+.57)*2)+r*.76*lip*sin(a)))
        if j:
            fs.append(((j-1)*sectors+i,j*sectors+i,j*sectors+(i+1)%sectors,(j-1)*sectors+(i+1)%sectors))
            p=phase%1;abdidx.append(0 if p<.31 or y<-.99 else (2 if p>.875 else 1))
o=mesh('Overlapping banded abdominal segments',vs,fs,None,abd)
for m in [darkband,amber,gold]:o.data.materials.append(m)
for p,idx in zip(o.data.polygons,abdidx):p.material_index=idx
orb('Dark thoracic plate',(0,.25,.44),(.363,.442,.33),dark,root)
orb('Worker head',(0,.772,.41),(.315,.255,.249),dark,root)
for sg in (-1,1):
    o=orb('Compound eye',(sg*.231,.80,.46),(.107,.175,.154),eye,root);o.rotation_euler.z=sg*.17
for x,y in [(-.073,.834),(.073,.834),(0,.88)]:
    orb('Ocellus',(x,y,.63),(.027,.025,.017),eye,root,16)
def haircloud(name,geo,pars):
    vs=[];fs=[];inds=[]
    for pos,normal,length,idx in geo:
        p=Vector(pos);n=Vector(normal).normalized();b=n.cross(Vector((0,1,0)))
        if b.length<.02:b=n.cross(Vector((1,0,0)))
        b.normalize();k=n.cross(b).normalized();tip=p+n*length+Vector((0,-length*.41,0))
        rad=length*.055;j=len(vs)
        vs += [(p+b*rad)[:],(p-b*rad+k*rad*.7)[:],(p-b*rad-k*rad*.7)[:],tip[:]]
        fs.extend([(j,j+1,j+3),(j+1,j+2,j+3),(j+2,j,j+3)]);inds.extend([idx]*3)
    ob=mesh(name,vs,fs,None,pars,False)
    for m in [fuzz,silk,bristle]:ob.data.materials.append(m)
    for p,idx in zip(ob.data.polygons,inds):p.material_index=idx
hairs=[]
for _ in range(3700):
    a=rng.uniform(0,2*pi);z=rng.uniform(-.7,1);r=math.sqrt(1-z*z);n=(r*cos(a),r*sin(a),z)
    pos=(.363*n[0],.25+.442*n[1],.44+.33*n[2]);hairs.append((pos,n,rng.uniform(.028,.074),rng.choices([0,1,2],[.49,.27,.24])[0]))
haircloud('Dense branched-looking thoracic pile',hairs,root)
hairs=[]
for _ in range(1750):
    y=rng.uniform(-1.23,.10);r=envelope(y);a=rng.uniform(0,2*pi);z=sin(a);n=(cos(a),-.11,z)
    hairs.append(((r*cos(a),y,.031*cos((y+.57)*2)+r*.76*z),n,rng.uniform(.012,.035),0 if (y-y0)/.221%1>.65 else 2))
haircloud('Short abdominal setae',hairs,abd)
antennae=[]
for sg in (-1,1):
    g=group('Antennal pivot',root,(sg*.105,.946,.50));antennae.append(g)
    tube('Scape and flagellum',[(0,0,0),(sg*.098,.104,.07),(sg*.159,.19,.089),(sg*.236,.245,.048),(sg*.287,.32,-.015)],[.017,.014,.017,.012,.005],dark,g)
    for k in range(1,8):
        t=k/8;orb('Flagellum segment',(sg*(.159+.125*t),.19+.13*t,.089-.102*t),(.010,.014,.008),legmat,g,12)
legs=[]
for sg in (-1,1):
    for i,(y,footy) in enumerate([(.49,.34),(.22,-.11),(-.055,-.43)]):
        joint=group('Coxa',root,(sg*.235,y,.29));legs.append((joint,sg,i))
        pts=[(0,0,0),(sg*.18,.04,-.07),(sg*(.29+.032*i),footy*.6,-.15),(sg*(.34+.06*i),footy,-.23),(sg*(.45+.065*i),footy-.035,-.266)]
        tube('Six walking legs',pts,[.039,.041,.048 if i==2 else .030,.018,.006],legmat,joint)
        if i==2:
            tib=orb('Hind tibia pollen basket',pts[2],(.071,.115,.031),legmat,joint,24);tib.rotation_euler.z=sg*.55
        tube('Tarsal claw',[pts[-1],(pts[-1][0]+sg*.024,pts[-1][1]-.025,-.27)],[.007,.0015],dark,joint)
wing=mat('Thin amber wing membrane',(.57,.60,.49),.23,.16);nd=wing.node_tree.nodes;lk=wing.node_tree.links
p=nd.get('Principled BSDF');tr=nd.new('ShaderNodeBsdfTransparent');mx=nd.new('ShaderNodeMixShader');mx.inputs[0].default_value=.26
lk.new(tr.outputs[0],mx.inputs[1]);lk.new(p.outputs[0],mx.inputs[2]);lk.new(mx.outputs[0],nd.get('Material Output').inputs[0])
vein=mat('Umber wing venation',(.19,.142,.084),.38)
wings=[]
for sg in (-1,1):
    for hind in (True,False):
        g=group('Wing hinge',root,(sg*(.17 if hind else .205),.18 if hind else .31,.664 if hind else .714));wings.append((g,sg,hind))
        size=.73 if hind else 1
        def point(u,v):
            return (sg*size*(.37*u+.34*v),size*(-1.48*u+.018*v),size*(-.20*u-.087*v+.057*sin(pi*u)))
        # Outline, a costal leading edge and enclosed branching cells.
        boundary=[(.01,0),(.08,-.16),(.20,-.29),(.45,-.33),(.71,-.24),(.92,-.13),(1,0),(.96,.23),(.81,.46),(.62,.59),(.38,.58),(.2,.44),(.095,.26)]
        verts=[point(.47,.11)]+[point(u,v) for u,v in boundary]
        mesh('Hindwing' if hind else 'Forewing',verts,[(0,k+1,1+(k+1)%len(boundary)) for k in range(len(boundary))],wing,g)
        edges=[boundary+[boundary[0]],[(0,0),(.23,-.07),(.49,-.08),(.77,-.05),(.98,.01)],[(.05,.03),(.24,.21),(.47,.26),(.68,.21),(.91,.12)],[(.18,-.27),(.23,-.07),(.24,.21),(.21,.45)],[(.42,-.31),(.49,-.08),(.47,.26),(.59,.56)],[(.69,-.22),(.68,-.07),(.68,.21),(.79,.46)],[(.24,.21),(.38,.41),(.59,.56)]]
        for e,path in enumerate(edges):
            pts=[point(u,v) for u,v in path];tube('Visible wing vein',pts,[size*(.0062 if e==0 else .0044)]*len(pts),vein,g)
def pose(j):
    a=2*pi*j/12;abd.rotation_euler.z=.19*sin(a)
    for leg,sg,i in legs:leg.rotation_euler=(.105*cos(a+i*pi+sg),.07*sin(a+i*pi),sg*.18*sin(a+i*pi+(sg+1)*pi/2))
    for i,g in enumerate(antennae):g.rotation_euler.z=.09*sin(a+.9*i)
    for g,sg,h in wings:g.rotation_euler.z=sg*(.018*cos(a) if not h else .012*sin(a))
beeobs=list(root.children_recursive)+[root]
aim((0,-.11,6),(0,-.12,.28),2.02,820,1080)
for j in range(12):pose(j);render(f'bee-{j:02}')
# The separate comb is shot at native macro and wide magnifications.
for ob in beeobs:ob.hide_render=True
waxcolors=[(.43,.204,.055),(.58,.30,.084),(.54,.26,.048),(.61,.36,.115),(.43,.237,.073)]
wax=[]
for j,c in enumerate(waxcolors):
    m=mat('Hand-built wax '+str(j),c,.56)
    n=m.node_tree.nodes;lk=m.node_tree.links;tx=n.new('ShaderNodeTexNoise');tx.inputs['Scale'].default_value=105;tx.inputs['Detail'].default_value=2
    bu=n.new('ShaderNodeBump');bu.inputs['Distance'].default_value=.013;bu.inputs['Strength'].default_value=.20;lk.new(tx.outputs['Fac'],bu.inputs['Height']);lk.new(bu.outputs['Normal'],n.get('Principled BSDF').inputs['Normal'])
    wax.append(m)
inner=mat('Deep wax cell floor',(.125,.050,.013),.64);honey=mat('Small nectar meniscus',(.28,.095,.014),.17,.14)
vs=[];fs=[];idx=[];R=.405
def warp(x,y):
    return (.016*sin(.7*x+1.17*y)+.015*sin(2.2*x-.51*y),.009*cos(1.2*x-y)+.018*sin(.97*x+.4*y))
for col in range(-13,14):
    for row in range(-17,18):
        cx=1.5*R*col;cy=math.sqrt(3)*R*(row+.5*(col%2));ci=rng.randrange(len(wax));j=len(vs);N=18
        high=rng.uniform(-.033,.034);sweet=rng.random()<.085
        for ri,(scale,z) in enumerate([(1.,.035),(.946,.082),(.884,.057),(.851,-.04),(.77,-.34),(.39,-.52)]):
            for k in range(N):
                side=k//3;t=(k%3)/3;a=pi/3*side;b=pi/3*(side+1)
                hx=(1-t)*cos(a)+t*cos(b);hy=(1-t)*sin(a)+t*sin(b)
                x=cx+R*scale*hx;y=cy+R*scale*hy;wx,wy=warp(x,y)
                vz=z+high+.016*sin(4*x+3*y)+.012*cos(7*y-2*x)
                vs.append((x+wx,y+wy,vz))
                if ri:
                    fs.append((j+(ri-1)*N+k,j+(ri-1)*N+(k+1)%N,j+ri*N+(k+1)%N,j+ri*N+k));idx.append(ci if ri<5 else (len(wax) if not sweet else len(wax)+1))
        fs.append(tuple(j+5*N+k for k in range(N)));idx.append(len(wax)+int(sweet))
comb=mesh('Vertical worker comb with uneven raised cell lips',vs,fs,None)
for m in wax+[inner,honey]:comb.data.materials.append(m)
for p,mi in zip(comb.data.polygons,idx):p.material_index=mi
sc.render.film_transparent=False
for name,width in [('comb-close',4.55),('comb-wide',7.35)]:
    aim((.27,-.58,9),(0,0,0),width,1400,2460);render(name)
