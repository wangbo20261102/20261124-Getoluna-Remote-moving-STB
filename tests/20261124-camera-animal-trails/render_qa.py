from pathlib import Path
import subprocess
from battery_overlay import refresh,video_filter
from animation_control import filtergraph

root=Path(__file__).resolve().parent/'qa';root.mkdir(exist_ok=True)
refresh()
for phase in [0,10,20.3,20.9,30.3]:
    subprocess.run(['/usr/bin/ffmpeg','-hide_banner','-loglevel','error','-y',
        '-i','/run/user/1000/luna-camera-charging-animations/first-camera-frame.jpg',
        '-vf',filtergraph(video_filter(),control=False,enabled=True,time_offset=phase),
        '-frames:v','1',str(root/f'phase-{phase}.png')],check=True)
print('Rendered start, trails, turtle reset, snail reset')
