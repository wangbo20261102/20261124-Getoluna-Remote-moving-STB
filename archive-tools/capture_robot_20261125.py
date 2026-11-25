"""Run on the robot: read-only scoped snapshot, with no control/enable commands."""
from pathlib import Path
import hashlib, json, os, shutil, subprocess, time, tarfile

ROOT = Path('/home/nvidia/luna-archive-exports/20261125-connected-sync')
SNAP = ROOT / 'robot-snapshot/20261125-connected'
SNAP.mkdir(parents=True, exist_ok=True)
entries, errors = [], []

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()

def copy(src, rel):
    src=Path(src); dst=SNAP/rel
    try:
        if src.is_symlink():
            entries.append({'source':str(src),'path':str(rel),'symlink_target':os.readlink(src)})
            return
        before=src.stat(); dst.parent.mkdir(parents=True,exist_ok=True)
        h=hashlib.sha256();remaining=before.st_size
        with src.open('rb') as f,dst.open('wb') as out:
            while remaining:
                b=f.read(min(4*1024*1024,remaining))
                if not b: break
                out.write(b);h.update(b);remaining-=len(b)
        after=src.stat()
        entries.append({'source':str(src),'path':Path(rel).as_posix(),'bytes':dst.stat().st_size,
            'sha256':h.hexdigest(),'source_bytes_before':before.st_size,'source_bytes_after':after.st_size,
            'source_stable':before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns,
            'copy_complete_to_initial_size':remaining==0})
    except Exception as exc: errors.append({'source':str(src),'error':str(exc)})

def tree(src,rel):
    src=Path(src)
    for base,dirs,files in os.walk(src,followlinks=False):
        dirs[:]=[d for d in dirs if d!='.git' and not (Path(base)/d).is_symlink()]
        for name in sorted(files):
            p=Path(base)/name;copy(p,Path(rel)/p.relative_to(src))

for p in sorted(Path('/home/nvidia/luna-test-runs').iterdir()):
    if p.is_dir() and p.name.startswith(('20261124','20261125')):
        tree(p,Path('test-runs')/p.name)
tree('/home/nvidia/luna-ready-20261123','ready-scripts')
tree('/home/nvidia/d435-preview','d435-preview')
tree('/usr/local/lib/luna-apex-wrist','wrist-installed')
for base in [Path('/var/log/apex/ros'),Path('/home/nvidia/.ros/log')]:
    if base.exists():
        for p in sorted(base.iterdir()):
            if p.is_dir() and p.name.startswith(('2026-11-24','2026-11-25')):
                tree(p,Path('persistent-ros-logs')/base.parent.name/p.name)
    if base.exists():
        for p in sorted(base.iterdir()):
            if p.is_file():
                stamp=time.strftime('%Y-%m-%d',time.localtime(p.stat().st_mtime))
                if stamp in ['2026-11-24','2026-11-25']:
                    copy(p,Path('persistent-ros-logs')/base.parent.name/'node-log-files'/p.name)

