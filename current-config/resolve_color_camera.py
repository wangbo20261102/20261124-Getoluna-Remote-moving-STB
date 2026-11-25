#!/usr/bin/env python3
"""Resolve this D435 RGB interface before Camera starts; no robot control calls."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parent
CONFIG = Path('/home/nvidia/d435-preview/apex-color1080.yaml')
DEVICE = Path('/dev/v4l/by-path/platform-14160000.pcie-pci-0004:01:00.0-usb-0:2:1.3-video-index0')
SERIAL = '344223024944'

def select():
    device = DEVICE.resolve(strict=True)
    if not re.fullmatch(r'/dev/video\d+', str(device)):
        raise RuntimeError('RGB interface did not resolve to a video node')
    props = subprocess.check_output(['udevadm', 'info', '-q', 'property', '-n', str(device)], text=True, timeout=5)
    if SERIAL not in props or 'ID_USB_INTERFACE_NUM=03' not in props:
        raise RuntimeError('D435 serial or RGB USB interface did not match')
    formats = subprocess.check_output(['v4l2-ctl', '-d', str(device), '--list-formats-ext'], text=True, timeout=5)
    if "'YUYV'" not in formats or '1920x1080' not in formats:
        raise RuntimeError('Selected interface does not advertise YUYV 1920x1080')
    return device

deadline = time.monotonic() + 35
while True:
    try:
        selected = select()
        break
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        if time.monotonic() >= deadline:
            raise RuntimeError(f'D435 RGB interface not ready: {exc}') from exc
        print(f'Waiting for D435 RGB interface: {exc}', flush=True)
        time.sleep(2)

before = CONFIG.read_bytes()
uri = ('v4l2://' + str(selected)).encode()
patterns = [
    rb'(?m)^([ \t]*head_cam_source:[ \t]*\[[ \t]*")([^"\r\n]+)("[ \t]*\][^\r\n]*)$',
    rb'(?m)^([ \t]*head_left:[ \t]*")([^"\r\n]+)("[^\r\n]*)$',
]
after = before
changes = []
for pattern in patterns:
    matches = list(re.finditer(pattern, after))
    if len(matches) != 1:
        raise RuntimeError('Camera config does not have the expected unique RGB source field')
    changes.append(matches[0].group(2).decode())
    after = re.sub(pattern, lambda m: m.group(1) + uri + m.group(3), after)
def skeleton(data):
    for pattern in patterns:
        data = re.sub(pattern, lambda m: m.group(1) + b'RGB_SOURCE' + m.group(3), data)
    return data
assert skeleton(before) == skeleton(after)
if after != before:
    temp = CONFIG.with_name(CONFIG.name + '.resolve.tmp')
    temp.write_bytes(after)
    os.chmod(temp, CONFIG.stat().st_mode)
    os.replace(temp, CONFIG)
report = {'stable_rgb_interface': str(DEVICE), 'serial': SERIAL, 'selected_node': str(selected),
          'source': uri.decode(), 'previous_sources': changes, 'changed': before != after,
          'other_config_bytes_unchanged': True, 'sha256': hashlib.sha256(after).hexdigest(),
          'selected_at_unix': time.time()}
(ROOT / 'device-selection.json').write_text(json.dumps(report, indent=2) + '\n')
(ROOT / 'apex-color1080.after.yaml').write_bytes(after)
print(json.dumps(report), flush=True)
