"""Index frozen evidence in the local archive repository; never deploy files."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

REPO = Path(__file__).resolve().parents[1]
ARCHIVE = REPO / 'archives' / '20261125-apex-impedance-frozen'
HISTORY = REPO / 'manifests' / 'history' / '20261125-before-apex-freeze'


def digest(data):
    return hashlib.sha256(data).hexdigest()


conflicts = []


def save(relative, data):
    dest = (REPO / relative).resolve()
    if not dest.is_relative_to(REPO.resolve()):
        raise RuntimeError('Archive destination escaped repository')
    if dest.exists():
        prior = dest.read_bytes()
        if prior == data:
            return
        old = HISTORY / relative
        if old.exists() and old.read_bytes() != prior:
            old = old.with_name(old.name + '.' + digest(prior)[:12])
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_bytes(prior)
        conflicts.append({'path': relative, 'previous_copy': old.relative_to(REPO).as_posix(),
                          'previous_sha256': digest(prior), 'current_sha256': digest(data)})
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


for folder in sorted(Path('E:/Github/Mubea-EV-Gentoluna-tests').glob('20261125-*')):
    for source in sorted(folder.rglob('*')):
        if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc':
            save('tests/' + folder.name + '/' + source.relative_to(folder).as_posix(), source.read_bytes())

previous = json.loads((REPO / 'manifests/robot-active-file-consistency.json').read_text())['files']
mapping = [{'robot_path': row['robot_path'], 'repo_path': row['repo_path']} for row in previous]
mapping += [
    {'robot_path': '/opt/kernelmind/apex/install/apex_backend/lib/python3.10/site-packages/apex_backend/ros_state.py', 'repo_path': 'current-config/apex-ros_state.py'},
    {'robot_path': '/opt/kernelmind/apex/install/marvin_ros_control/lib/marvin_ros_control/marvin_robot_node', 'repo_path': 'current-config/marvin_robot_node'},
]
by_member = {'robot/' + row['robot_path'].lstrip('/'): row for row in mapping}
with tarfile.open(ARCHIVE / 'robot/robot-apex-runtime-and-records.tar.gz', 'r|gz') as tar:
    prefix = 'robot/home/nvidia/luna-test-runs/'
    for member in tar:
        if not member.isfile():
            continue
        record = by_member.get(member.name)
        relative = None
        if record:
            relative = record['repo_path']
        elif member.name.startswith(prefix + '20261125-'):
            suffix = member.name[len(prefix):]
            if not any(part in ('build', '__pycache__') for part in Path(suffix).parts) and not suffix.endswith('.pyc'):
                relative = 'tests/' + suffix
        if relative:
            data = tar.extractfile(member).read()
            save(relative, data)
            if record:
                record.update(sha256=digest(data), bytes=len(data), snapshot_member=member.name)
if any('sha256' not in row for row in mapping):
    raise RuntimeError('A current deployed file was not found in the snapshot')
for source in (ARCHIVE / 'local-attachments').glob('*'):
    save('attachments/20261125-apex/' + source.name, source.read_bytes())
save('docs/AGENTS.md', Path('C:/Users/Wang Bo/OneDrive/Documents/ChatGPT/Mubea 弹簧开发/AGENTS.md').read_bytes())
for side in ('robot', 'windows'):
    for name in ('snapshot-manifest.json', 'archive-verification.json', 'capture-spec.json'):
        save('manifests/20261125-apex-frozen/' + side + '/' + name, (ARCHIVE / side / name).read_bytes())
for source in (ARCHIVE / 'robot/metadata').glob('*'):
    save('manifests/20261125-apex-frozen/robot-metadata/' + source.name, source.read_bytes())
result = {'files': mapping, 'prior_copies_preserved': conflicts,
          'runtime_files_modified': False, 'source': str(ARCHIVE),
          'note': 'Repository current-config files are archival mirrors. Runtime and installation paths were not written.'}
save('manifests/20261125-apex-frozen/active-file-mapping.json', json.dumps(result, ensure_ascii=False, indent=2).encode())
print(json.dumps({'current_files': len(mapping), 'previous_copies_preserved': len(conflicts)}, ensure_ascii=False))
