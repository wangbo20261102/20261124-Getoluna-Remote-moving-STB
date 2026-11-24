"""Read-only battery overlay. No robot control interfaces."""
import json
import math
import os
from pathlib import Path
import time

SOURCE = Path('/run/luna-battery-screen/status.json')
RUNTIME = Path('/run/user/1000/luna-camera-fast-marmots')
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
THRESHOLD = 30


def display_state(status, source_fresh=True):
    fresh = (source_fresh and status.get('fresh') is True
             and isinstance(status.get('seconds_since_feedback'), (int, float))
             and 0 <= status['seconds_since_feedback'] < 8)
    entries = {b.get('id'): b for b in status.get('batteries', []) if isinstance(b, dict)}
    texts = {name: ' ' for name in ('b1_normal', 'b1_red', 'b1_unknown',
                                   'b2_normal', 'b2_red', 'b2_unknown', 'warning', 'stale')}
    rows = []
    for number in (1, 2):
        b = entries.get(number, {})
        energy = b.get('energy')
        valid = (fresh and b.get('is_connected') is True and b.get('is_in_place') is True
                 and isinstance(energy, (int, float)) and not isinstance(energy, bool)
                 and math.isfinite(energy) and 0 <= energy <= 100)
        if not valid:
            label, kind = f'电池 {number}：--  数据不可用', 'unknown'
        else:
            charging = '充电中' if b.get('is_charging') is True else '使用中'
            label = f'电池 {number}：{energy:g}%  {charging}'
            kind = 'red' if energy < THRESHOLD or b.get('error_code', 0) != 0 else 'normal'
            if b.get('error_code', 0):
                label += '  异常'
        texts[f'b{number}_{kind}'] = label
        rows.append({'id': number, 'valid': valid, 'energy': energy if valid else None,
                     'color': kind, 'text': label,
                     'charging': valid and b.get('is_charging') is True})
    if any(r['valid'] and r['energy'] < THRESHOLD for r in rows):
        texts['warning'] = '电量低于 30%，请优先充电'
    if any(not r['valid'] for r in rows):
        texts['stale'] = '电量数据不可用，请检查连接'
    return {'fresh': fresh, 'threshold_percent': THRESHOLD, 'rows': rows, 'texts': texts}


def atomic_write(path, text):
    path = Path(path)
    if path.exists() and path.read_text(encoding='utf-8') == text:
        return
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(text, encoding='utf-8')
    os.replace(temp, path)


def refresh(runtime=RUNTIME, source=SOURCE):
    runtime.mkdir(parents=True, exist_ok=True)
    try:
        age = time.time() - source.stat().st_mtime
        status = json.loads(source.read_text(encoding='utf-8'))
        state = display_state(status, 0 <= age < 5)
    except (OSError, ValueError, TypeError, AttributeError):
        state = display_state({}, False)
    for name, content in state['texts'].items():
        atomic_write(runtime / (name + '.txt'), content)
    atomic_write(runtime / 'display-state.json', json.dumps(state, ensure_ascii=False, indent=2))
    return state


def video_filter(runtime=RUNTIME):
    filters = ['crop=iw/2:ih/2:0:0',
               'drawbox=x=iw*0.51:y=ih*0.02:w=iw*0.47:h=ih*0.15:color=black@0.70:t=fill']
    for number in (1, 2):
        for kind, color in [('normal', 'white'), ('red', '0xFF3333'), ('unknown', '0xFFD166')]:
            filters.append(f'drawtext=fontfile={FONT}:textfile={runtime}/b{number}_{kind}.txt:'
                           f'reload=1:expansion=none:fontcolor={color}:fontsize=h/24:'
                           f'x=w*0.53:y=h*{0.034 + (number-1)*0.067}:borderw=1:bordercolor=black')
    for name, color, y in [('warning', '0xFF3333', .88), ('stale', '0xFFD166', .94)]:
        filters.append(f'drawtext=fontfile={FONT}:textfile={runtime}/{name}.txt:'
                       f'reload=1:expansion=none:fontcolor={color}:fontsize=h/22:'
                       f'x=(w-text_w)/2:y=h*{y}:borderw=2:bordercolor=black')
    return ','.join(filters)
