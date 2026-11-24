"""Small procedural UI sprites; transparent, no external assets."""
from PIL import Image, ImageDraw
import math
from pathlib import Path

BASE=Path(__file__).resolve().parent/'assets'
BASE.mkdir(exist_ok=True)

def frame(kind,index):
    image=Image.new('RGBA',(192,128))
    d=ImageDraw.Draw(image)
    phase=2*math.pi*index/16
    bob=round(2*math.sin(phase))
    if kind=='turtle':
        for x,offset in [(49,0),(100,math.pi)]:
            step=round(5*math.sin(phase+offset))
            d.ellipse((x+step,83,x+25+step,103),fill='#9ac95e',outline='#244e38',width=3)
        d.polygon([(23,78),(44,70),(47,86)],fill='#a3d263',outline='#244e38')
        d.ellipse((113,57+bob,160,88+bob),fill='#a3d263',outline='#244e38',width=3)
        d.ellipse((38,34+bob,128,89+bob),fill='#4e9c62',outline='#244e38',width=4)
        d.ellipse((48,43+bob,116,79+bob),fill='#67b778',outline='#315d43',width=2)
        d.polygon([(69,45+bob),(93,45+bob),(104,60+bob),(92,77+bob),(68,77+bob),(57,61+bob)],outline='#315d43',width=3)
        d.line([(69,45+bob),(64,35+bob)],fill='#315d43',width=2)
        d.line([(104,60+bob),(125,60+bob)],fill='#315d43',width=2)
        d.ellipse((143,64+bob,150,71+bob),fill='#172e25')
        d.arc((143,69+bob,160,82+bob),10,95,fill='#315d43',width=2)
    else:
        d.ellipse((25,82,170,106),fill='#f3c682',outline='#73533e',width=3)
        d.polygon([(126,92),(133,66+bob),(152,62+bob),(164,95)],fill='#f3c682')
        d.ellipse((130,57+bob,160,84+bob),fill='#f5d294',outline='#73533e',width=2)
        for x,y in [(141,42+bob),(162,39+bob)]:
            d.line([(145,65+bob),(x,y)],fill='#b88752',width=4)
            d.ellipse((x-5,y-5,x+5,y+5),fill='#fff5dc',outline='#73533e',width=2)
            d.ellipse((x,y-2,x+3,y+2),fill='#352a29')
        d.ellipse((37,27+bob,120,99+bob),fill='#dc935c',outline='#704a35',width=4)
        d.ellipse((46,35+bob,110,91+bob),fill='#efb877',outline='#b77849',width=2)
        points=[]
        for i in range(120):
            t=i/119*math.pi*4.7;r=1+t*1.7
            points.append((78+r*math.cos(t),64+bob+r*.88*math.sin(t)))
        d.line(points,fill='#98613e',width=4)
        for x in range(48,146,16):
            y=102+round(2*math.sin(phase+x/12))
            d.line([(x,y),(x+9,y)],fill='#bc8d58',width=2)
    return image

for kind in ('turtle','snail'):
    frames=[]
    palette=frame(kind,0).convert('RGB').quantize(colors=255)
    for i in range(16):
        rgba=frame(kind,i)
        im=rgba.convert('RGB').quantize(palette=palette,dither=0)
        im.paste(255,mask=rgba.getchannel('A').point(lambda a:255 if a<128 else 0))
        im.putpalette((im.getpalette()+[0]*768)[:765]+[0,0,0])
        frames.append(im)
    frames[0].save(BASE/(kind+'.gif'),save_all=True,append_images=frames[1:],duration=80,
                   loop=0,transparency=255,disposal=2,optimize=False)
print('Created turtle and snail: 16 transparent frames each')
