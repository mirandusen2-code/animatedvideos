"""Optical range flight, native Cycles camera plates and a one-year ruler."""
import json,math,os
from pathlib import Path
from functools import lru_cache
from PIL import Image,ImageDraw,ImageFont
import numpy as np
P=Path(os.environ['PLATES']);HERE=Path(__file__).resolve().parent
D=json.loads((HERE/'vo/timing.json').read_text());N=D['NFRAMES'];DUR=N/30
def W(key,word=None):
    if word is None:return D['lines'][key][0]
    a,b=D['ranges'][key]
    return next(v[0] for v in D['words'][a:b] if v[2].casefold().strip('.,?')==word)
SHOTS=[('moon',0),('array',W('apollo')-.07),('station',W('pulse')-.07),('clock',W('echo')-.09),('measure',W('drift')-.07),('ruler',W('drift','drifting')-.07),('quiz',W('quiz')-.07),('return',DUR-.80)]
def shot(t):
    n=max(i for i,(_,a) in enumerate(SHOTS) if a<=t)
    name,a=SHOTS[n];b=SHOTS[n+1][1] if n+1<len(SHOTS) else DUR
    return name,max(0,min(1,(t-a)/(b-a))),a,b
@lru_cache(maxsize=3)
def plate(name):return Image.open(P/(name+'.png')).convert('RGB')
@lru_cache(maxsize=12)
def font(px):return ImageFont.truetype(os.environ['CAPTION_FONT'],px)
def ease(u):return .15*u+.85*u*u*(3-2*u)
def track(name,cx,cy,span):
    im=plate(name);w=round(span);h=round(w*16/9)
    assert w>=1080 and h>=1920
    x=round(max(0,min(im.width-w,cx-w/2)));y=round(max(0,min(im.height-h,cy-h/2)))
    return im.resize((1080,1920),Image.Resampling.LANCZOS,box=(x,y,x+w,y+h))
@lru_cache(maxsize=1)
def instrument():
    y,x=np.ogrid[:2070,:1230]
    g=np.exp(-((x-520)/700)**2-((y-880)/605)**2)
    rgb=np.stack([6+10*g,13+18*g,22+25*g],axis=-1).astype(np.uint8)
    im=Image.fromarray(rgb);d=ImageDraw.Draw(im)
    for xx in range(70,1180,90):
        for yy in range(320,1490,90):d.line((xx-2,yy,xx+2,yy),fill=(33,54,64));d.line((xx,yy-2,xx,yy+2),fill=(33,54,64))
    return im
GOLD=(251,204,117);TEAL=(129,218,222);WHITE=(222,231,228)
@lru_cache(maxsize=2)
def disk(which):
    im=plate(which);size=260 if which=='moon' else 280
    if which=='moon':box=(10,520,1310,1820)
    else:box=(295,815,1045,1565)
    return im.resize((size,size),Image.Resampling.LANCZOS,box=box)
def emblem(im,x,y,which):
    im2=disk(which);r=im2.width//2;mask=Image.new('L',im2.size);ImageDraw.Draw(mask).ellipse((1,1,2*r-2,2*r-2),fill=255)
    im.paste(im2,(x-r,y-r),mask);d=ImageDraw.Draw(im);d.ellipse((x-r,y-r,x+r,y+r),outline=(58,85,96),width=3)
def diagram(name,t,u,elapsed):
    im=instrument().copy();emblem(im,331,1012,'station');emblem(im,766,641,'moon');d=ImageDraw.Draw(im)
    d.text((248,1180),'EARTH',font=font(45),fill=WHITE,anchor='lt');d.text((704,458),'MOON',font=font(45),fill=WHITE,anchor='lt')
    a=np.array([443.,912.]);b=np.array([665.,735.]);delta=b-a
    d.line([tuple(a),tuple(b)],fill=(65,91,98),width=4)
    clock=min(2.5,max(0,elapsed))
    leg=min(1.,clock/1.25);point=a+delta*leg
    if clock<=1.25:
        d.line([tuple(a),tuple(point)],fill=GOLD,width=5);col=GOLD
    else:
        frac=(clock-1.25)/1.25;point=b-delta*frac;d.line([tuple(b),tuple(point)],fill=TEAL,width=5);col=TEAL
    x,y=point;d.ellipse((x-11,y-11,x+11,y+11),fill=col,outline=WHITE,width=2)
    if name=='clock':
        val=round(clock*100);seconds=f'{val//100}.{val%100:02d} s'
        # Fixed field prevents the digits from pushing the decimal point around.
        for i,c in enumerate(seconds):d.text((224+i*42,550),c,font=font(70),fill=TEAL if clock>=1.25 else GOLD,anchor='mt')
    camx=round(15+85*u);camy=round(0+55*u)
    return im.crop((camx,camy,camx+1080,camy+1920))
def ruler(t,u):
    im=instrument().copy();d=ImageDraw.Draw(im)
    x0=250;y0=1040;inch=290
    d.text((x0,590),'ONE YEAR',font=font(53),fill=WHITE)
    d.line((x0-8,y0,x0+2*inch+12,y0),fill=(164,189,192),width=4)
    for k in range(33):
        x=round(x0+k*inch/16);h=59 if k%16==0 else 42 if k%8==0 else 28 if k%4==0 else 16
        d.line((x,y0,x,y0+h),fill=WHITE,width=3 if k%4==0 else 2)
    for k in range(3):d.text((x0+inch*k,y0+65),str(k),font=font(50),fill=WHITE,anchor='mt')
    d.text((x0+2*inch-17,y0+150),'in',font=font(40),fill=WHITE)
    q=ease(min(1,u/.84));x=x0+1.5*inch*q
    d.line((x0,922,x,922),fill=TEAL,width=5)
    for p in (x0,x):d.line((p,900,p,y0-10),fill=TEAL,width=3)
    d.polygon([(x-10,892),(x+10,892),(x,912)],fill=GOLD)
    d.text((x0,734),f'{1.5*q:.1f} in',font=font(84),fill=GOLD)
    dx=round(15+79*u);dy=round(5+46*u)
    return im.crop((dx,dy,dx+1080,dy+1920))
def frame(i):
    t=i/30;name,u,a,b=shot(t);q=ease(u)
    if name in ('moon','return'):
        v=t if name=='moon' else t-DUR
        return track('moon',655+42*math.sin(v*.64),1180+22*math.sin(v*.49),1230-48*math.sin(v*.50))
    if name=='array':return track('array',625+82*q,1150+51*q,1290-180*q)
    if name=='station':
        span=1282-132*q;cx=670-61*q;cy=1180-42*q
        im=track('station',cx,cy,span)
        # Trace a brief outgoing pulse in the atmosphere at the open shutter.
        if t>=W('pulse','fires')-.12:
            px=(626-(cx-span/2))*1080/span;py=(803-(cy-span*8/9))*1080/span
            pulse=math.exp(-((t-W('pulse','laser')+.03)/.25)**2)
            veil=Image.new('RGBA',im.size);d=ImageDraw.Draw(veil)
            for width,alpha in [(15,15),(6,48),(2,190)]:
                d.line((px,py,px+323,py-820),fill=(125,239,189,round(alpha*pulse)),width=width)
            im.paste(veil,(0,0),veil)
        return im
    if name=='clock':return diagram(name,t,u,t-a)
    if name=='measure':return track('array',690-87*q,1213-65*q,1110+86*q)
    if name=='ruler':return ruler(t,u)
    return diagram(name,t,u,min(2.5,(t-a)*1.12))
