import pathlib,json,hashlib,os,shutil,tempfile,subprocess
base=pathlib.Path(__file__).parent
paths={'controller_udp.py':pathlib.Path('/opt/kernelmind/apex/install/marvin_teleop/lib/marvin_teleop/controller_udp.py'),'robot_param.yaml':pathlib.Path('/opt/kernelmind/apex/install/marvin_teleop/share/marvin_teleop/config/luna/robot_param.yaml')}
expected=json.loads((base/'expected-before.json').read_text())
for name,dest in paths.items():
 if hashlib.sha256(dest.read_bytes()).hexdigest()!=expected[name]:raise SystemExit('Source changed: '+name)
backup=base/'installed-before';backup.mkdir(exist_ok=False)
for name,dest in paths.items():shutil.copy2(dest,backup/name)
module=paths['controller_udp.py'].with_name('elbow_home_alignment.py')
if module.exists():raise SystemExit('Unexpected existing alignment module')
# Files and backup are complete before the coordinated reader reload.
for name,dest in {**paths,'elbow_home_alignment.py':module}.items():
 data=(base/name).read_bytes();fd,tmp=tempfile.mkstemp(dir=dest.parent,prefix='.elbow-home-')
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(tmp,0o755 if name=='controller_udp.py' else 0o644);os.chown(tmp,0,0);os.replace(tmp,dest)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
subprocess.run(['systemctl','restart','apex-teleop.service'],check=True)
r={'installed':True,'files':{name:str(dest) for name,dest in {**paths,'elbow_home_alignment.py':module}.items()},'robot_restarted':False,'home_sent':False,'other_ik_tasks_modified':False}
(base/'deployment.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
