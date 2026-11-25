import ctypes,json,pathlib
base=pathlib.Path('/home/nvidia/luna-test-runs/20261125-mode3-right-arm-diagnostic')
d=ctypes.CDLL('/home/nvidia/tianji-robot-SDK/C_SDK/libGentoSDK.so')
f=d.FX_FileClient_RecvFile;f.argtypes=[ctypes.c_ubyte]*4+[ctypes.c_char_p,ctypes.c_char_p];f.restype=ctypes.c_int
for remote,local in [('/var/log/syslog','controller-syslog.txt'),('/var/log/syslog.1','controller-syslog-previous.txt'),('/var/log/kern.log','controller-kern.log'),('/home/FUSION/Config/cfg/robot.ini','controller-robot.ini')]:
    dest=base/local;ret=f(6,6,7,190,str(dest).encode(),remote.encode());print(json.dumps({'remote':remote,'ret':ret,'bytes':dest.stat().st_size if dest.exists() else None}),flush=True)
