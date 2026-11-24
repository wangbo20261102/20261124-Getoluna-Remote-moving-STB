import json
from pathlib import Path
import subprocess
import time
from battery_overlay import refresh,video_filter
from animation_control import Client,filtergraph
import animation_control

base=Path(__file__).resolve().parent
qa=base/'qa';qa.mkdir(exist_ok=True)
animation_control.ENDPOINT='ipc://'+str(qa/'test-animation.sock')
refresh()
graph=filtergraph(video_filter(),control=False,enabled=True)
subprocess.run(['/usr/bin/ffmpeg','-hide_banner','-loglevel','error','-y',
                '-i','/run/user/1000/luna-camera-battery-overlay/first-camera-frame.jpg',
                '-vf',graph,'-frames:v','1',str(qa/'charging-animals.png')],check=True)
with (qa/'ipc-test.log').open('wb') as logfile:
    player=subprocess.Popen(['/usr/bin/ffmpeg','-hide_banner','-loglevel','error',
        '-re','-f','lavfi','-i','color=c=black:s=3840x2160:r=5',
        '-vf',filtergraph(video_filter()),'-t','4','-f','null','-'],stderr=logfile)
    client=Client()
    replies=[]
    try:
        deadline=time.monotonic()+3
        while True:
            try:
                replies.append(client.request('overlay@battery1 enable 1'))
                break
            except TimeoutError:
                if time.monotonic()>deadline:raise
        for command in ['overlay@battery2 enable 1','overlay@battery1 enable 0','overlay@battery2 enable 0']:
            replies.append(client.request(command))
        player.wait(timeout=8)
        if player.returncode:raise RuntimeError('Filter exited with error')
    finally:
        if player.poll() is None:player.terminate();player.wait()
        client.close()
report={'offline_render':True,'charging_visibility_commands':replies,'real_battery_data_modified':False}
(qa/'render-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
