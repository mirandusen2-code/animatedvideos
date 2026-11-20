from post import *
from timeline import W
dest=Path('thumbnails');dest.mkdir(exist_ok=True)
for label,t,rows in [('choice-a',.72,["THOSE AREN’T","ITS EYES"]),('choice-b',W('dome')[0]+.65,["INSIDE ITS","CLEAR HEAD"]),('choice-c',W('turn','forward')[0]+.05,["ITS EYES","CAN TURN"])]:
 im=image_at(round(t*FPS));d=ImageDraw.Draw(im)
 for j,row in enumerate(rows):
  sz=100;f=font(sz)
  while f.getlength(row)>733:sz-=1;f=font(sz)
  pos=(105,343+j*112)
  box=d.textbbox(pos,row,font=f,anchor='lt',stroke_width=7)
  assert 92<=box[0] and box[2]<=860 and 300<=box[1] and box[3]<=1540
  d.text(pos,row,font=f,anchor='lt',fill=(255,197,89) if not j else (245,248,241),stroke_width=7,stroke_fill=(10,24,27))
 im.save(dest/(label+'.jpg'),quality=94,subsampling=0)
