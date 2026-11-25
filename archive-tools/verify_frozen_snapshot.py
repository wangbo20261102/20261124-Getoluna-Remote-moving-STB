"""Verify every captured file/link against a frozen snapshot manifest."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile


def verify(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'snapshot-manifest.json').read_text(encoding='utf-8-sig'))
    archive = folder / manifest['archive']['name']
    h = hashlib.sha256()
    with archive.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    if h.hexdigest() != manifest['archive']['sha256']:
        raise RuntimeError('Archive SHA-256 mismatch')
    expected = {f['archive_path']: f for f in manifest['files']}
    checked = 0
    with tarfile.open(archive, 'r|gz') as tar:
        for member in tar:
            if member.name == 'SNAPSHOT-MANIFEST.json' or member.isdir():
                continue
            row = expected.pop(member.name)
            if row['kind'] == 'file':
                if not member.isfile() or member.size != row['bytes']:
                    raise RuntimeError('File metadata mismatch: ' + member.name)
                h = hashlib.sha256()
                with tar.extractfile(member) as f:
                    for block in iter(lambda: f.read(1024*1024), b''):
                        h.update(block)
                if h.hexdigest() != row['sha256']:
                    raise RuntimeError('File SHA-256 mismatch: ' + member.name)
            elif row['kind'] in ('symlink', 'hardlink'):
                if member.linkname != row['target']:
                    raise RuntimeError('Link mismatch: ' + member.name)
            checked += 1
    if expected or manifest['errors']:
        raise RuntimeError('Missing entries or capture errors')
    result = {'verified': True, 'archive': manifest['archive'], 'entries_verified': checked,
              'source_changed_during_capture': sum(bool(f.get('source_changed_during_capture')) for f in manifest['files']),
              'source_truncated_during_capture': sum(bool(f.get('truncated_during_capture')) for f in manifest['files'])}
    (folder / 'archive-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    for folder in sys.argv[1:]:
        verify(folder)
