"""Windows stdlib SSH transport. Credentials stay in the existing SSH profile."""
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import uuid

ROOT=Path(__file__).resolve().parent
NO_WINDOW=getattr(subprocess,'CREATE_NO_WINDOW',0)

def ssh_args(profile,video=False):
    host=profile['ssh_host'];remote=profile['remote_dir']
    if not re.fullmatch(r'[A-Za-z0-9_.@-]+',host):raise ValueError('SSH 主机配置不合法')
    if not re.fullmatch(r'/home/nvidia/luna-test-runs/[A-Za-z0-9_/-]+',remote):raise ValueError('远程程序目录不合法')
    command=f"source /etc/apex/apex_ros_env.sh; exec /usr/bin/python3 -u {remote}/robot_agent.py"+(' --video' if video else '')
    return ['ssh.exe' if os.name=='nt' else 'ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=6',host,'bash','-lc',"'"+command+"'"]

class RemoteClient:
    def __init__(self,profile,on_diagnostic=None):
        self.profile=profile;self.process=None;self.responses=queue.Queue();self.lock=threading.Lock()
        self.diagnostic=on_diagnostic or (lambda x:None)

    def close(self):
        p=self.process;self.process=None
        if p and p.poll() is None:p.terminate()

    def _reader(self,p,responses):
        try:
            for line in p.stdout:
                try:responses.put(json.loads(line))
                except ValueError:self.diagnostic(line.strip()[:500])
        finally:responses.put({'transport_closed':True})

    def _stderr(self,p):
        for line in p.stderr:
            if line.strip():self.diagnostic(line.strip()[:700])

    def _exchange(self,cmd,args,timeout):
        p=self.process;request_id=uuid.uuid4().hex
        p.stdin.write(json.dumps({'id':request_id,'cmd':cmd,'args':args or {}})+'\n');p.stdin.flush()
        response=self.responses.get(timeout=timeout)
        if response.get('transport_closed'):raise ConnectionError('机器人连接已断开，请检查网线与 SSH')
        if response.get('id')!=request_id:raise ConnectionError('响应顺序异常，已断开；请重新读取状态')
        if not response.get('ok'):raise RuntimeError(response.get('error','机器人操作失败'))
        return response.get('data')

    def request(self,cmd,args=None,timeout=70):
        with self.lock:
            try:
                if self.process is None or self.process.poll() is not None:
                    self.responses=queue.Queue()
                    self.process=subprocess.Popen(ssh_args(self.profile),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1,creationflags=NO_WINDOW)
                    threading.Thread(target=self._reader,args=(self.process,self.responses),daemon=True).start()
                    threading.Thread(target=self._stderr,args=(self.process,),daemon=True).start()
                    hello=self._exchange('hello',{},15)
                    local_hash=hashlib.sha256((ROOT/'robot_agent.py').read_bytes()).hexdigest()
                    if hello.get('agent_sha256')!=local_hash:
                        self.close();raise RuntimeError('本机与机器人控制台版本不一致，请运行安装/同步入口')
                return self._exchange(cmd,args,timeout)
            except queue.Empty as exc:
                self.close();raise TimeoutError('响应超时，结果未确认。请读取状态后再操作；不会自动重发动作。') from exc
            except (ConnectionError,OSError,BrokenPipeError):self.close();raise

class VideoClient:
    def __init__(self,profile,on_frame,on_error):
        self.profile=profile;self.on_frame=on_frame;self.on_error=on_error;self.process=None
    def start(self):
        if self.process and self.process.poll() is None:return
        self.process=subprocess.Popen(ssh_args(self.profile,True),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1,creationflags=NO_WINDOW)
        threading.Thread(target=self.read,args=(self.process,),daemon=True).start()
        threading.Thread(target=self.drain,args=(self.process,),daemon=True).start()
    def read(self,p):
        for line in p.stdout:
            try:
                value=json.loads(line)
                if value.get('frame'):self.on_frame(value)
                elif value.get('waiting'):self.on_error(value.get('message','等待视频'))
            except (ValueError,KeyError):pass
    def drain(self,p):
        for line in p.stderr:
            if line.strip():self.on_error(line.strip()[:300])
    def close(self):
        if self.process and self.process.poll() is None:self.process.terminate()
        self.process=None

def direct_controller_connection(profile):
    if os.name!='nt':return False
    p=subprocess.run(['netstat.exe','-ano','-p','tcp'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,creationflags=NO_WINDOW,timeout=5)
    ip=profile['controller_ip']+':'
    return any(ip in line and 'ESTABLISHED' in line.upper() for line in p.stdout.splitlines())
