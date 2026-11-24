"""Facing, upright cartoon marmots with alternating sparring paws."""
from PIL import Image,ImageDraw
import math
from pathlib import Path

BASE=Path(__file__).resolve().parent/'assets'
BASE.mkdir(exist_ok=True)

def marmot(phase,fur):
    im=Image.new('RGBA',(160,128));d=ImageDraw.Draw(im)
    bob=round(2*math.sin(phase*2));outline='#483629'
    d.ellipse((24,88+bob,55,118+bob),fill='#745036',outline=outline,width=3)
    d.ellipse((45,48+bob,102,116+bob),fill=fur,outline=outline,width=3)
    d.ellipse((58,67+bob,92,109+bob),fill='#d5ae7a')
    d.ellipse((47,108,73,123),fill=fur,outline=outline,width=3)
    d.ellipse((80,108,107,123),fill=fur,outline=outline,width=3)
    d.ellipse((47,14+bob,67,35+bob),fill=fur,outline=outline,width=3)
    d.ellipse((53,20+bob,62,30+bob),fill='#d9b184')
    d.ellipse((83,14+bob,101,35+bob),fill=fur,outline=outline,width=3)
    d.ellipse((45,23+bob,108,73+bob),fill=fur,outline=outline,width=3)
    d.ellipse((81,44+bob,117,67+bob),fill='#dfbb89',outline=outline,width=2)
    d.ellipse((107,45+bob,119,55+bob),fill='#3d3029')
    d.ellipse((86,34+bob,96,46+bob),fill='#fff8e7',outline=outline,width=2)
    d.ellipse((91,37+bob,96,43+bob),fill='#282624')
    d.line([(85,31+bob),(97,35+bob)],fill=outline,width=3)
    d.rectangle((102,60+bob,110,68+bob),fill='#fff8df',outline=outline,width=1)
    d.line([(106,61+bob),(106,67+bob)],fill=outline,width=1)
    reach=round(12*math.sin(phase))
    d.line([(92,78+bob),(117-reach//2,79+bob)],fill=outline,width=13)
    d.line([(92,78+bob),(117-reach//2,79+bob)],fill=fur,width=9)
    d.ellipse((110-reach//2,72+bob,125-reach//2,87+bob),fill='#d9af78',outline=outline,width=2)
    d.line([(97,66+bob),(130+reach,58+bob)],fill=outline,width=14)
    d.line([(97,66+bob),(130+reach,58+bob)],fill=fur,width=10)
    d.ellipse((123+reach,50+bob,140+reach,67+bob),fill='#dbb27d',outline=outline,width=2)
    return im

def frame(i):
    phase=2*math.pi*i/16
    im=Image.new('RGBA',(256,128))
    im.alpha_composite(marmot(phase,'#997249'),(0,0))
    im.alpha_composite(marmot(phase+math.pi,'#b48a58').transpose(Image.FLIP_LEFT_RIGHT),(96,0))
    if i in (3,4,11,12):
        d=ImageDraw.Draw(im)
        d.line([(128,42),(128,34)],fill='#ffdb78',width=3)
        d.line([(122,44),(116,39)],fill='#ffdb78',width=3)
        d.line([(134,44),(140,39)],fill='#ffdb78',width=3)
    return im

palette=frame(0).convert('RGB').quantize(colors=255)
frames=[]
for i in range(16):
    rgba=frame(i)
    im=rgba.convert('RGB').quantize(palette=palette,dither=0)
    im.paste(255,mask=rgba.getchannel('A').point(lambda a:255 if a<128 else 0))
    im.putpalette((im.getpalette()+[0]*768)[:765]+[0,0,0]);frames.append(im)
frames[0].save(BASE/'marmots.gif',save_all=True,append_images=frames[1:],duration=80,
               loop=0,transparency=255,disposal=2,optimize=False)
print('Created 16-frame upright marmot sparring loop')
