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


def data_fresh(data, source_age):
    seconds=data.get('seconds_since_feedback')
    return (0 <= source_age < 5 and data.get('fresh') is True
            and isinstance(seconds,(int,float)) and math.isfinite(seconds)
            and 0 <= seconds < 8)


def low_batteries(data, source_age):
    if not data_fresh(data, source_age):
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


def charging_detected(data, source_age):
    if not data_fresh(data,source_age): return None
    valid=[b for b in data.get('batteries',[]) if b.get('id') in (1,2)
           and b.get('is_connected') is True and b.get('is_in_place') is True
           and b.get('error_code',0)==0 and isinstance(b.get('is_charging'),bool)]
    if any(b['is_charging'] for b in valid): return True
    return False if len({b['id'] for b in valid})==2 else None


class Schedule:
    def __init__(self): self.last_started = float('-inf')
    def due(self, low, now): return bool(low) and now-self.last_started >= INTERVAL
    def started(self, now): self.last_started = now


class AlarmPolicy(Schedule):
    def __init__(self, latched=False):
        super().__init__()
        self.latched=latched

    def observe(self,low,charging):
        # Once triggered, retain the warning until fresh charging confirmation.
        # Losing telemetry or a fluctuating SOC is not a charging event.
        if charging is True: self.latched=False
        elif low: self.latched=True
        return self.latched

    def due(self,now): return super().due(self.latched,now)


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def load_policy():
    policy=AlarmPolicy()
    try:
        saved=json.loads((RUNTIME/'latch.json').read_text())
        if saved.get('boot_id')==boot_id():
            policy.latched=saved.get('latched') is True
            started=saved.get('last_started_mono')
            if isinstance(started,(int,float)) and 0 <= started <= time.monotonic():
                policy.last_started=started
    except (OSError,ValueError,TypeError): pass
    return policy


def save_policy(policy):
    target=RUNTIME/'latch.json'
    last=policy.last_started if math.isfinite(policy.last_started) else None
    data=json.dumps({'boot_id':boot_id(),'latched':policy.latched,'last_started_mono':last})
    if target.exists() and target.read_text()==data: return
    temp=target.with_suffix('.tmp');temp.write_text(data);temp.replace(target)


def log(event, **fields):
    print(json.dumps({'event':event,'wall_time':datetime.now().astimezone().isoformat(),
                      'mono':time.monotonic(),**fields},ensure_ascii=False),flush=True)


def read_feedback():
    try:
        age=time.time()-SOURCE.stat().st_mtime
        data=json.loads(SOURCE.read_text(encoding='utf-8'))
        return low_batteries(data,age),charging_detected(data,age),data_fresh(data,age)
    except (OSError,ValueError,TypeError,AttributeError): return [],None,False


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
    schedule=load_policy()
    proc=None
    lock=None
    starts=0
    last_error=None
    try:
        while not stopping:
            now=time.monotonic()
            low,charging,fresh=read_feedback()
            was_latched=schedule.latched
            schedule.observe(low,charging)
            if was_latched and not schedule.latched:
                log('charging_started_alarm_cleared')
            save_policy(schedule)
            if proc is not None:
                if charging is True and proc.poll() is None:
                    proc.terminate()
                    log('playback_cancelled',reason='charging detected')
                if now-schedule.last_started>8 and proc.poll() is None:
                    proc.kill()
                    last_error='Audio playback timed out'
                if proc.poll() is not None:
                    _,stderr=proc.communicate(timeout=1)
                    if proc.returncode and schedule.latched:
                        last_error=stderr.decode(errors='replace') or str(proc.returncode)
                    log('playback_finished',returncode=proc.returncode,error=last_error)
                    proc=None
                    lock.close();lock=None
            if proc is None and schedule.due(now):
                candidate=(RUNTIME/'playback.lock').open('a')
                try:
                    fcntl.flock(candidate,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:
                    candidate.close()
                else:
                    try:
                        proc=play();lock=candidate
                        schedule.started(time.monotonic());starts+=1;last_error=None
                        save_policy(schedule)
                        log('low_battery_playback_started',low_batteries=low,playback_count=starts)
                    except OSError as exc:
                        candidate.close();last_error=str(exc);schedule.started(now)
                        save_policy(schedule)
            status({'message':'warning，请立即充电','threshold_percent':30,'repeat_seconds':INTERVAL,
                    'low_batteries':low,'playing':proc is not None,'live_playback_count':starts,
                    'alarm_latched':schedule.latched,'charging_detected':charging,'source_fresh':fresh,
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
