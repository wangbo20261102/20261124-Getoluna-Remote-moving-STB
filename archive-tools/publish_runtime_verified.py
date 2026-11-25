"""Publish the already-reviewed archive using existing Git credential-manager auth.

Credentials stay in process memory and are never written to a file or printed.
The original robot and all source directories are untouched.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPO = 'wangbo20261102/20261124-Getoluna-Remote-moving-STB'
API = 'https://api.github.com/repos/' + REPO
TAG = 'verified-20261125'

def get_credentials():
    result = subprocess.run(['git', '-c', 'credential.interactive=never', 'credential', 'fill'],
        input='protocol=https\nhost=github.com\n\n', text=True, capture_output=True,
        env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'Never'}, check=True)
    values = dict(s.split('=', 1) for s in result.stdout.splitlines() if '=' in s)
    return values['password']

token = get_credentials()
headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
           'User-Agent': 'Luna-20261124-Archive', 'X-GitHub-Api-Version': '2022-11-28'}

def api(method, url, body=None):
    data = None if body is None else json.dumps(body).encode('utf-8')
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, method=method,
            headers={**headers, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                b = r.read()
                return json.loads(b) if b else None
        except urllib.error.HTTPError as exc:
            if exc.code not in [429, 500, 502, 503, 504] or method == 'POST' or attempt == 3:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if method == 'POST' or attempt == 3:
                raise
        print(json.dumps({'api_retry': attempt + 1, 'method': method}), flush=True)
        time.sleep(2 ** attempt)

head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
remote = subprocess.check_output(['git', '-C', str(ROOT), 'ls-remote', 'origin', 'refs/heads/main'], text=True).split()[0]
assert head == remote, 'The commit must be pushed before creating a release.'
try:
    release = api('GET', API + '/releases/tags/' + TAG)
except urllib.error.HTTPError as exc:
    if exc.code != 404:
        raise
    release = None
if release is None:
    # A previous interrupted run may have left a draft, which tags lookup can miss.
    release = next((x for x in api('GET', API + '/releases') if x['tag_name'] == TAG), None)
if release is None:
    release = api('POST', API + '/releases', {'tag_name': TAG, 'target_commitish': head,
        'name': '2026-11-25 联机资料与工具参数运行时核验', 'draft': True,
        'body': '本版包括先前所有联机补采和持久化修复，并追加 Robot 工具参数运行时核验。现场确认空载、双腕支撑且 FXPlatform 断开后启动 Robot，仅执行 set_ready；左右工具数组从运行参数服务读回与保存值一致，控制器 6 次反馈正常，保持待机，未执行 Home、模式切换或遥操。不是控制器 EEPROM 独立读回或断电测试。\n\n完整恢复：先解压 archive-20261124 的完整基包，再解压本版 verified supplement 到同一目录；无需叠加之前 sync-20261125 补充包。原基准与既有发布保留，昨天无法追回的 journal 缺项仍有注明。'})

class ProgressFile:
    def __init__(self, f, name, size):
        self.f, self.name, self.size, self.sent, self.last = f, name, size, 0, time.monotonic()
    def read(self, n=-1):
        b = self.f.read(n)
        self.sent += len(b)
        if time.monotonic() - self.last > 15:
            print(json.dumps({'upload': self.name, 'sent_bytes': self.sent, 'total_bytes': self.size}), flush=True)
            self.last = time.monotonic()
        return b

paths = [ROOT / 'archives/verified-20261125/Getoluna-STB-20261125-verified-supplement.zip', ROOT / 'archives/verified-20261125/SHA256SUMS.txt',
         ROOT / 'manifests/FILE-MANIFEST.json', ROOT / 'archives/verified-20261125/package-result.json']
uploaded = []
for p in paths:
    existing = next((a for a in api('GET', release['assets_url']) if a['name'] == p.name), None)
    if existing and existing.get('size') == p.stat().st_size and existing.get('state') == 'uploaded':
        uploaded.append(existing)
        print(json.dumps({'already_uploaded': p.name, 'bytes': existing['size']}), flush=True)
        continue
    if existing:
        api('DELETE', existing['url'])
    url = release['upload_url'].split('{')[0] + '?name=' + urllib.parse.quote(p.name)
    for attempt in range(1, 4):
        try:
            with p.open('rb') as f:
                stream = ProgressFile(f, p.name, p.stat().st_size)
                req = urllib.request.Request(url, data=stream, method='POST',
                    headers={**headers, 'Content-Type': 'application/octet-stream', 'Content-Length': str(p.stat().st_size)})
                with urllib.request.urlopen(req, timeout=180) as response:
                    asset = json.load(response)
            assert asset['size'] == p.stat().st_size and asset['state'] == 'uploaded'
            uploaded.append(asset)
            print(json.dumps({'uploaded': p.name, 'bytes': asset['size'], 'digest': asset.get('digest')}), flush=True)
            break
        except Exception as exc:
            print(json.dumps({'retry': attempt, 'asset': p.name, 'error_type': type(exc).__name__, 'error': str(exc)}), flush=True)
            existing = next((a for a in api('GET', release['assets_url']) if a['name'] == p.name), None)
            if existing and existing.get('size') == p.stat().st_size and existing.get('state') == 'uploaded':
                uploaded.append(existing)
                break
            if existing:
                api('DELETE', existing['url'])
            if attempt == 3:
                raise

package = json.loads((ROOT / 'archives/verified-20261125/package-result.json').read_text())
archive_asset = next(a for a in uploaded if a['name'] == package['archive'])
if archive_asset.get('digest'):
    assert archive_asset['digest'] == 'sha256:' + package['sha256']
release = api('PATCH', release['url'], {'draft': False, 'target_commitish': head})
uploaded = api('GET', release['assets_url'])
receipt = {'repository': 'https://github.com/' + REPO, 'commit': head,
           'release': release['html_url'], 'draft': release['draft'],
           'assets': [{k: a.get(k) for k in ['name', 'size', 'digest', 'browser_download_url']} for a in uploaded]}
(ROOT / 'publication-verified-20261125.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False), flush=True)
