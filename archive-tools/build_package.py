"""Create the complete ZIP and its manifest; no network or robot access."""
from pathlib import Path
import hashlib
import json
import zipfile
import time

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_FILES = {'prepublish-secret-scan.json', 'publication-result.json', 'manifests/FILE-MANIFEST.json'}
def included(p):
    rel = p.relative_to(ROOT)
    return not any(x in {'.git', 'archives'} for x in rel.parts) and rel.as_posix() not in EXCLUDE_FILES

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

files = sorted(p for p in ROOT.rglob('*') if p.is_file() and included(p))
entries = [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in files]
manifest = ROOT / 'manifests/FILE-MANIFEST.json'
manifest.write_text(json.dumps({'note': 'Manifest excludes itself, Git metadata, output archives and post-publication receipt.',
    'files': entries, 'file_count': len(entries), 'total_bytes': sum(e['bytes'] for e in entries)}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
files.append(manifest)
out = ROOT / 'archives'
out.mkdir(exist_ok=True)
archive = out / 'Getoluna-STB-20261124-complete.zip'
last = time.monotonic()
with zipfile.ZipFile(archive, 'w', allowZip64=True, compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for i, p in enumerate(files, 1):
        store = p.suffix.lower() in {'.zip', '.gz', '.png', '.jpg', '.jpeg', '.gif', '.apk', '.deb', '.exe', '.dll', '.pdf', '.jar'}
        z.write(p, p.relative_to(ROOT).as_posix(), compress_type=zipfile.ZIP_STORED if store else zipfile.ZIP_DEFLATED)
        if time.monotonic() - last > 15:
            print(json.dumps({'packing': i, 'of': len(files), 'archive_bytes': archive.stat().st_size}), flush=True)
            last = time.monotonic()
with zipfile.ZipFile(archive) as z:
    bad = z.testzip()
    assert bad is None, bad
    for e in entries:
        i = z.getinfo(e['path'])
        assert i.file_size == e['bytes'], e['path']
assert archive.stat().st_size < 2 * 1024**3, 'Release assets must be smaller than 2 GiB'
checksum = sha(archive)
(out / 'SHA256SUMS.txt').write_text(checksum + '  ' + archive.name + '\n' + sha(manifest) + '  FILE-MANIFEST.json\n', encoding='ascii')
(out / 'package-result.json').write_text(json.dumps({'archive': archive.name, 'bytes': archive.stat().st_size, 'sha256': checksum,
    'zip_crc_verified': True, 'archive_entries': len(files), 'manifest_files': len(entries)}, indent=2) + '\n', encoding='utf-8')
print((out / 'package-result.json').read_text(), flush=True)
