"""Read-only SHA-256 verifier for the extracted complete archive or local copy."""
from pathlib import Path
import hashlib
import json
import sys

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'manifests/FILE-MANIFEST.json').read_text(encoding='utf-8'))
failed = []
for entry in manifest['files']:
    p = root / entry['path']
    h = hashlib.sha256()
    if not p.is_file():
        failed.append({'path': entry['path'], 'error': 'missing'})
        continue
    with p.open('rb') as f:
        for data in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(data)
    if h.hexdigest() != entry['sha256'] or p.stat().st_size != entry['bytes']:
        failed.append({'path': entry['path'], 'error': 'hash or size mismatch'})
print(json.dumps({'verified_files': len(manifest['files']), 'failed': failed}, ensure_ascii=False, indent=2))
raise SystemExit(bool(failed))
