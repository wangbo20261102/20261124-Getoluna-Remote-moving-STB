"""Check frozen payloads for credential material without printing matched values."""
import json
import hashlib
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'archives/20261125-apex-impedance-frozen'
patterns = {
    'github_token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})'),
    'openai_key': re.compile(rb'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}'),
    'private_key_block': re.compile(rb'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{80,}-----END '),
}
findings = []
false_positives = []
checked = 0
for archive in (BASE/'robot/robot-apex-runtime-and-records.tar.gz', BASE/'windows/windows-apex-and-local-evidence.tar.gz'):
    with tarfile.open(archive, 'r|gz') as tar:
        for member in tar:
            if not member.isfile():
                continue
            checked += 1
            with tar.extractfile(member) as f:
                tail = b''
                found = set()
                while True:
                    block = f.read(1024*1024)
                    if not block:
                        break
                    data = tail + block
                    for name, pattern in patterns.items():
                        for match in pattern.finditer(data):
                            fingerprint = hashlib.sha256(match[0]).hexdigest()
                            if name == 'openai_key' and fingerprint == '601724a460808810f2809eb0d06d417ad6ed0a507c9e9e9689668381ff6c1dcd':
                                # Reviewed stock Electron locale table: sk-SK is
                                # immediately followed by concatenated locales.
                                row = {'path': member.name, 'kind': 'Chromium locale table', 'match_sha256': fingerprint}
                                if row not in false_positives:
                                    false_positives.append(row)
                            else:
                                found.add(name)
                    tail = data[-8192:]
                for kind in sorted(found):
                    findings.append({'archive': archive.name, 'path': member.name, 'kind': kind})
report = {'files_scanned': checked, 'findings': findings,
          'reviewed_false_positives': false_positives,
          'credential_directories_not_selected': ['.ssh', 'credential manager', 'runtime console authentication tokens'],
          'matched_values_printed': False}
(ROOT/'manifests/20261125-apex-frozen/publication-scan.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report), flush=True)
if findings:
    raise SystemExit(2)
