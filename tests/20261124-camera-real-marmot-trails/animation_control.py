"""Local-only FFmpeg animation control via the installed libzmq C API."""
import ctypes as c
import ctypes.util
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent
ENDPOINT='ipc:///run/user/1000/luna-camera-real-marmot-trails/animation.sock'

def config():
    data=json.loads((BASE/'animations.json').read_text())
    if data.get('schema_version')!=1:raise ValueError('Unsupported animation config')
    for key in ('1','2'):
        b=data['batteries'][key]
        if b['kind'] not in ('turtle','snail','marmots'):raise ValueError('Unknown sprite')
        if not 16<=b['width']<=160 or not 16<=b['height']<=100:raise ValueError('Invalid sprite size')
        if not 10<=b['cycle_seconds']<=120:raise ValueError('Invalid cycle')
        if not 0<=b['x_fraction']<=.9 or not 0<=b['travel_fraction']<=.2:raise ValueError('Invalid track')
        if not 0<=b['y_fraction']<=.15:raise ValueError('Invalid row')
        if b.get('motion') not in ('forward_wrap','stationary'):raise ValueError('Invalid motion')
        if b['motion']=='forward_wrap' and b['travel_fraction']==0:raise ValueError('Track cannot be empty')
        if not .1<=b.get('restart_pause_seconds',.6)<=3:raise ValueError('Invalid reset pause')
        if not isinstance(b.get('trail_dots'),int) or not 0<=b['trail_dots']<=100:raise ValueError('Invalid dot count')
        if not 1<=b.get('trail_dot_size',4)<=6:raise ValueError('Invalid dot size')
    return data

def track(b,elapsed,width=1920):
    if b['motion']=='stationary':return width*b['x_fraction']
    duration=b['cycle_seconds']/2
    pause=b.get('restart_pause_seconds',.6)
    phase=elapsed%(duration+pause)
    if phase>=duration:return None
    return width*(b['x_fraction']+b['travel_fraction']*phase/duration)


def filtergraph(base_filter, control=True, enabled=False,time_offset=0):
    cfg=config()
    filters=[f'[in]{base_filter},settb=AVTB,setpts=PTS-STARTPTS+{time_offset}/TB[base]']
    previous='base'
    for key in ('1','2'):
        b=cfg['batteries'][key]
        sprite=BASE/'assets'/(b['kind']+'.gif')
        if b['motion']=='stationary':
            filters.append(f"movie=filename={sprite}:loop=0,settb=AVTB,setpts=N/(12.5*TB)+{time_offset}/TB,"
                           f"scale={b['width']}:{b['height']},format=rgba[sprite{key}]")
            filters.append(f"[{previous}][sprite{key}]overlay@battery{key}=x=main_w*{b['x_fraction']}:"
                           f"y=main_h*{b['y_fraction']}:enable={int(enabled and cfg['enabled'])}[b{key}]")
            previous='b'+key
            continue
        duration=b['cycle_seconds']/2
        pause=b.get('restart_pause_seconds',.6)
        period=duration+pause
        width=1920
        origin=width*b['x_fraction'];travel=width*b['travel_fraction']
        dots=[]
        count=b.get('trail_dots',9)
        for i in range(count):
            distance=travel*i/count
            threshold=(distance+12)/(travel/duration)
            tail_y=b['height']*(.61 if b['kind']=='turtle' else .76)
            size=b.get('trail_dot_size',4)
            dots.append(f"drawbox=x={origin+distance}:y={tail_y}:w={size}:h={size}:"
                        f"color=white@0.85:t=fill:replace=1:"
                        f"enable='gte(mod(t,{period}),{threshold})*lt(mod(t,{period}),{duration})'")
        filters.append(f"color=c=black@0:s={width}x{b['height']}:r=25,format=rgba,settb=AVTB,"
                       f"setpts=PTS+{time_offset}/TB,"+','.join(dots)+f'[trail{key}]')
        filters.append(f"movie=filename={sprite}:loop=0,settb=AVTB,setpts=N/(12.5*TB)+{time_offset}/TB,"
                       f"scale={b['width']}:{b['height']},format=rgba[sprite{key}]")
        position=f"main_w*{b['x_fraction']}+main_w*{b['travel_fraction']}*mod(t,{period})/{duration}"
        filters.append(f"[trail{key}][sprite{key}]overlay=x='{position}':y=0:format=auto:"
                       f"enable='lt(mod(t,{period}),{duration})',format=rgba[layer{key}]")
        filters.append(f"[{previous}][layer{key}]overlay@battery{key}=x=0:"
                       f"y=main_h*{b['y_fraction']}:enable={int(enabled and cfg['enabled'])}[b{key}]")
        previous='b'+key
    if control:
        escaped=ENDPOINT.replace(':','\\:')
        filters.append(f"[{previous}]zmq=bind_address='{escaped}'[out]")
    else:filters.append(f'[{previous}]null[out]')
    return ';'.join(filters)

class Client:
    def __init__(self):
        self.lib=c.CDLL(ctypes.util.find_library('zmq'))
        self.lib.zmq_ctx_new.restype=c.c_void_p
        self.lib.zmq_ctx_term.argtypes=[c.c_void_p]
        self.lib.zmq_socket.argtypes=[c.c_void_p,c.c_int];self.lib.zmq_socket.restype=c.c_void_p
        self.lib.zmq_close.argtypes=[c.c_void_p]
        self.lib.zmq_connect.argtypes=[c.c_void_p,c.c_char_p]
        self.lib.zmq_setsockopt.argtypes=[c.c_void_p,c.c_int,c.c_void_p,c.c_size_t]
        self.lib.zmq_send.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t,c.c_int]
        self.lib.zmq_recv.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t,c.c_int]
        self.ctx=self.lib.zmq_ctx_new()
        if not self.ctx:raise RuntimeError('Cannot create local animation client')

    def request(self,text):
        sock=self.lib.zmq_socket(self.ctx,3)  # ZMQ_REQ
        if not sock:raise RuntimeError('Cannot create animation socket')
        try:
            for option,value in [(17,0),(27,400),(28,400)]: # LINGER, RCVTIMEO, SNDTIMEO
                n=c.c_int(value)
                if self.lib.zmq_setsockopt(sock,option,c.byref(n),c.sizeof(n)):
                    raise RuntimeError('Cannot configure animation socket')
            if self.lib.zmq_connect(sock,ENDPOINT.encode()):raise RuntimeError('Animation connect failed')
            payload=text.encode()
            if self.lib.zmq_send(sock,payload,len(payload),0)<0:raise RuntimeError('Animation send failed')
            buffer=c.create_string_buffer(1024)
            n=self.lib.zmq_recv(sock,buffer,1024,0)
            if n<0:raise TimeoutError('Animation reply not ready')
            reply=buffer.raw[:n].decode()
            if not reply.startswith('0 '):raise RuntimeError(reply)
            return reply
        finally:self.lib.zmq_close(sock)

    def close(self):
        self.lib.zmq_ctx_term(self.ctx)
