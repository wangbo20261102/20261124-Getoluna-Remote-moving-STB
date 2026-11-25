import pathlib,re,os,json,hashlib,subprocess,tempfile
base=pathlib.Path(__file__).parent
p=pathlib.Path('/opt/kernelmind/apex/install/marvin_teleop/share/marvin_teleop/config/luna/robot_param.yaml')
cal=pathlib.Path('/home/nvidia/luna-test-runs/20261124-elbow-home-alignment/calibration.json')
cal_before=hashlib.sha256(cal.read_bytes()).hexdigest()
old=p.read_bytes();new=old
for name in (b'left_elbow',b'right_elbow'):
 new,count=re.subn(rb'(?m)^(      '+name+rb': )1\.0(\r?)$',rb'\g<1>1.2\2',new)
 if count!=1:raise SystemExit('Unexpected elbow scaling')
backup=base/'robot_param.before.yaml'
if backup.exists():raise SystemExit('Backup exists; inspect before repeating')
backup.write_bytes(old);s=p.stat();fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.elbow-scale-')
try:
 with os.fdopen(fd,'wb') as f:f.write(new);f.flush();os.fsync(f.fileno())
 os.chmod(tmp,s.st_mode);os.chown(tmp,s.st_uid,s.st_gid);os.replace(tmp,p)
finally:
 if os.path.exists(tmp):os.unlink(tmp)
(base/'robot_param.after.yaml').write_bytes(new)
subprocess.run(['systemctl','restart','apex-teleop.service'],check=True)
r={'left_elbow':1.2,'right_elbow':1.2,'other_yaml_bytes_unchanged':True,'home_calibration_unchanged':cal_before==hashlib.sha256(cal.read_bytes()).hexdigest(),'motion_test_started':False,'home_sent':False}
(base/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
