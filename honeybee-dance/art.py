"""Composite original native Cycles plates with an animated foraging-route diagram."""
import os,math,random
from pathlib import Path
from functools import lru_cache
import numpy as np
from PIL import Image,ImageDraw,ImageFilter,ImageFont
from timeline import FPS,DUR,NFRAMES,shot,ease
W,H=1080,1920
ASSET=Path(os.environ.get('BEE_ASSETS','assets'))
FONTP=Path(__file__).parent/'Montserrat.ttf'
def typeface(n):
    f=ImageFont.truetype(str(FONTP),n);f.set_variation_by_axes([740]);return f
@lru_cache(maxsize=20)
def source(name):
    return Image.open(ASSET/(name+'.png')).convert('RGBA' if name.startswith('bee') else 'RGB')
def comb(t,wide,u=0):
    bg=source('comb-wide' if wide else 'comb-close')
    sx=(1316 if wide else 1188)-int(34*u)
    sy=round(sx*H/W);x=round((bg.width-sx)/2+17*math.sin(t*.48));y=round((bg.height-sy)/2+22*math.sin(t*.39))
    x=max(0,min(bg.width-sx,x));y=max(0,min(bg.height-sy,y))
    assert sx>=W and sy>=H
    return bg.crop((x,y,x+sx,y+sy)).resize((W,H),Image.Resampling.LANCZOS)
@lru_cache(maxsize=190)
def stamp(phase,scale100,angle):
    b=source('bee-%02d'%phase)
    # The plate camera looks slightly from positive Y. Turn its projected head north.
    b=b.transpose(Image.Transpose.ROTATE_180)
    k=scale100/100;assert k<=1
    b=b.resize((round(b.width*k),round(b.height*k)),Image.Resampling.LANCZOS)
    b=b.rotate(-angle,Image.Resampling.BICUBIC,expand=True)
    bounds=b.getbbox()
    if bounds:b=b.crop(bounds)
    shadow=b.getchannel('A').filter(ImageFilter.GaussianBlur(max(2,round(8*k)))).point(lambda v:int(.32*v))
    return b,shadow
def actor(img,x,y,scale,bearing,phase):
    b,sh=stamp(phase%12,round(scale*100),round(bearing)%360)
    x=round(x-b.width/2);y=round(y-b.height/2)
    img.paste((38,25,13),(x+8,y+12,x+8+b.width,y+12+b.height),sh)
    img.paste(b,(x,y),b)
D2=math.sqrt(.5)
def vadd(o,a,d):return (o[0]+a[0]*d,o[1]+a[1]*d)
def motion(t):
    # A straight central waggle run with alternating, rounded return paths.
    period=1.72;cycle=math.floor(t/period);v=t/period-cycle
    stem=(D2,-D2);side=(D2,D2);origin=(447,912);length=192
    sign=1 if cycle%2 else -1
    if v<.39:
        u=v/.39;xy=vadd(origin,stem,length*u);return xy,45,True
    a=math.pi*(v-.39)/.61
    xy=vadd(vadd(origin,stem,length*(1+math.cos(a))/2),side,sign*126*math.sin(a))
    vx=-stem[0]*length/2*math.sin(a)+side[0]*sign*126*math.cos(a)
    vy=-stem[1]*length/2*math.sin(a)+side[1]*sign*126*math.cos(a)
    return xy,math.degrees(math.atan2(vx,-vy)),False
def dash(d,a,b,fill,width,seg=13,gap=12):
    dx=b[0]-a[0];dy=b[1]-a[1];L=math.hypot(dx,dy)
    if L<1:return
    for i in range(0,int(L),seg+gap):
        k=min(L,i+seg);d.line((a[0]+dx*i/L,a[1]+dy*i/L,a[0]+dx*k/L,a[1]+dy*k/L),fill=fill,width=width)
def arrow(d,a,b,fill,width=6):
    dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy)
    if L<.1:return
    dx/=L;dy/=L;sz=width*3.1;d.line((*a,*b),fill=fill,width=width)
    d.polygon([b,(b[0]-dx*sz+dy*sz*.47,b[1]-dy*sz-dx*sz*.47),(b[0]-dx*sz-dy*sz*.47,b[1]-dy*sz+dx*sz*.47)],fill=fill)
@lru_cache(maxsize=1)
def fields():
    rr=random.Random(663)
    # A bird's-eye atlas with surveyed field boundaries and hedgerows.
    yy,xx=np.mgrid[:H,:W].astype('f')
    qx=xx+49*np.sin(yy/311)+20*np.cos(yy/149+xx/550)
    qy=yy+63*np.sin(xx/291)+30*np.cos((xx+yy)/205)
    best=np.full_like(xx,1.e11);second=best.copy();tag=np.zeros_like(xx,dtype=np.int16)
    palette=[(66,88,64),(75,92,65),(72,90,69),(76,100,76),(59,83,68),(84,99,71),(69,89,70)]
    for i in range(42):
        x=rr.uniform(-110,W+110);y=rr.uniform(-100,H+100)
        dd=(qx-x)**2+.72*(qy-y)**2
        better=dd<best;second=np.where(better,best,np.minimum(second,dd));best=np.minimum(best,dd);tag=np.where(better,i%len(palette),tag)
    c=np.asarray(palette,dtype='f')[tag]
    hedges=np.exp(-np.maximum(0,np.sqrt(second)-np.sqrt(best))/6.7)
    soft=2.3*np.sin(xx*.022+yy*.032)+1.2*np.sin(yy*.115+qx*.057)
    c=c*(1-.30*hedges[:,:,None])+soft[:,:,None]
    im=Image.fromarray(np.clip(c,0,255).astype('uint8'));d=ImageDraw.Draw(im)
    track=[(-30,1460),(150,1293),(289,1211),(433,1179),(566,1143),(719,1120),(852,1052),(1089,984)]
    d.line(track,fill=(58,68,54),width=17,joint='curve');d.line(track,fill=(132,122,86),width=8,joint='curve')
    for _ in range(1200):
        x=rr.randint(0,W-1);y=rr.randint(0,H-1)
        if hedges[y,x]<.32 and rr.random()<.95:continue
        r=rr.uniform(2.5,11);d.ellipse((x-r+3,y-r+4,x+r+3,y+r+4),fill=(45,65,48))
        d.ellipse((x-r,y-r,x+r,y+r),fill=rr.choice([(64,86,57),(73,94,64),(79,98,66)]))
    return im
