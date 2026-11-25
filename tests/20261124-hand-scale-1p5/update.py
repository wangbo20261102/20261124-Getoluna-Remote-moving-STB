import pathlib,re,json,hashlib,os,tempfile,subprocess
b=pathlib.Path(__file__).parent;p=pathlib.Path('/opt/kernelmind/apex/install/marvin_teleop/share/marvin_teleop/config/luna/robot_param.yaml')
cal=pathlib.Path('/home/nvidia/luna-test-runs/20261124-elbow-home-alignment/calibration.json');cal_hash=hashlib.sha256(cal.read_bytes()).hexdigest()
old=p.read_bytes();new=old
for name in (b'left_hand',b'right_hand'):
 new,count=re.subn(rb'(?m)^(      '+name+rb': )1\.0(\r?)$',rb'\g<1>1.5\2',new)
 if count!=1:raise SystemExit('Unexpected hand scaling')
backup=b/'robot_param.before.yaml'
if backup.exists():raise SystemExit('Backup already exists')
backup.write_bytes(old);s=p.stat();fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.hand-scale-')
try:
 with os.fdopen(fd,'wb') as f:f.write(new);f.flush();os.fsync(f.fileno())
 os.chmod(tmp,s.st_mode);os.chown(tmp,s.st_uid,s.st_gid);os.replace(tmp,p)
finally:
 if os.path.exists(tmp):os.unlink(tmp)
(b/'robot_param.after.yaml').write_bytes(new)
subprocess.run(['systemctl','restart','apex-teleop.service'],check=True)
r={'left_hand':1.5,'right_hand':1.5,'other_yaml_bytes_unchanged':True,'calibration_unchanged':cal_hash==hashlib.sha256(cal.read_bytes()).hexdigest(),'motion_test_started':False,'home_sent':False}
(b/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
