"""Verify, merge and index a read-only robot snapshot; never deploys to the robot."""
from pathlib import Path
import hashlib,json,shutil,tarfile,gzip

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def put_json(p,o):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

result=json.loads((ROOT/'archives/robot-capture-result-20261125.json').read_text())
archive=ROOT/'archives/robot-connected-snapshot-20261125.tar.gz'
assert sha(archive)==result['sha256']
for name in ['FILE-MANIFEST.json','collection-status.json','source-copies.json']:
 src=ROOT/'manifests'/name;dst=ROOT/'manifests/history'/('20261124-'+name)
 if src.exists() and not dst.exists():dst.parent.mkdir(exist_ok=True);shutil.copy2(src,dst)
with tarfile.open(archive) as t:t.extractall(ROOT,filter='data')
snap=ROOT/'robot-snapshot/20261125-connected'
m=json.loads((snap/'ROBOT-FILE-MANIFEST.json').read_text())
fail=[]
for e in m['entries']:
 if 'sha256' not in e:continue
 p=snap/e['path']
 if not p.is_file() or sha(p)!=e['sha256']:fail.append(e['path'])
assert not fail,fail
conflicts=[]
def merge_file(src,dst):
 if dst.exists() and sha(src)!=sha(dst):
  old=ROOT/'history/local-before-robot-sync'/dst.relative_to(ROOT)
  if not old.exists():old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,old)
  conflicts.append(dst.relative_to(ROOT).as_posix())
 dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists() or sha(src)!=sha(dst):shutil.copyfile(src,dst)

for src in (snap/'test-runs').rglob('*'):
 if src.is_file():merge_file(src,ROOT/'tests'/src.relative_to(snap/'test-runs'))
for d in Path('E:/Github/Mubea-EV-Gentoluna-tests').glob('20261125*'):
 for src in d.rglob('*'):
  if src.is_file() and '__pycache__' not in src.parts:merge_file(src,ROOT/'tests'/d.name/src.relative_to(d))

active={
'teleop-robot_param.yaml':'installed/opt/kernelmind/apex/install/marvin_teleop/share/marvin_teleop/config/luna/robot_param.yaml',
'robot-control.yaml':'installed/opt/kernelmind/apex/install/marvin_ros_control/share/marvin_ros_control/config/robot_param_luna.yaml',
'controller_udp.py':'installed/opt/kernelmind/apex/install/marvin_teleop/lib/marvin_teleop/controller_udp.py',
'elbow_home_alignment.py':'installed/opt/kernelmind/apex/install/marvin_teleop/lib/marvin_teleop/elbow_home_alignment.py',
'libGentoSDK.release-fix.so':'wrist-installed/sdk/libGentoSDK.so',
'calibration.json':'test-runs/20261124-elbow-home-alignment/calibration.json',
'pico_chassis_bridge.py':'test-runs/20261124-full-body-cooperation/pico_chassis_bridge.py',
'start_manual_chassis.sh':'test-runs/20261124-full-body-cooperation/start_manual_chassis.sh',
'animations.json':'test-runs/20261124-camera-fast-marmots/animations.json',
'camera-preview.py':'test-runs/20261124-camera-fast-marmots/camera-preview.py',
'preview_guard.py':'test-runs/20261124-camera-fast-marmots/preview_guard.py',
'battery_voice.py':'test-runs/20261124-battery-voice-charging-stop/battery_voice.py',
'camera-color1080.yaml':'d435-preview/apex-color1080.yaml',
'resolve_color_camera.py':'test-runs/20261125-camera-device-fix/resolve_color_camera.py',
'maxhub_client_guard.py':'test-runs/20261125-maxhub-startup-fix/maxhub_client_guard.py',
'start-maxhub.sh':'ready-scripts/start-maxhub.sh',
'70-d435-device.conf':'installed/etc/systemd/system/apex-camera.service.d/70-d435-device.conf',
'luna-maxhub-client.service':'installed/home/nvidia/.config/systemd/user/luna-maxhub-client.service',
'luna-camera-fast-marmots.service':'installed/home/nvidia/.config/systemd/user/luna-camera-fast-marmots.service',
'luna-battery-voice-warning.service':'installed/home/nvidia/.config/systemd/user/luna-battery-voice-warning.service',
}
source_index={e['path']:e for e in m['entries']}
verification=[]
for name,rel in active.items():
 src=snap/rel;assert src.is_file(),str(src)
 dst=ROOT/'current-config'/name;merge_file(src,dst)
 entry=source_index[rel]
 assert sha(dst)==entry['sha256']
 verification.append({'robot_path':entry['source'],'repo_path':dst.relative_to(ROOT).as_posix(),'sha256':sha(dst),'snapshot_source_stable':entry['source_stable'],'matches':True})

ignore=(ROOT/'.gitignore').read_text()
if '/robot-snapshot/' not in ignore:ignore+='\n/robot-snapshot/\n/publication-*.json\n'
large=[]
for p in (ROOT/'tests').rglob('*'):
 if p.is_file() and p.stat().st_size>=95_000_000:
  rel=p.relative_to(ROOT).as_posix();gz=p.with_name(p.name+'.gz')
  with p.open('rb') as f,gzip.open(gz,'wb',compresslevel=6) as out:shutil.copyfileobj(f,out)
  if '/'+rel+'\n' not in ignore:ignore+='/'+rel+'\n'
  large.append({'raw_path':rel,'git_browsable_compressed_path':gz.relative_to(ROOT).as_posix(),'raw_sha256':sha(p),'raw_bytes':p.stat().st_size})
(ROOT/'.gitignore').write_text(ignore)
put_json(ROOT/'manifests/robot-snapshot-files.json',m)
put_json(ROOT/'manifests/robot-active-file-consistency.json',{'files':verification,'all_match':True,'note':'Installed/stored file identity, not proof of live loading by stopped Robot/Teleop services.'})
put_json(ROOT/'manifests/robot-sync-merge.json',{'capture':result,'historical_conflicts_preserved':conflicts,'large_files':large,'robot_originals_changed':False})
put_json(ROOT/'manifests/collection-status.json',{'date':'2026-11-25','robot_new_capture':True,'robot_source_files':len(m['entries']),'robot_snapshot_sha256':result['sha256'],'snapshot_errors':m['errors'],'closed_gap':'Previously unsynchronized on-robot test runs, deployment scripts, telemetry, installed files and retained ROS logs collected.','unrecoverable_gap':'No Nov 24 systemd journal entries remain; preserved historical diagnostic journal exports and ROS log files included.','runtime_limit':'Robot/Teleop stopped at inspection; no forced enable, mode change or Home to verify controller live tool values. Manual chassis transient service absent after reboot; program remains.','base_release_unchanged':True})
print(json.dumps({'verified_robot_entries':len(m['entries']),'active_files_matching':len(verification),'historical_conflicts':len(conflicts),'large_files':large},ensure_ascii=False))
