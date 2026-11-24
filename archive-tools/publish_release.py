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
TAG = 'archive-20261124'

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
    req = urllib.request.Request(url, data=data, method=method,
        headers={**headers, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=45) as r:
        b = r.read()
        return json.loads(b) if b else None

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
        'name': '2026-11-24 Gento Luna / PICO / STB 全日工程归档', 'draft': True,
        'body': '完整包包含当天 21 个独立测试/修改版本、程序与配置、原始遥测/故障证据、显示/语音素材、原项目和冻结基准。最终手部 1.5、肘部 1.2，底盘上限 0.2 m/s、0.2 rad/s。\n\n请同时下载 SHA256SUMS.txt 核验。归档时机器人 SSH 不可达，未新增补采仅存在机器人端的日志；既有本地资料已全部整理。详细范围、已知问题和版本索引见仓库 README。聊天仅导出可见消息并移除密码回复。'})

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

paths = [ROOT / 'archives/Getoluna-STB-20261124-complete.zip', ROOT / 'archives/SHA256SUMS.txt',
         ROOT / 'manifests/FILE-MANIFEST.json', ROOT / 'archives/package-result.json']
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

package = json.loads((ROOT / 'archives/package-result.json').read_text())
archive_asset = next(a for a in uploaded if a['name'] == package['archive'])
if archive_asset.get('digest'):
    assert archive_asset['digest'] == 'sha256:' + package['sha256']
release = api('PATCH', release['url'], {'draft': False})
receipt = {'repository': 'https://github.com/' + REPO, 'commit': head,
           'release': release['html_url'], 'draft': release['draft'],
           'assets': [{k: a.get(k) for k in ['name', 'size', 'digest', 'browser_download_url']} for a in uploaded]}
(ROOT / 'publication-result.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False), flush=True)
