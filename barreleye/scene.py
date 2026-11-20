"""A procedural reconstruction of Macropinna microstoma; +X points toward the mouth."""
import sys,os,math,random
from pathlib import Path
from math import sin,cos,pi
import bpy
from mathutils import Vector
from timeline import *
root=Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene;sc.render.engine='CYCLES'
sc.cycles.device='CPU';sc.cycles.samples=8;sc.cycles.adaptive_threshold=.08;sc.cycles.adaptive_min_samples=1
sc.cycles.use_denoising=True;sc.cycles.max_bounces=3;sc.cycles.diffuse_bounces=1;sc.cycles.glossy_bounces=1;sc.cycles.transparent_max_bounces=4
sc.render.resolution_x=1080;sc.render.resolution_y=1920;sc.render.resolution_percentage=100;sc.render.fps=30
sc.render.use_motion_blur=False;sc.render.use_persistent_data=True;sc.render.threads_mode='FIXED';sc.render.threads=4
sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=-.30
sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGBA';sc.render.image_settings.compression=85
# Only the occupied scanlines need tracing. The open water above and below is composited at native resolution.
sc.render.film_transparent=True;sc.render.use_border=True;sc.render.use_crop_to_border=True
sc.render.border_min_y=.27;sc.render.border_max_y=.73
world=bpy.data.worlds.new('Open water');sc.world=world;world.color=(.22,.26,.3)
def mat(name,col,rough=.4,metal=0,noise=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True
 nd=m.node_tree.nodes;lk=m.node_tree.links;pr=nd.get('Principled BSDF')
 pr.inputs['Base Color'].default_value=(*col,1);pr.inputs['Roughness'].default_value=rough;pr.inputs['Metallic'].default_value=metal
 if noise:
  tx=nd.new('ShaderNodeTexNoise');tx.inputs['Scale'].default_value=noise;tx.inputs['Detail'].default_value=3
  ramp=nd.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(*[i*.32 for i in col],1);ramp.color_ramp.elements[1].color=(*[min(1,i*1.7+.015) for i in col],1)
  lk.new(tx.outputs['Fac'],ramp.inputs[0]);lk.new(ramp.outputs[0],pr.inputs['Base Color'])
  bump=nd.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.17;bump.inputs['Distance'].default_value=.015;lk.new(tx.outputs['Fac'],bump.inputs['Height']);lk.new(bump.outputs[0],pr.inputs['Normal'])
 return m
def thin(name,col,amount,rough):
 m=mat(name,col,rough);n=m.node_tree.nodes;lk=m.node_tree.links
 tr=n.new('ShaderNodeBsdfTransparent');mx=n.new('ShaderNodeMixShader');fw=n.new('ShaderNodeLayerWeight');mul=n.new('ShaderNodeMath');mul.operation='MULTIPLY_ADD';mul.inputs[1].default_value=amount;mul.inputs[2].default_value=.035
 # Facing output is strongest at the silhouette.
 lk.new(fw.outputs['Facing'],mul.inputs[0]);lk.new(mul.outputs[0],mx.inputs[0]);lk.new(tr.outputs[0],mx.inputs[1]);lk.new(n.get('Principled BSDF').outputs[0],mx.inputs[2]);lk.new(mx.outputs[0],n.get('Material Output').inputs[0]);return m
body=mat('Umber and bronze dermis',(.130,.084,.056),.46,.17,19)
cheek=mat('Silvery lower head',(.32,.255,.211),.32,.35,15)
gill=mat('Operculum shadow',(.062,.042,.034),.45,.1,10)
dark=mat('Olfactory chamber',(.012,.009,.008),.34)
rim=mat('Mucosal fold',(.19,.127,.091),.31,.17,23)
shield=thin('Transparent fluid shield',(.42,.56,.65),.30,.17)
silver=mat('Tapetal sleeve',(.19,.235,.14),.29,.28,11)
lens=mat('Green lens pigment',(.35,.64,.079),.17,.24,7)
core=mat('Olive lens centre',(.25,.39,.036),.29,.15,10)
mem=thin('Translucent fin membrane',(.44,.37,.27),.83,.36)
ray=mat('Fin rays',(.33,.24,.145),.46,.16)
silk=mat('Silver skin folds',(.50,.42,.28),.38,.26)
plankton=thin('Drifting gelatinous prey',(.62,.76,.83),.8,.25)
def empty(name,parent=None):
 o=bpy.data.objects.new(name,None);sc.collection.objects.link(o);o.parent=parent;return o
hero=empty('Fish');eyes=[];fins=[]
def mesh(name,verts,faces,m,parent=hero):
 me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(name,me);sc.collection.objects.link(o);o.data.materials.append(m);o.parent=parent
 for p in me.polygons:p.use_smooth=True
 return o
def sphere(name,loc,scale,m,parent=hero):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=36,ring_count=20)
 o=bpy.context.object;o.name=name;o.parent=parent;o.location=loc;o.scale=scale;o.data.materials.append(m)
 for p in o.data.polygons:p.use_smooth=True
 return o
