"""Copy-only collection of the 2026-11-24 Luna work. Never controls the robot."""
from pathlib import Path
import collections
import base64
import hashlib
import json
import re
import shutil
import stat
import zipfile
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path('E:/Github/Mubea-EV-Gentoluna')
TESTS = Path('E:/Github/Mubea-EV-Gentoluna-tests')
BASE = Path('E:/Github/Mubea-EV-Gentoluna-baselines/20261124-before-0p2')
WORKSPACE = Path('C:/Users/Wang Bo/OneDrive/Documents/ChatGPT/Mubea 弹簧开发')
SKIP = {'.git', 'luna-review-venv', '__pycache__'}

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def write_json(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

copied = []
def copy_file(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    before = src.stat()
    if not dst.is_file() or digest(dst) != digest(src):
        if dst.is_file():
            assert dst.resolve().is_relative_to(ROOT)
            dst.chmod(dst.stat().st_mode | stat.S_IWRITE)
        shutil.copy2(src, dst)
    source_hash = digest(src)
    dest_hash = digest(dst)
    after = src.stat()
    stable = before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns
    if source_hash != dest_hash:
        # Live PC keepalive logs can be appended during capture; take one new snapshot.
        shutil.copy2(src, dst)
        dest_hash = digest(dst)
        source_hash = digest(src)
        stable = source_hash == dest_hash
    copied.append({'source': str(src), 'path': dst.relative_to(ROOT).as_posix(),
                   'bytes': dst.stat().st_size, 'sha256': dest_hash,
                   'source_sha256_at_check': source_hash, 'source_stable_during_copy': stable})

def copy_tree(src, dst, skip=True):
    for p in sorted(src.rglob('*')):
        if p.is_file() and (not skip or not any(x in SKIP for x in p.relative_to(src).parts)):
            copy_file(p, dst / p.relative_to(src))

copy_tree(TESTS, ROOT / 'tests', skip=False)
copy_tree(PROJECT, ROOT / 'reference-project')
copy_tree(BASE, ROOT / 'frozen-baseline', skip=False)
copy_tree(WORKSPACE / 'work', ROOT / 'workspace-records')
for n in ['AGENTS.md', '20261124_右臂报警归档与电量提醒.md']:
    copy_file(WORKSPACE / n, ROOT / 'docs' / n)

# Extract only visible user/assistant messages from this one project chat.
# Excludes reasoning, developer/system messages, tool calls/results, credentials and image payloads.
session = next(Path('C:/Users/Wang Bo/.codex/sessions/2026/11/24').glob('*01a20ade-6a36-7aa1-8c36-9ce194fd5445.jsonl'))
messages = []
attachment_names = set()
embedded_attachments = {}
redactions = 0
with session.open(encoding='utf-8') as f:
    for line in f:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        pl = item.get('payload', {})
        if item.get('type') != 'response_item' or pl.get('type') != 'message' or pl.get('role') not in ['user', 'assistant']:
            continue
        texts = [c.get('text', '') for c in pl.get('content', []) if c.get('type') in ['input_text', 'output_text', 'text']]
        text = '\n'.join(texts)
        names = list(dict.fromkeys(re.findall(r'codex-clipboard-[0-9a-f-]+\.(?:png|jpg|jpeg)', text, flags=re.I)))
        attachment_names.update(names)
        images = [c.get('image_url', '') for c in pl.get('content', []) if c.get('type') == 'input_image']
        if pl['role'] == 'user' and len(names) == len(images):
            for name, image in zip(names, images):
                if isinstance(image, str) and image.startswith('data:image/') and ';base64,' in image:
                    embedded_attachments[name] = image.split(';base64,', 1)[1]
        if text.startswith('# AGENTS.md instructions for '):
            continue
        if re.fullmatch(r'\s*nvidia\s*', text, re.I):
            text = '[密码回复已移除]'
            redactions += 1
        text, n = re.subn(r'("answer"\s*:\s*)"nvidia"', r'\1"[密码回复已移除]"', text)
        redactions += n
        if ('密码' in text or 'password' in text.lower()) and not ('/home/nvidia/' in text or 'nvidia@' in text):
            text, n = re.subn(r'(?<![\w/])nvidia(?![\w/])', '[凭据已移除]', text)
            redactions += n
        if text.strip():
            messages.append({'timestamp_utc': item.get('timestamp'), 'role': pl['role'], 'text': text})
write_json(ROOT / 'docs/conversation-visible-redacted.json', {'note': '仅本聊天可见用户和助手消息；工具证据请见各测试目录。密码回复移除，不包含隐藏推理或系统指令。', 'redactions': redactions, 'messages': messages})
md = ['# 2026-11-24 会话记录（可见消息，凭据已移除）', '', '时间字段为源记录 UTC。此文件不含工具原始调用、隐藏推理、系统指令或图像内嵌数据。', '']
for m in messages:
    md += [f"## {m['timestamp_utc']} / {m['role']}", '', m['text'], '']
(ROOT / 'docs/conversation-visible-redacted.md').write_text('\n'.join(md), encoding='utf-8')

attachments = []
temp = Path('C:/Users/Wang Bo/AppData/Local/Temp')
for name in sorted(attachment_names):
    src = temp / name
    exists = src.is_file()
    if exists:
        copy_file(src, ROOT / 'attachments' / name)
        origin = 'original_temp_file'
    elif name in embedded_attachments:
        dst = ROOT / 'attachments' / name
        dst.parent.mkdir(exist_ok=True)
        dst.write_bytes(base64.b64decode(embedded_attachments[name], validate=True))
        exists = True
        origin = 'recovered_from_this_chat_embedded_user_image'
    else:
        origin = 'not_found'
    attachments.append({'name': name, 'available': exists, 'source': origin})
write_json(ROOT / 'manifests/attachments.json', attachments)

current = ROOT / 'current-config'
for src, name in [
    (TESTS / '20261124-hand-scale-1p5/robot_param.after.yaml', 'teleop-robot_param.yaml'),
    (TESTS / '20261124-elbow-home-alignment/controller_udp.py', 'controller_udp.py'),
    (TESTS / '20261124-elbow-home-alignment/elbow_home_alignment.py', 'elbow_home_alignment.py'),
    (TESTS / '20261124-elbow-home-alignment/records/calibration.json', 'calibration.json'),
    (TESTS / '20261124-full-body-cooperation/pico_chassis_bridge.py', 'pico_chassis_bridge.py'),
    (TESTS / '20261124-full-body-cooperation/start_manual_chassis.sh', 'start_manual_chassis.sh'),
    (TESTS / '20261124-gripper-release-fix/libGentoSDK.release-fix.so', 'libGentoSDK.release-fix.so'),
    (TESTS / '20261124-camera-fast-marmots/animations.json', 'animations.json'),
]:
    copy_file(src, current / name)

checks = json.loads((BASE / 'ARCHIVE-CHECKSUMS.json').read_text(encoding='utf-8-sig'))
for entry in checks:
    assert digest(BASE / entry['name']) == entry['sha256'], entry['name']
    assert digest(ROOT / 'frozen-baseline' / entry['name']) == entry['sha256'], entry['name']
write_json(ROOT / 'manifests/baseline-integrity.json', {'original_untouched': True, 'all_original_archive_checksums_match': True, 'checked': checks})
write_json(ROOT / 'manifests/source-copies.json', copied)
write_json(ROOT / 'manifests/collection-status.json', {
    'date': '2026-11-24', 'timezone': 'Asia/Shanghai',
    'collected_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'test_versions': len([d for d in TESTS.iterdir() if d.is_dir()]),
    'source_files_copied': len(copied), 'source_bytes_copied': sum(x['bytes'] for x in copied),
    'robot_new_capture': False,
    'robot_connection_result': 'SSH to 6.6.7.100 timed out during banner exchange on two attempts; no service/motion/config changes attempted.',
    'battery_at_archive': '无法连接，无法读取新鲜电量，不能判断当前是否低于 30%。历史电量保留在各原始报告中。',
    'excluded_recreatable_working_files': ['work/luna-review-venv', 'nested .git metadata', 'working __pycache__ (test directories and frozen baseline retain their originals)'],
    'raw_codex_session': 'Not published: export only visible user/assistant text, with password replies removed.',
    'all_originals_kept_in_place': True,
})
print(json.dumps({'copied_files': len(copied), 'copied_bytes': sum(x['bytes'] for x in copied), 'test_versions': 21,
                  'chat_messages': len(messages), 'credential_redactions': redactions,
                  'attachments': len(attachments), 'available_attachments': sum(x['available'] for x in attachments)}, ensure_ascii=False), flush=True)
