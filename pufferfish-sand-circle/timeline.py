import json
import math
from pathlib import Path
D=json.loads((Path(__file__).parent/'vo/timing.json').read_text())
FPS=30
NFRAMES=D['NFRAMES']
DUR=NFRAMES/FPS

def W(key, word=None):
    if word is None:
        return D['lines'][key][0]
    lo,hi=D['ranges'][key]
    for t,_,w,_,_ in D['words'][lo:hi]:
        if w.strip('.,!?').lower()==word.lower(): return t
    raise KeyError((key,word))

def ease(v):
    v=max(0.,min(1.,v))
    return .15*v+.85*v*v*v*(10+v*(-15+6*v))

def mix(a,b,u):
    return a+(b-a)*u

# Distinct shots use spoken transitions, with one small editorial lead.
SHOTS=[
 ('circle',0),('coast',W('where')-.06),('portrait',W('where','male')-.06),
 ('width',W('where','over')-.06),('fins',W('fins')-.05),('pass',W('dig')-.06),
 ('trench',W('ridges')-.06),('radial',W('ridges','hundreds')-.06),
 ('center',W('eggs')-.06),('roe',W('eggs','eggs')-.06),('find',W('question')-.06)]
CUTS=[start for _,start in SHOTS]+[DUR]

def shot(t):
    k=max(i for i,(_,s) in enumerate(SHOTS) if s<=t+1e-8)
    name,a=SHOTS[k];b=CUTS[k+1]
    return name,ease((t-a)/(b-a)),a,b

def camera_state(t):
    name,u,a,b=shot(t)
    dx=.006*math.sin(2*math.pi*t/DUR)
    # x/y/z look target, camera offset from target and horizontal field of view (meters)
    if name=='circle':
        return (dx,.035+.05*u,0),(.10+.13*u,-.18-.20*u,2.9),mix(2.23,1.81,u)
    if name=='coast':
        return (.02+.12*u,.07,0),(.17,-1.05,1.06),mix(1.65,1.38,u)
    if name=='width':
        return (0,.08,0),(.10+.17*u,-.40,2.5),mix(2.03,2.21,u)
    if name=='radial':
        return (.03+.02*u,.07,0),(.37-.29*u,-.76+.41*u,1.5+.6*u),mix(1.28,2.16,u)
    if name=='center':
        return (.02-.04*u,.04+.015*u,.008),(.09,-.38,.42),mix(.68,.49,u)
    if name=='find':
        return (dx,.035,0),(.1,-.18,2.9),mix(2.04,2.23,u)
    if name=='roe':
        return (8.0+.002*u,.0,.001),(.006,-.032,.022),mix(.030,.025,u)
    pos,heading=puffer_state(t)
    x,y,z=pos
    if name=='portrait':
        return (x+.009,y,z+.001),(.064-.022*u,-.135,.042+.012*u),mix(.157,.131,u)
    if name=='fins':
        return (x+.008,y,z-.003),(.015,-.086,.028),mix(.105,.094,u)
    if name=='pass':
        return (x-.008,y,z-.004),(-.026+.022*u,-.095,.068),mix(.155,.181,u)
    return (x-.047-.026*u,y+.002,z-.008),(-.055,-.026,.190),mix(.200,.235,u)

def puffer_state(t):
    name,u,a,b=shot(t)
    if name in ('portrait','fins','pass','trench'):
        # Natural-length male moving up a single trench in the early construction set.
        x=4.0-.145+.019*(t-W('where','male'))
        return ((x,.004*math.sin(t*1.55),.0158+.0008*math.sin(t*5.1)),.035*math.sin(t*2.7))
    phase=2*math.pi*t/DUR
    x=-.42+.036*math.sin(phase)
    y=-.64+.04*math.sin(phase)
    if name=='center':
        x=-.07+.045*u; y=.08+.033*u
    return ((x,y,.016),.82+.06*math.sin(phase))