def line(name,pts,rad,m,parent=hero):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=8;c.bevel_depth=rad;c.bevel_resolution=2
 s=c.splines.new('BEZIER');s.bezier_points.add(len(pts)-1)
 for k,p in zip(s.bezier_points,pts):k.co=p;k.handle_left_type='AUTO';k.handle_right_type='AUTO'
 o=bpy.data.objects.new(name,c);sc.collection.objects.link(o);o.parent=parent;o.data.materials.append(m);return o
def hull(name,stations,m,half=False):
 # Monotone interpolation across anatomical cross sections.
 vs=[];faces=[];K=52
 for j in range(len(stations)-1):
  prev=stations[max(0,j-1)];a,b=stations[j:j+2];nxt=stations[min(len(stations)-1,j+2)]
  for ll in range(6):
   t=ll/6; vals=[]
   for idx in range(4):
    p0,p1,p2,p3=[k[idx] for k in (prev,a,b,nxt)]
    vals.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t**3))
   x,z,ry,rz=vals
   for k in range(K):
    ang=(pi*k/(K-1) if half else 2*pi*k/K);vs.append((x,max(.003,ry)*cos(ang),z+max(.003,rz)*sin(ang)-(.056*abs(cos(ang))**3 if half else 0)))
 rows=len(vs)//K
 if not half:
  faces.append(tuple(reversed(range(K))));faces.append(tuple((rows-1)*K+j for j in range(K)))
 for j in range(rows-1):
  for k in range(K-1 if half else K):
   l=(k+1)%K;faces.append((j*K+k,j*K+l,(j+1)*K+l,(j+1)*K+k))
 return mesh(name,vs,faces,m)
