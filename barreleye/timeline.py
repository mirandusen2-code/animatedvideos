import json
from pathlib import Path
from math import sin,pi
DATA=json.loads((Path(__file__).parent/'vo/timing.json').read_text())
FPS=30;NFRAMES=DATA['NFRAMES'];DUR=NFRAMES/FPS
def W(line,word=None):
 a,b=DATA['ranges'][line]
 if word:
  return next(v[:2] for v in DATA['words'][a:b] if v[2].strip('.,?!').lower()==word)
 return DATA['words'][a][:2]
def ease(x):
 x=min(1,max(0,x));return .85*x*x*x*(x*(x*6-15)+10)+.15*x
CUTS=[0,W('dome')[0]-.065,W('up')[0]-.065,W('turn','down')[0]-.065,W('pay')[0]-.065,W('loop')[0]-.065,DUR]
def shot(t):return min(5,sum(t>=a for a in CUTS[1:-1]))
def env_t(t):return t-DUR if shot(t)==5 else t
def frame_state(t):
 s=shot(t);q=ease((t-CUTS[s])/(CUTS[s+1]-CUTS[s]));a=env_t(t)
 poses=[((5.45,-1.18,1.26),(5.20,-1.72,1.29),(.88,0,.11),(.87,0,.13),2.58,2.48),((3.2,-3.8,1.6),(2.2,-4.25,1.75),(.8,0,.16),(.72,0,.22),2.72,2.53),((1.9,-4.6,1.25),(1.75,-4.6,1.32),(-.43,0,.10),(-.36,0,.17),5.08,5.0),((2.1,-4.25,1.32),(2.7,-4.6,1.2),(.75,0,.16),(.85,0,.13),2.72,2.66),((2.8,-4.5,1.05),(3.25,-4.15,1.0),(.9,0,.16),(.99,0,.12),3.2,3.05),((5.60,-.98,1.25),(5.45,-1.18,1.26),(.89,0,.11),(.88,0,.11),2.65,2.58)]
 A,B,C,D,l,m=poses[s];lerp=lambda u,v:tuple(i+(j-i)*q for i,j in zip(u,v))
 f=ease((t-W('turn','down')[0])/.9)*(1-ease((t-CUTS[5])/.72))
 return s,lerp(A,B),lerp(C,D),l+(m-l)*q,f,a
