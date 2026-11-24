"""Switch to the independent annotated preview after fresh frames arrive."""
import os
from pathlib import Path
import signal
import subprocess
import time

BASE = Path(__file__).resolve().parent
SCRIPT = str(BASE / 'camera-preview.py')
OLD = '/home/nvidia/.local/share/maxhub-5.10.46.0.BAJgRx/camera-preview.py'
HEARTBEAT = Path('/run/user/1000/luna-camera-real-marmot-trails/frame-heartbeat')
ENV = os.environ.copy()
ENV.update(DISPLAY=':0', XAUTHORITY='/run/luna-maxhub/Xauthority', XDG_RUNTIME_DIR='/run/user/1000')
stopping = False
player = None

def stop(signum, frame):
    global stopping
    stopping = True

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

def originals():
    result=[]
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit(): continue
        try:
            args=(entry/'cmdline').read_bytes().split(b'\0')
            if args[:2] == [b'/usr/bin/python3', OLD.encode()]: result.append(int(entry.name))
        except OSError: pass
    return result

try:
    while not stopping:
        subprocess.run(['sudo','-n','/usr/local/sbin/luna-maxhub-prepare'], env=ENV, check=True)
        if subprocess.run(['systemctl','is-active','--quiet','apex-camera.service']).returncode:
            subprocess.run(['sudo','-n','/usr/bin/systemctl','start','apex-camera.service'],env=ENV,check=True)
        log=BASE / ('preview-' + time.strftime('%Y%m%d-%H%M%S') + '.log')
        with log.open('wb') as output:
            player=subprocess.Popen(['/bin/bash','-lc',
                'source /etc/apex/apex_ros_env.sh; exec /usr/bin/python3 "$1"','bash',SCRIPT],
                env=ENV, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True)
        deadline=time.monotonic()+25
        ready=False
        while not stopping and time.monotonic()<deadline and player.poll() is None:
            if ('Preview frames received: 60' in log.read_text(errors='replace')
                    and HEARTBEAT.exists() and time.time()-HEARTBEAT.stat().st_mtime<3):
                ready=True
                break
            time.sleep(.3)
        if ready:
            subprocess.run(['systemctl','--user','stop','luna-camera-marmot-animation.service'],env=ENV,check=True)
            for pid in originals():
                try: os.kill(pid,signal.SIGTERM)
                except ProcessLookupError: pass
            print('Annotated preview ready; original preview retired. PID='+str(player.pid),flush=True)
            while not stopping and player.poll() is None:
                if not HEARTBEAT.exists() or time.time()-HEARTBEAT.stat().st_mtime>20:
                    print('Frame heartbeat stale; restarting annotated preview',flush=True)
                    break
                time.sleep(1)
        else:
            print('Annotated preview failed readiness; original preview preserved. Log='+str(log),flush=True)
        if player.poll() is None:
            os.killpg(player.pid,signal.SIGTERM)
            try: player.wait(timeout=4)
            except subprocess.TimeoutExpired: os.killpg(player.pid,signal.SIGKILL)
        for _ in range(5):
            if stopping: break
            time.sleep(1)
finally:
    if player is not None and player.poll() is None:
        os.killpg(player.pid,signal.SIGTERM)
