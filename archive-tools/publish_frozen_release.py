"""Publish the verified frozen snapshot; never contacts or controls the robot.

Uses existing credential-manager auth only in memory. Large release uploads are
not supported by the connected GitHub tools, so use the GitHub REST upload API.
The TLS/proxy choice is process-local and does not change system settings.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'archives/20261125-apex-impedance-frozen'
REPO = 'wangbo20261102/20261124-Getoluna-Remote-moving-STB'
API = 'https://api.github.com/repos/' + REPO
TAG = 'apex-impedance-frozen-20261125'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


class Progress:
    def __init__(self, stream, path):
        self.stream, self.path, self.sent, self.last = stream, path, 0, time.monotonic()

    def read(self, size=-1):
        block = self.stream.read(size)
        self.sent += len(block)
        if time.monotonic() - self.last > 15:
            print(json.dumps({'upload': self.path.name, 'sent': self.sent,
                              'total': self.path.stat().st_size}), flush=True)
            self.last = time.monotonic()
        return block


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit('Pass --apply after the reviewed snapshot is committed and pushed')
    credential = subprocess.run(
        ['git', '-c', 'credential.interactive=never', 'credential', 'fill'],
        input='protocol=https\nhost=github.com\n\n', text=True, capture_output=True,
        env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'Never'}, check=True)
    values = dict(line.split('=', 1) for line in credential.stdout.splitlines() if '=' in line)
    headers = {'Authorization': 'Bearer ' + values['password'], 'Accept': 'application/vnd.github+json',
               'User-Agent': 'Luna-Frozen-Archive', 'X-GitHub-Api-Version': '2022-11-28'}
    context = ssl.create_default_context()
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    context.set_alpn_protocols(['http/1.1'])
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({'https': 'http://127.0.0.1:7890'}),
        urllib.request.HTTPSHandler(context=context))

    def api(method, url, body=None):
        request = urllib.request.Request(url, method=method,
                    data=None if body is None else json.dumps(body).encode('utf-8'),
                    headers={**headers, 'Content-Type': 'application/json'})
        with opener.open(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else None

    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    assert api('GET', API + '/git/ref/heads/main')['object']['sha'] == head, 'Push commit first'
    scan = json.loads((ROOT/'manifests/20261125-apex-frozen/publication-scan.json').read_text())
    assert not scan['findings'], 'Publication scan has unresolved findings'
    paths = [BASE/'robot/robot-apex-runtime-and-records.tar.gz',
             BASE/'windows/windows-apex-and-local-evidence.tar.gz',
             BASE/'robot-snapshot-manifest.json', BASE/'windows-snapshot-manifest.json',
             BASE/'Getoluna-Apex-frozen-records-20261125.zip',
             BASE/'FREEZE-SUMMARY.json', BASE/'README.txt', BASE/'SHA256SUMS.txt']
    expected = {path.name: {'bytes': path.stat().st_size, 'sha256': sha(path)} for path in paths}
    try:
        release = api('GET', API + '/releases/tags/' + TAG)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        release = next((r for r in api('GET', API + '/releases') if r['tag_name'] == TAG), None)
    if release is None:
        release = api('POST', API + '/releases', {
            'tag_name': TAG, 'target_commitish': head, 'draft': True,
            'name': '2026-11-25 Apex 阻抗按钮实测成功版本与完整冻结资料',
            'body': 'Apex 原始待机→阻抗按钮已实测成功，双臂状态2、ready=true、error=false；14项后端测试、两轮临时接口实机验证和6次正式按钮反馈均保留。\n\n本次仅冻结、归档和同步，不再修改运行逻辑、参数或服务状态。两份完整快照合计14,991个文件/链接条目、原始捕获约1.86GB。另附本次仓库记录ZIP、逐文件清单与SHA-256清单。\n\n下载两份tar.gz及records.zip并核验SHA-256后，解压到普通资料目录查阅；不是自动部署或运动入口。实时底盘日志保存截至捕获时的前缀，详见README.txt。既有基准和旧发布全部保留。'})
    uploaded = []
    for path in paths:
        target = expected[path.name]
        for attempt in range(3):
            existing = next((a for a in api('GET', release['assets_url']) if a['name'] == path.name), None)
            if existing and existing.get('state') == 'uploaded':
                assert existing['size'] == target['bytes']
                assert existing.get('digest') == 'sha256:' + target['sha256']
                uploaded.append(existing)
                break
            if existing:
                if not release.get('draft'):
                    raise RuntimeError('Refusing to alter an existing published release asset')
                api('DELETE', existing['url'])
            try:
                url = release['upload_url'].split('{')[0] + '?name=' + urllib.parse.quote(path.name)
                with path.open('rb') as stream:
                    request = urllib.request.Request(url, data=Progress(stream, path), method='POST',
                        headers={**headers, 'Content-Type': 'application/octet-stream',
                                 'Content-Length': str(target['bytes'])})
                    with opener.open(request, timeout=900) as response:
                        asset = json.load(response)
                assert asset['size'] == target['bytes'] and asset.get('digest') == 'sha256:' + target['sha256']
                uploaded.append(asset)
                print(json.dumps({'uploaded': path.name, 'bytes': asset['size'], 'digest': asset['digest']}), flush=True)
                break
            except Exception as exc:
                print(json.dumps({'upload_retry': path.name, 'attempt': attempt+1, 'error_type': type(exc).__name__}), flush=True)
                if attempt == 2:
                    raise
    release = api('PATCH', release['url'], {'draft': False})
    assets = api('GET', release['assets_url'])
    for name, value in expected.items():
        asset = next(a for a in assets if a['name'] == name)
        assert asset.get('digest') == 'sha256:' + value['sha256'] and asset['size'] == value['bytes']
    ref = api('GET', API + '/git/ref/heads/main')['object']['sha']
    tag = api('GET', API + '/git/ref/tags/' + TAG)['object']['sha']
    assert ref == head and tag == head
    receipt = {'repository': 'https://github.com/' + REPO, 'commit': head,
               'release': release['html_url'], 'draft': release['draft'],
               'all_asset_sha256_match_local': True, 'remote_main_and_tag_match_commit': True,
               'system_network_settings_changed': False,
               'assets': [{key: a.get(key) for key in ('name', 'size', 'digest', 'browser_download_url')} for a in assets]}
    (ROOT/'publication-apex-frozen-20261125.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
