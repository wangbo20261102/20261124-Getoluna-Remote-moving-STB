import pathlib,re,os,tempfile,json,subprocess,hashlib
base=pathlib.Path(__file__).parent
p=pathlib.Path('/opt/kernelmind/apex/install/marvin_teleop/share/marvin_teleop/config/luna/robot_param.yaml')
old=p.read_bytes();new=old
for name in (b'left_hand',b'right_hand'):
 pattern=rb'(?m)^(      '+name+rb': )1\.5(\r?)$'
 new,count=re.subn(pattern,rb'\g<1>1.0\2',new)
 if count!=1:raise SystemExit('Expected one 1.5 setting for '+name.decode())
backup=base/'robot_param.before.yaml'
if backup.exists():raise SystemExit('Backup already exists; inspect before repeating')
backup.write_bytes(old)
s=p.stat();fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.hand-scale-')
try:
 with os.fdopen(fd,'wb') as f:f.write(new);f.flush();os.fsync(f.fileno())
 os.chmod(tmp,s.st_mode);os.chown(tmp,s.st_uid,s.st_gid);os.replace(tmp,p)
finally:
 if os.path.exists(tmp):os.unlink(tmp)
(base/'robot_param.after.yaml').write_bytes(new)
subprocess.run(['systemctl','restart','apex-teleop.service'],check=True)
r={'left_hand':1.0,'right_hand':1.0,'other_yaml_bytes_unchanged':True,'old_sha256':hashlib.sha256(old).hexdigest(),'new_sha256':hashlib.sha256(new).hexdigest(),'reloaded':'apex-teleop.service','robot_service_restarted':False}
(base/'change-result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
