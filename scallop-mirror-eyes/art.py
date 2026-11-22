"""Native microphotography-style plates and a ray-optics cutaway drawn at final size."""
import math,os,random
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from timeline import FPS,DUR,shot,ease
W,H=1080,1920
P=Path(os.environ.get('SCALLOP_ASSETS','assets'))
@lru_cache(maxsize=5)
def plate(name):
    return Image.open(P/(name+'.png')).convert('RGB')
def crop(name,u,cx,cy,zoom):
    im=plate(name);sw=round(zoom);sh=round(sw*H/W)
    x=min(im.width-sw,max(0,round(cx-sw/2)));y=min(im.height-sh,max(0,round(cy-sh/2)))
    assert sw>=W and sh>=H
    return im.resize((W,H),Image.Resampling.LANCZOS,box=(x,y,x+sw,y+sh))
def field(t):
    # Near and far suspended material. Every particle has the same phase at the loop.
    rng=random.Random(212);v=[]
    for j in range(46):
        x,y,r,s,phase=rng.uniform(0,W),rng.uniform(0,H),rng.choice([1,1,2,2,3]),rng.uniform(.4,1.3),rng.uniform(0,6)
        v.append(((x+13*math.sin(t*.53+phase)+t*4*s)%W,(y-t*13*s+11*math.cos(t*.31+phase))%H,r))
    return v
def macro_motion(im,t):
    glass=Image.new('RGBA',(W,H));d=ImageDraw.Draw(glass)
    for x,y,r in field(t):d.ellipse((x-r,y-r,x+r,y+r),fill=(200,237,227,28+5*r))
    im.paste(glass,(0,0),glass);return im
@lru_cache(maxsize=1)
def section_base():
    # Pigment cup, cornea, weak lens, double retinal tissue and posterior mirror.
    yy,xx=np.ogrid[:H+156,:W+156];cx,cy=511,895
    rr=np.sqrt(((xx-cx)/297)**2+((yy-cy)/322)**2)
    halo=np.exp(-rr**2/2.7);light=np.exp(-(((xx-309)/319)**2+((yy-646)/366)**2))
    base=np.empty((H+156,W+156,3),np.uint8)
    for c,(lo,hi) in enumerate([(7,13),(22,40),(34,53)]):
        base[:,:,c]=np.uint8(lo+halo*hi+light*(7-c))
    im=Image.fromarray(base);d=ImageDraw.Draw(im)
    # Restrained concentric cell wall, painted with compound depth.
    for i in range(36):
        u=i/35;k=1-.00225*i
        c=(int(26+26*math.sin(pi*u)),int(55+57*math.sin(pi*u)),int(70+63*math.sin(pi*u)))
        d.ellipse((cx-294*k,cy-321*k,cx+294*k,cy+321*k),fill=c)
    for j in range(220):
        k=1-j/244;col=(int(12+10*(1-k)),int(45+25*(1-k)),int(65+25*(1-k)))
        d.ellipse((cx-266*k,cy-296*k,cx+266*k,cy+296*k),fill=col)
    d.ellipse((cx-154,594,cx+154,683),fill=(46,105,127),outline=(108,173,187),width=4)
    d.arc((cx-148,600,cx+148,679),183,335,fill=(175,211,215),width=4)
    # Two retinal layers. The marker on the upper face receives the ray bundle.
    for layer,(off,shade) in enumerate([(0,(108,166,149)),(27,(71,119,123))]):
        for i in range(-16,17):
            x=cx+12*i;y=977+off-(x-cx)**2*.00018
            d.rounded_rectangle((x-5,y-5,x+5,y+12),radius=4,fill=shade)
    for i in range(-28,29):
        x1=cx+i*8-3.5;x2=x1+7;y1=mir(x1);y2=mir(x2)
        d.polygon([(x1,y1),(x2,y2),(x2,y2+13),(x1,y1+13)],fill=[(158,202,205),(205,223,212),(129,179,186)][i%3])
    return im
pi=math.pi;CX=511;YV=1130;FOC=149
def mir(x):return YV-(x-CX)**2/(4*FOC)
def beam(d,a,b,color,phase,width=3):
    d.line((a,b),fill=color,width=width)
    x=a[0]+(b[0]-a[0])*phase;y=a[1]+(b[1]-a[1])*phase
    r=4;d.ellipse((x-r,y-r,x+r,y+r),fill=(255,248,205))
def label(d,txt,x,y):
    f=ImageFont.truetype(str(Path(__file__).parent/'Montserrat.ttf'),44);f.set_variation_by_axes([740])
    assert 92<=x and x+f.getlength(txt)<=860 and 300<=y<=1480
    d.text((x,y),txt,font=f,fill=(202,224,217),anchor='lt')
def section(name,u,t):
    im=section_base().copy();d=ImageDraw.Draw(im)
    for i,x in enumerate([391,471,551,631]):
        by=mir(x)
        start=490-18*math.sin(i);phase=(t*.96+.17*i)%1
        # Phase moves downward before reflection and upward after reflection.
        frac=1 if name!='enter' else min(1,.15+1.05*u)
        beam(d,(x,start),(x,start+(by-start)*frac),(228,186,102),phase,4)
        if name=='focus':
            end=(CX,YV-FOC);k=min(1,.18+2.4*u);p=(x+(end[0]-x)*k,by+(end[1]-by)*k)
            beam(d,(x,by),p,(131,226,224),phase,5)
    if name=='reflector':
        d.line([(690,mir(690)+10),(758,1168),(794,1168)],fill=(186,214,209),width=3)
        label(d,'MIRROR',640,1190)
    if name=='focus':
        rad=9+3*math.sin(8*t);d.ellipse((CX-rad,YV-FOC-rad,CX+rad,YV-FOC+rad),outline=(253,238,179),width=3)
        d.line([(599,977),(730,916),(788,916)],fill=(170,205,196),width=3);label(d,'RETINA',653,853)
    # Keep the section in the macro camera while the rays cross it.
    # Native overscan supports tracking without magnification or edge repetition.
    x=round(8+104*u);y=round(10+73*u)
    return im.crop((x,y,x+W,y+H))
def frame(i):
    t=i/FPS;name,u,a,b=shot(t);q=.78*ease(u)+.22*u
    if name in ('enter','reflector','focus'):return section(name,u,t)
    if name in ('macro','return'):
        v=t if name=='macro' else t-DUR
        im=crop('mantle',u,643+44*math.sin(v*.52),1141+25*math.sin(v*.41),1164-22*math.sin(v*.48))
        return macro_motion(im,v)
    if name=='animal':im=crop('animal',u,645+34*(q-.5),1152+26*q,1252-109*q)
    elif name=='rim':im=crop('mantle',u,565+126*q,1148-44*q,1114+21*q)
    elif name=='single':im=crop('single',u,653-37*q,1142+19*q,1221-115*q)
    else:im=crop('crystals',u,602+72*q,1154-45*q,1262-151*q)
    return macro_motion(im,t)
