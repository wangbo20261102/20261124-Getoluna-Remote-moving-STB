"""Install or roll back only the private wrist SDK, with Robot and Tool stopped."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile

BASE=pathlib.Path('/home/nvidia/luna-test-runs/20261124-gripper-release-fix')
DEST=pathlib.Path('/usr/local/lib/luna-apex-wrist/sdk/libGentoSDK.so')
OLD='4cdbe4a52db7361891be7b05040574577625d58b59ab8a353ec3220cc1a3bbaf'
NEW='07cecbce36ebcd89e915cf5a7f274db2159251f68dcab83d707a5d3f7a85aa43'
rollback=len(sys.argv)==2 and sys.argv[1]=='--rollback'
if len(sys.argv)>1 and not rollback:raise SystemExit('Invalid arguments')
if os.geteuid()!=0:raise SystemExit('Run as root')
for service in ('apex-robot','apex-tool'):
    if subprocess.run(['systemctl','is-active','--quiet',service]).returncode==0:
        raise SystemExit('Refusing to replace SDK while '+service+' is active')
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected=json.loads((BASE/'protected-settings-sha256.json').read_text())
if any(digest(pathlib.Path(p))!=h for p,h in expected.items()):
    raise SystemExit('Protected settings changed; inspect before continuing')
source=BASE/('before/libGentoSDK.so' if rollback else 'candidate-build/libGentoSDK.so')
want=OLD if rollback else NEW
if digest(source)!=want:raise SystemExit('Source SDK checksum mismatch')
current=digest(DEST)
if current not in (OLD,NEW):raise SystemExit('Unexpected installed SDK; refusing overwrite')
if current==want:raise SystemExit('Requested version already installed')
backup=DEST.with_name('libGentoSDK.before-release-fix-20261124.so')
if not backup.exists():
    if current!=OLD:raise SystemExit('Original backup missing')
    shutil.copy2(DEST,backup)
if digest(backup)!=OLD:raise SystemExit('Original backup checksum mismatch')
fd,name=tempfile.mkstemp(prefix='.release-fix-',dir=DEST.parent)
try:
    with os.fdopen(fd,'wb') as stream:
        stream.write(source.read_bytes());stream.flush();os.fsync(stream.fileno())
    os.chmod(name,0o644);os.chown(name,0,0)
    if digest(pathlib.Path(name))!=want:raise RuntimeError('Staged checksum mismatch')
    os.replace(name,DEST)
    directory=os.open(DEST.parent,os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
finally:
    if os.path.exists(name):os.unlink(name)
print(json.dumps({'installed_sha256':digest(DEST),'rollback':rollback,'settings_unchanged':True}))
