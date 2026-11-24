import getpass,sys
from pathlib import Path
import paramiko
credential=getpass.getpass('One-time diagnostic sudo password: ')
cfg=paramiko.SSHConfig()
with (Path.home()/'.ssh'/'config').open() as f:cfg.parse(f)
h=cfg.lookup('gentoluna')
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy())
try:
    c.connect(h['hostname'],username=h['user'],key_filename=h.get('identityfile'),look_for_keys=False,allow_agent=False,timeout=8)
    cmd="sudo -S -p '' /usr/bin/timeout --signal=INT 5 /usr/bin/tcpdump -n -i eth0 -s 0 -c 32 -w /home/nvidia/luna-incidents/20261124-right-gripper-power/live-rt-after-position-20261124.pcap 'src host 6.6.7.190 and udp dst port 3721'"
    i,o,e=c.exec_command(cmd,timeout=12)
    i.write(credential+'\n');i.flush();i.channel.shutdown_write();del credential
    stdout=o.read().decode(errors='replace');stderr=e.read().decode(errors='replace')
    status=o.channel.recv_exit_status()
    print(stdout,end='');print(stderr,end='',file=sys.stderr)
    raise SystemExit(status)
finally:c.close()