hull('Deep bodied trunk',[(-2.31,.015,.025,.06),(-2.05,.00,.10,.15),(-1.62,.04,.28,.34),(-1.04,.09,.47,.54),(-.42,.10,.56,.65),(-.05,.10,.56,.65),(.24,.06,.51,.58),(.49,-.03,.37,.40),(.66,-.10,.015,.05)],body)
hull('Opaque cheek and lower jaw',[(.03,-.13,.15,.26),(.24,-.15,.46,.37),(.68,-.19,.52,.32),(1.03,-.18,.46,.27),(1.34,-.14,.33,.20),(1.54,-.09,.22,.12),(1.64,-.07,.045,.045)],cheek)
hull('Continuous cephalic shield',[(-.21,.045,.49,.59),(.06,.06,.56,.68),(.44,.065,.55,.67),(.82,.057,.50,.60),(1.14,.065,.42,.46),(1.41,.038,.30,.28),(1.56,-.004,.18,.14),(1.61,-.045,.025,.035)],shield,True)
for side in [-1,1]:
 p=empty('Eye pivot',hero);p.location=(.63,side*.235,.074);eyes.append(p)
 # One continuous optical organ, with the olive lens blending into its silver-green tube.
 eye_mat=mat('Retinal tube and lens',(.24,.34,.10),.245,.21)
 nodes=eye_mat.node_tree.nodes;links=eye_mat.node_tree.links
 coord=nodes.new('ShaderNodeTexCoord');sep=nodes.new('ShaderNodeSeparateXYZ');links.new(coord.outputs['Generated'],sep.inputs[0])
 ramp=nodes.new('ShaderNodeValToRGB');rr=ramp.color_ramp;rr.elements[0].color=(.045,.060,.055,1);rr.elements[1].color=(.47,.62,.11,1)
 for pos,color in [(.40,(.10,.14,.104,1)),(.69,(.19,.24,.12,1)),(.81,(.23,.38,.063,1)),(.93,(.43,.61,.10,1))]:rr.elements.new(pos).color=color
 rr.interpolation='EASE';links.new(sep.outputs['Z'],ramp.inputs[0]);links.new(ramp.outputs[0],nodes.get('Principled BSDF').inputs['Base Color'])
 profile=[(-.12,.015),(-.08,.072),(.00,.108),(.11,.125),(.20,.132),(.278,.143),(.321,.149),(.357,.15),(.385,.138),(.407,.115),(.422,.083),(.434,.043),(.437,.003)]
 vs=[];fs=[]
 for zz,rrad in profile:
  for j in range(48):
   ang=j*2*pi/48;vs.append((rrad*cos(ang)+.02*zz,rrad*1.04*sin(ang),zz))
 for k in range(len(profile)-1):
  for j in range(48):fs.append((k*48+j,k*48+(j+1)%48,(k+1)*48+(j+1)%48,(k+1)*48+j))
 mesh('Pigmented tubular eye',vs,fs,eye_mat,p)
 loc=(1.40,side*.24,.108);o=sphere('Raised olfactory fold',loc,(.100,.055,.096),rim);o.rotation_euler.y=.30
 o=sphere('Dark olfactory opening',(1.435,side*.273,.124),(.064,.037,.055),dark);o.rotation_euler.y=.33
 line('Opercular boundary',[(.24,side*.51,.15),(.27,side*.54,-.01),(.18,side*.50,-.29),(-.01,side*.42,-.45)],.017,gill)
 for i in range(4):
  line('Branchiostegal fold',[(.77+i*.08,side*(.47-i*.025),-.20),(.64+i*.09,side*.43,-.33),(.40+i*.11,side*.36,-.40)],.008,silk)
 line('Mouth commissure',[(1.39,side*.31,-.096),(1.54,side*.195,-.112),(1.62,0,-.085)],.012,dark)
# Soft rostral folds seal the jaw; the tiny mouth has a lateral, shallow opening.
sphere('Upper lip',(1.591,0,-.060),(.061,.170,.044),cheek)
sphere('Lower lip',(1.585,0,-.123),(.060,.151,.039),cheek)
line('Mouth aperture',[(1.579,-.153,-.088),(1.632,-.078,-.095),(1.641,0,-.099),(1.632,.078,-.095),(1.579,.153,-.088)],.009,gill)
for s in (-1,1):
 line('Clear cowl crease',[(.26,s*.51,.00),(.61,s*.518,.004),(.96,s*.445,.006),(1.24,s*.355,.02)],.008,shield)
def fan(name,base,vecs):
 pivot=empty(name,hero);pivot.location=base;fins.append(pivot)
 vs=[];faces=[]
 for j,(x,y,z) in enumerate(vecs):
  for k in range(6):
   t=k/5;vs.append((x*t,y*t+.038*sin(t*pi),z*t))
  line('Segmented fin ray',[(0,0,0),(x*.5,y*.5+.035,z*.5),(x,y,z)],.007,ray,pivot)
 for j in range(len(vecs)-1):
  for k in range(5):faces.append((j*6+k,(j+1)*6+k,(j+1)*6+k+1,j*6+k+1))
 mesh(name+' veil',vs,faces,mem,pivot)
