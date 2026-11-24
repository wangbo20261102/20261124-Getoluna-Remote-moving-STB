"""One supervised 300-second chassis-only trial, with no arm commands."""
import json,os,pathlib,signal,subprocess,time,urllib.request
import rclpy
from rclpy.qos import QoSProfile,ReliabilityPolicy
from sensor_msgs.msg import Joy
from std_msgs.msg import Bool

BASE=pathlib.Path(__file__).resolve().parent
stopping=False
def stop(signum,frame):
    global stopping
    stopping=True
for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,stop)

def get_status():
    with urllib.request.urlopen('http://127.0.0.1:8080/api/v1/robot/status',timeout=2) as response:
        return json.load(response)['data']

def check_status():
    result=get_status()
    if result.get('control_error') or result.get('arm_state_age_sec',99)>1 or result.get('arm_state',[])[:2]!=[2,2]:
        raise RuntimeError('Robot holding state is not healthy: '+json.dumps(result))
    for svc in ('apex-teleop','apex-tool'):
        if subprocess.run(['systemctl','is-active','--quiet',svc]).returncode==0:
            raise RuntimeError('Arm/gripper input service unexpectedly active: '+svc)
    return result

if (BASE/'telemetry.jsonl').exists():raise SystemExit('Refusing to overwrite or append a previous trial')
rclpy.init();node=rclpy.create_node('pico_chassis_trial_monitor')
qos=QoSProfile(depth=1,reliability=ReliabilityPolicy.BEST_EFFORT)
inputs={}
def receive(key,msg):inputs[key]=(time.monotonic(),msg)
for side,topic in [('left','/control/vr_joy_L'),('right','/control/vr_joy_R')]:
    node.create_subscription(Joy,topic,lambda m,k=side:receive(k,m),qos)
node.create_subscription(Bool,'/info/vr_connected',lambda m:receive('connected',m),10)

def vr_ready(neutral=False):
    now=time.monotonic()
    if any(k not in inputs or now-inputs[k][0]>1 for k in ('left','right','connected')):return False
    if not inputs['connected'][1].data:return False
    return not neutral or all(abs(v)<=.15 for k in ('left','right') for v in inputs[k][1].axes[:2])

proc=None;result={'planned_seconds':300,'completed':False,'reason':None}
try:
    ready_deadline=time.monotonic()+60
    while not stopping and not vr_ready(True):
        if time.monotonic()>ready_deadline:raise RuntimeError('No fresh centered PICO input')
        rclpy.spin_once(node,timeout_sec=.1)
    if stopping:raise RuntimeError('Stopped before start')
    result['initial_robot']=check_status()
    source=json.loads(pathlib.Path('/run/luna-battery-screen/status.json').read_text())
    if not source.get('fresh') or any(b['energy']<30 or b['is_charging'] for b in source['batteries']):
        raise RuntimeError('Battery state is low, charging, or stale')
    result['initial_batteries']=source
    print('READY: fresh centered PICO; arms holding; Teleop/Tool off; starting full 300 seconds',flush=True)
    with (BASE/'console.log').open('wb') as console, (BASE/'safety-monitor.jsonl').open('w',buffering=1) as monitor:
        proc=subprocess.Popen(['/usr/bin/python3',str(BASE/'pico_chassis_bridge.py'),'--live',
            '--left-forward','2','--left-lateral','-1','--right-turn','-1',
            '--record',str(BASE/'telemetry.jsonl')],stdout=console,stderr=subprocess.STDOUT,start_new_session=True)
        wait=time.monotonic()+8
        while not (BASE/'telemetry.jsonl').exists():
            if proc.poll() is not None or time.monotonic()>wait:raise RuntimeError('Bridge failed to start')
            rclpy.spin_once(node,timeout_sec=.1)
        first=json.loads((BASE/'telemetry.jsonl').open().readline())
        result['start_mono']=first['mono'];deadline=first['mono']+300
        result['start_robot_wall']=first['time']
        next_check=0;next_progress=first['mono']+30;last_vr=time.monotonic()
        while not stopping and time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.05)
            now=time.monotonic()
            if proc.poll() is not None:raise RuntimeError('Bridge exited early')
            if vr_ready():last_vr=now
            if now-last_vr>2:raise RuntimeError('PICO input disconnected for more than 2 seconds')
            if now>=next_check:
                robot=check_status()
                batteries=json.loads(pathlib.Path('/run/luna-battery-screen/status.json').read_text())
                if batteries.get('fresh') and any(b['energy']<30 for b in batteries['batteries']):
                    raise RuntimeError('Battery fell below 30 percent')
                monitor.write(json.dumps({'mono':now,'elapsed':now-first['mono'],'robot':robot,
                    'batteries':batteries,'joy_ages':{k:now-v[0] for k,v in inputs.items()}})+'\n')
                next_check=now+1
            if now>=next_progress:
                print('RUNNING elapsed='+str(round(now-first['mono'],1))+' seconds',flush=True)
                next_progress+=30
        result['completed']=not stopping and time.monotonic()>=deadline
        result['reason']='timer_complete' if result['completed'] else 'operator_stop'
except BaseException as exc:
    result['reason']=str(exc)
    print('TRIAL STOP: '+str(exc),flush=True)
finally:
    if proc is not None:
        if proc.poll() is None:os.killpg(proc.pid,signal.SIGINT)
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=2)
        result['bridge_exit_code']=proc.returncode
    result['end_mono']=time.monotonic()
    (BASE/'run-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    node.destroy_node();rclpy.try_shutdown()
    print(json.dumps({k:result[k] for k in ('completed','reason')}) ,flush=True)