def flowers(d,x,y,scale=1):
    rr=random.Random(11)
    for i in range(19):
        a=rr.uniform(0,2*math.pi);dist=rr.uniform(4,42)*scale
        bx=x+math.cos(a)*dist;by=y+math.sin(a)*dist*.68;r=rr.uniform(2.0,4.4)*scale
        d.ellipse((bx-r,by-r,bx+r,by+r),fill=rr.choice([(255,216,108),(231,159,69),(248,225,153)]))
def sun(d,x,y):
    d.ellipse((x-20,y-20,x+20,y+20),fill=(255,211,112),outline=(255,237,180),width=3)
    for k in range(12):
        a=2*math.pi*k/12;d.line((x+27*cos(a),y+27*sin(a),x+39*cos(a),y+39*sin(a)),fill=(251,216,132),width=4)
sin=math.sin;cos=math.cos
def hiveglyph(d,x,y):
    for i,(w,shade) in enumerate([(68,(191,141,70)),(79,(203,151,78)),(75,(218,173,91))]):
        d.rounded_rectangle((x-w/2,y+15-20*i,x+w/2,y+34-20*i),radius=4,fill=shade,outline=(69,60,40),width=3)
    d.polygon([(x-48,y-28),(x,y-52),(x+48,y-28)],fill=(226,190,111),outline=(70,60,43))
    d.rounded_rectangle((x-12,y+13,x+12,y+33),radius=4,fill=(55,54,41))
def atlas(name,u,t):
    im=fields().copy();d=ImageDraw.Draw(im)
    ox,oy=390,1110;sy=573;sun(d,ox,sy)
    dash(d,(ox,oy-42),(ox,sy+42),(212,214,173),5,15,15)
    d.arc((ox-132,oy-132,ox+132,oy+132),270,315,fill=(252,211,116),width=6)
    distance=365 if name=='map' else 560
    end=(ox+D2*distance,oy-D2*distance);flowers(d,*end,1.18)
    k=.12+.88*(.86*ease(u)+.14*u);p=vadd((ox,oy),(D2,-D2),58+(distance-65)*k)
    arrow(d,vadd((ox,oy),(D2,-D2),48),p,(252,203,81),9)
    hiveglyph(d,ox,oy)
    if name=='map':
        # One short label disambiguates the reference bearing.
        d.text((ox+56,sy-16),'SUN',font=typeface(42),fill=(251,237,191),stroke_width=2,stroke_fill=(58,76,58))
    # A small moving forager is an explicitly schematic map marker.
    actor(im,p[0],p[1],.079,45,int(t*11)%12)
    return im
def frame(i):
    t=i/FPS;name,u,a,b=shot(t)
    if name in ('map','far'):return atlas(name,u,t)
    env=t-DUR if name=='quiz' else t
    wide=name in ('hive','angle')
    if name=='quiz':
        im=comb(env,False,0)
    else:im=comb(t,wide,0 if name=='hook' else u*.55)
    draw=ImageDraw.Draw(im)
    phase=int((env*30)%12)
    if name in ('hook','quiz'):
        x=493+12*sin(env*.83);y=936-36*sin(env*.95)
        angle=3.8*sin(env*2.4);size=.62
        actor(im,100+8*sin(env),608,.28,-137,int(env*11)%12)
        actor(im,948,1106+5*sin(env),.26,150,int(env*12)%12)
        if name=='quiz' and u<.79:
            dash(draw,(x,y+248),(x,y+75),(244,213,140),5,10,14)
            arrow(draw,(x,y-240),(x,y-325),(252,219,135),6)
    elif name=='hive':
        (x,y),angle,stroking=motion(t-a+.13);size=.35
        actor(im,270,771,.27,116,round(t*10)%12);actor(im,735,1038,.30,-66,round(t*12+2)%12)
        pts=[motion(t-a+.13-j*.021)[0] for j in range(65)]
        for j in range(len(pts)-1,0,-1):
            if j%3!=0:draw.line((*pts[j],*pts[j-1]),fill=(225,179+int(29*(1-j/65)),100),width=4)
    elif name in ('run','duration'):
        x=413+167*u;y=1010-167*u;size=.58 if name=='run' else .53
        angle=45+3*sin(t*13)
        dash(draw,(271,1152),(x-70,y+70),(248,203,111),5,10,14)
        actor(im,826,765,.26,-125,int(t*15)%12)
    else:
        ox,oy=390,1110;x=ox+172+47*u;y=oy-172-47*u;size=.35;angle=45
        dash(draw,(ox,oy-10),(ox,595),(250,231,178),5,15,17)
        draw.arc((ox-132,oy-132,ox+132,oy+132),270,315,fill=(255,210,88),width=7)
        arrow(draw,(ox,oy),(ox+275,oy-275),(255,213,91),7)
        draw.text((ox+17,565),'UP',font=typeface(42),fill=(255,238,181),stroke_width=3,stroke_fill=(70,46,27))
    actor(im,x,y,size,angle,phase)
    return im