for s in [-1,1]:
 fan('Broad pectoral fin',(0,s*.48,-.12),[(-.26-.48*t,s*(.13+.47*sin(pi*t)),-.28-.46*sin(pi*t)) for t in [i/15 for i in range(16)]])
fan('Caudal fan',(-2.10,0,.018),[(-.72+.20*cos(pi*t)**2,.025*sin(pi*t),.46*cos(pi*t)) for t in [i/19 for i in range(20)]])
fan('Dorsal fin',(-1.24,0,.54),[(-.63*t,0,.30*sin(pi*t)+.035) for t in [i/13 for i in range(14)]])
fan('Anal fin',(-1.19,0,-.37),[(-.60*t,0,-.20*sin(pi*t)-.035) for t in [i/12 for i in range(13)]])
food=empty('Drifting pelagic morsel');sphere('Copepod carapace',(0,0,0),(.041,.036,.084),plankton,food)
for s in (-1,1):line('Antennule',[(0,0,.06),(.039,s*.038,.105),(.045,s*.12,.14)],.004,ray,food)
def area(name,p,energy,size,col):
 d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size;d.color=col
 o=bpy.data.objects.new(name,d);sc.collection.objects.link(o);o.location=p;o.rotation_euler=(-Vector(p)).to_track_quat('-Z','Y').to_euler()
area('ROV high softbox',(2,-3.7,4),345,3.0,(.86,.94,1));area('Warm port rim',(-2.5,.9,2.8),265,2.3,(1,.81,.60));area('Cool fluid rim',(.5,3,1.9),245,2,(.52,.79,1));area('Lower reflection',(2,-2,-1.5),53,1.9,(.58,.75,.86))
camdata=bpy.data.cameras.new('Macro port');cam=bpy.data.objects.new('Macro port',camdata);sc.collection.objects.link(cam);sc.camera=cam;camdata.type='ORTHO'
def pose(t):
 s,loc,target,width,f,a=frame_state(t)
 cam.location=loc;cam.rotation_euler=(Vector(target)-Vector(loc)).to_track_quat('-Z','Y').to_euler();camdata.ortho_scale=width*1920/1080
 hero.location=(0,.012*sin(a*2),.026*sin(a*2.4));hero.rotation_euler=(.012*sin(a*2),.013*sin(a*2.4),.017*sin(a*1.8))
 for p in eyes:p.rotation_euler.y=1.13*f+.018*sin(a*2)
 for i,p in enumerate(fins):p.rotation_euler.x=(.14 if i<2 else .034)*sin(a*4+.6*i);p.rotation_euler.z=.045*sin(a*3+i)
 t0=W('turn')[0]-.55;t1=W('pay')[0]+.45;q=ease((t-t0)/(t1-t0));food.location=(1.05+.55*q,-.08,.94-.99*q);food.rotation_euler.y=.30+q*.9
 food.scale=(1,)*3 if t0-.3<t<t1+.28 else (.00001,)*3
def render(i,test=False):
 pose(i/FPS);dst=root/('qa' if test else 'frames')/(('%05d'%i)+'.png')
 if dst.exists() and not test:return
 sc.render.resolution_percentage=25 if test else 100
 sc.render.filepath=str(dst.with_suffix('.part.png'));bpy.ops.render.render(write_still=True);os.replace(sc.render.filepath,dst)
if __name__=='__main__':
 mode=sys.argv[1]
 if mode=='test':
  for a,b in zip(CUTS,CUTS[1:]):render(int((a+b)*15),True)
 elif mode=='save':
  pose(0);bpy.ops.wm.save_as_mainfile(filepath=str(root/'barreleye.blend'))
 else:
  for i in range(int(sys.argv[1]),min(int(sys.argv[2]),NFRAMES)):render(i)
