"""Read-only <30% battery speech, repeated every ten seconds."""
import argparse
from datetime import datetime
import fcntl
import json
import math
from pathlib import Path
import signal
import subprocess
import time

BASE = Path(__file__).resolve().parent
SOURCE = Path('/run/luna-battery-screen/status.json')
RUNTIME = Path('/run/user/1000/luna-battery-voice-warning')
CLIP = BASE / 'warning-charge-now.wav'
SINK = 'alsa_output.platform-sound.analog-stereo'
INTERVAL = 10.0
stopping = False


def low_batteries(data, source_age):
    if (not 0 <= source_age < 5 or data.get('fresh') is not True
            or not isinstance(data.get('seconds_since_feedback'), (int, float))
            or not 0 <= data['seconds_since_feedback'] < 8):
        return []
    low = []
    for b in data.get('batteries', []):
        energy = b.get('energy')
        if (b.get('id') in (1,2) and b.get('is_connected') is True
                and b.get('is_in_place') is True
                and isinstance(energy, (int,float)) and not isinstance(energy,bool)
                and math.isfinite(energy) and 0 <= energy < 30):
            low.append({'id':b['id'], 'energy':energy})
    return low


class Schedule:
    def __init__(self): self.last_started = float('-inf')
    def due(self, low, now): return bool(low) and now-self.last_started >= INTERVAL
    def started(self, now): self.last_started = now


def log(event, **fields):
    print(json.dumps({'event':event,'wall_time':datetime.now().astimezone().isoformat(),
                      'mono':time.monotonic(),**fields},ensure_ascii=False),flush=True)


def read_low():
    try:
        age=time.time()-SOURCE.stat().st_mtime
        data=json.loads(SOURCE.read_text(encoding='utf-8'))
        return low_batteries(data,age), data
    except (OSError,ValueError,TypeError,AttributeError): return [],{}


def play():
    return subprocess.Popen(['/usr/bin/paplay','--server=unix:/run/user/1000/pulse/native',
                             '--device='+SINK,'--volume=65536',str(CLIP)],
                            stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)


def shutdown(signum,frame):
    global stopping
    stopping=True


def status(value):
    path=RUNTIME/'status.json'
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)


def run_test(count):
    """Explicit playback test only. No fake battery data is written."""
    results=[]
    origin=time.monotonic()
    with (RUNTIME/'playback.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for index in range(count):
            target=origin+INTERVAL*index
            while not stopping and time.monotonic()<target:
                time.sleep(max(0,min(.1,target-time.monotonic())))
            if stopping: break
            started=time.monotonic()
            log('test_playback_started',number=index+1,relative_seconds=started-origin)
            proc=play()
            try:
                _,stderr=proc.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill();proc.communicate();raise RuntimeError('Audio playback timed out')
            row={'number':index+1,'started_mono':started,'relative_seconds':started-origin,
                 'returncode':proc.returncode,'stderr':stderr.decode(errors='replace')}
            results.append(row)
            log('test_playback_finished',**row)
            if proc.returncode: break
    report={'mode':'explicit_playback_test','real_battery_data_modified':False,
            'requested_count':count,'results':results,
            'start_intervals_seconds':[b['started_mono']-a['started_mono'] for a,b in zip(results,results[1:])],
            'success':len(results)==count and all(r['returncode']==0 for r in results)}
    (BASE/('playback-test-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')).write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not report['success']: raise RuntimeError('Playback test incomplete')


def live():
    schedule=Schedule()
    proc=None
    lock=None
    starts=0
    last_error=None
    try:
        while not stopping:
            now=time.monotonic()
            low,data=read_low()
            if proc is not None:
                if not low and proc.poll() is None:
                    proc.terminate()
                    log('playback_cancelled',reason='threshold cleared or data unavailable')
                if now-schedule.last_started>8 and proc.poll() is None:
                    proc.kill()
                    last_error='Audio playback timed out'
                if proc.poll() is not None:
                    _,stderr=proc.communicate(timeout=1)
                    if proc.returncode and low:
                        last_error=stderr.decode(errors='replace') or str(proc.returncode)
                    log('playback_finished',returncode=proc.returncode,error=last_error)
                    proc=None
                    lock.close();lock=None
            if proc is None and schedule.due(low,now):
                candidate=(RUNTIME/'playback.lock').open('a')
                try:
                    fcntl.flock(candidate,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:
                    candidate.close()
                else:
                    try:
                        proc=play();lock=candidate
                        schedule.started(time.monotonic());starts+=1;last_error=None
                        log('low_battery_playback_started',low_batteries=low,playback_count=starts)
                    except OSError as exc:
                        candidate.close();last_error=str(exc);schedule.started(now)
            status({'message':'warning，请立即充电','threshold_percent':30,'repeat_seconds':INTERVAL,
                    'low_batteries':low,'playing':proc is not None,'live_playback_count':starts,
                    'last_error':last_error,'updated_at':datetime.now().astimezone().isoformat()})
            time.sleep(.2)
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=2)
            except subprocess.TimeoutExpired: proc.kill()
        if lock is not None: lock.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--test-playbacks',type=int,choices=[3,10])
    args=parser.parse_args()
    RUNTIME.mkdir(parents=True,exist_ok=True)
    if not CLIP.is_file(): raise SystemExit('Speech clip missing')
    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGINT,shutdown)
    if args.test_playbacks: run_test(args.test_playbacks)
    else: live()