installed=[
'/opt/kernelmind/apex/install/marvin_teleop/share/marvin_teleop/config/luna/robot_param.yaml',
'/opt/kernelmind/apex/install/marvin_teleop/lib/marvin_teleop/controller_udp.py',
'/opt/kernelmind/apex/install/marvin_teleop/lib/marvin_teleop/elbow_home_alignment.py',
'/opt/kernelmind/apex/install/marvin_ros_control/share/marvin_ros_control/config/robot_param_luna.yaml',
'/opt/kernelmind/apex/install/marvin_ros_control/share/marvin_ros_control/launch/bringup_control_gento_luna.launch.py',
'/opt/kernelmind/apex/install/marvin_teleop/share/marvin_teleop/launch/teleop_luna.launch.py',
'/opt/kernelmind/apex/install/marvin_qp_controller/share/marvin_qp_controller/config/luna/robot_param.yaml',
'/opt/kernelmind/apex/install/marvin_qp_controller/share/marvin_qp_controller/config/luna/ik_tasks.yaml',
'/opt/kernelmind/apex/install/marvin_qp_controller/share/marvin_qp_controller/config/luna/collision_pairs.json',
'/usr/local/sbin/luna-maxhub-prepare',
'/etc/systemd/system/apex-camera.service.d/60-d435.conf',
'/etc/systemd/system/apex-camera.service.d/70-d435-device.conf',
'/home/nvidia/.config/systemd/user/luna-maxhub-client.service',
'/home/nvidia/.config/systemd/user/luna-camera-fast-marmots.service',
'/home/nvidia/.config/systemd/user/luna-battery-voice-warning.service',
'/home/nvidia/.config/systemd/user/luna-pico-manual-chassis-20261124.service',
]
for p in installed:
    if Path(p).exists(): copy(p,Path('installed')/p.lstrip('/'))
    else: errors.append({'source':p,'error':'not present at this known path'})

def command(name,args):
    try:
        p=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=35)
        (SNAP/'evidence').mkdir(exist_ok=True)
        (SNAP/'evidence'/name).write_text(p.stdout)
        return {'returncode':p.returncode,'bytes':len(p.stdout.encode())}
    except Exception as e:return {'error':str(e)}

commands={
'service-state.txt':['systemctl','show','apex-camera.service','apex-robot.service','apex-teleop.service','apex-tool.service','-p','Id','-p','ActiveState','-p','MainPID','-p','UnitFileState','-p','ExecMainStartTimestamp'],
'user-service-state.txt':['systemctl','--user','show','luna-maxhub-client.service','luna-camera-fast-marmots.service','luna-battery-voice-warning.service','-p','Id','-p','ActiveState','-p','MainPID','-p','UnitFileState'],
'camera-unit.txt':['systemctl','cat','apex-camera.service'],
'robot-unit.txt':['systemctl','cat','apex-robot.service'],
'boot-history.txt':['journalctl','--list-boots','--no-pager'],
'manual-chassis-unit.txt':['systemctl','--user','show','luna-pico-manual-chassis-20261124.service','-p','LoadState','-p','ActiveState','-p','FragmentPath'],
'journal-20261124.txt':['journalctl','--since','2026-11-24 00:00:00','--until','2026-11-25 00:00:00','-u','apex-robot.service','-u','apex-teleop.service','-u','apex-tool.service','-u','apex-camera.service','--no-pager'],
'journal-20261125.txt':['journalctl','-b','-u','apex-robot.service','-u','apex-teleop.service','-u','apex-tool.service','-u','apex-camera.service','--no-pager'],
'video-devices.txt':['v4l2-ctl','--list-devices'],
'usb-devices.txt':['lsusb'],
'display.txt':['env','DISPLAY=:0','XAUTHORITY=/run/luna-maxhub/Xauthority','xrandr','--query'],
}
command_results={n:command(n,a) for n,a in commands.items()}
for p in ['/run/luna-battery-screen/status.json','/run/user/1000/luna-maxhub-client/status.json',
          '/run/user/1000/luna-camera-fast-marmots/display-state.json','/run/user/1000/luna-camera-fast-marmots/animation-state.json',
          '/run/user/1000/luna-battery-voice-warning/status.json']:
    if Path(p).exists():copy(p,Path('runtime')/p.lstrip('/'))
manifest={'captured_at_unix':time.time(),'entries':entries,'errors':errors,'commands':command_results,
          'motion_commands_sent':False,'services_restarted':False,'mutable_logs_are_bounded_snapshots':True}
(SNAP/'ROBOT-FILE-MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
archive=ROOT/'robot-connected-snapshot.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=4) as t:t.add(ROOT/'robot-snapshot',arcname='robot-snapshot')
result={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':digest(archive),
        'files':len(entries),'source_bytes':sum(x.get('bytes',0) for x in entries),'errors':errors}
(ROOT/'capture-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
