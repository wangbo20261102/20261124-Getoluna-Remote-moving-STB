#!/usr/bin/env python3
"""Keep only the MAXHUB display client alive; never opens cameras or robot APIs."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

HOME = Path('/home/nvidia')
RUN = Path('/run/user/1000/luna-maxhub-client')
ROOT = Path(__file__).resolve().parent
RUN.mkdir(parents=True, exist_ok=True)
lock = (RUN / 'guard.lock').open('w')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
ENV = dict(os.environ, DISPLAY=':0', XAUTHORITY='/run/luna-maxhub/Xauthority', XDG_RUNTIME_DIR='/run/user/1000')

def status(**values):
    values['checked_at_unix'] = time.time()
    target = RUN / 'status.json'
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(values, ensure_ascii=False) + '\n')
    tmp.replace(target)

def clients():
    found = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            if (p / 'comm').read_text().strip() == 'DongleClient' and (p / 'status').read_text().split('Uid:')[1].split()[0] == '1000':
                found.append(int(p.name))
        except (OSError, IndexError):
            continue
    return sorted(found)

def run(args, timeout=20):
    r = subprocess.run(args, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(r.stdout.strip()[-600:] or f'{args[0]} returned {r.returncode}')
    return r.stdout

child = None
log = None
print('MAXHUB client guard started; existing preview, voice and robot services are untouched.', flush=True)
while True:
    if child is not None and child.poll() is not None:
        print(f'MAXHUB child exited: {child.returncode}', flush=True)
        child = None
        if log:
            log.close()
            log = None
    pids = clients()
    if pids:
        status(state='running', client_pids=pids, adopted_existing=child is None)
        time.sleep(3)
        continue
    try:
        dirs = list((HOME / '.local/share').glob('maxhub-5.10.46.0.*'))
        if len(dirs) != 1:
            raise RuntimeError(f'Expected one MAXHUB installation, got {len(dirs)}')
        binary = dirs[0] / 'opt/apps/com.cvte.exceedshare/files/bin/DongleClient'
        if not os.access(binary, os.X_OK):
            raise RuntimeError('MAXHUB client binary missing or not executable')
        run(['/usr/bin/sudo', '-n', '/usr/local/sbin/luna-maxhub-prepare'])
        display = run(['/usr/bin/xrandr', '--query'])
        if 'DP-1 connected' not in display:
            raise RuntimeError('DP-1 display is not connected yet')
        run(['/usr/bin/xrandr', '--output', 'DP-1', '--mode', '1920x1080', '--rate', '60'])
        # Recheck immediately before launch: do not duplicate a manually started client.
        if clients():
            continue
        client_env = dict(ENV, LD_LIBRARY_PATH=str(binary.parent.parent / 'lib'),
                          QT_PLUGIN_PATH=str(binary.parent.parent / 'plugins'), QT_QPA_PLATFORM='xcb')
        log = (ROOT / 'client.log').open('ab', buffering=0)
        child = subprocess.Popen([str(binary)], cwd=binary.parent, env=client_env,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        print(f'MAXHUB client launched: PID {child.pid}', flush=True)
        status(state='starting', client_pids=[child.pid], adopted_existing=False)
    except Exception as exc:
        status(state='waiting', client_pids=[], error=str(exc))
        print(f'Waiting for MAXHUB display/USB readiness: {exc}', flush=True)
    time.sleep(5)
