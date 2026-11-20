from post import *
import cv2
from timeline import CUTS
c=cv2.VideoCapture('barreleye.mp4');n=0;cuts={math.ceil(v*FPS) for v in CUTS};Path('qa/sheets').mkdir(parents=True,exist_ok=True)
while True:
 ok,im=c.read()
 if not ok:break
 if n%80==0:sheet=Image.new('RGB',(1000,1504),(13,20,22));draw=ImageDraw.Draw(sheet)
 x=n%10*100;y=(n%80)//10*188
 thumb=Image.fromarray(cv2.cvtColor(cv2.resize(im,(100,178),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2RGB))
 sheet.paste(thumb,(x,y));draw.rectangle((x+8,y+28,x+80,y+143),outline=(56,95,93));draw.text((x+2,y+174),str(n),fill='orange' if n in cuts else 'white')
 if n%80==79:sheet.save('qa/sheets/%02d.jpg'%(n//80),quality=82)
 n+=1
if n%80:sheet.save('qa/sheets/%02d.jpg'%((n-1)//80),quality=82)
out=Image.new('RGB',(750,267))
for j,k in enumerate([NFRAMES-3,NFRAMES-2,NFRAMES-1,0,1]):out.paste(image_at(k).resize((150,267),Image.Resampling.LANCZOS),(j*150,0))
out.save('qa/seam.jpg',quality=90)
