"""Independent native HMI; opening reads state, never starts robot actions."""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import queue
import subprocess
import threading
import time
import sys
import base64
import io
import tkinter as tk
from tkinter import filedialog,messagebox,ttk

from transport import RemoteClient,VideoClient,direct_controller_connection,NO_WINDOW

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
from PIL import Image,ImageTk
BG='#eef2f6';INK='#142f49';BLUE='#176d94';GREEN='#087f72';RED='#b62d39';GRAY='#64778a'
MODULES={'apex-camera.service':'摄像头','apex-robot.service':'Robot','apex-teleop.service':'PICO 遥操','apex-tool.service':'夹爪输入','luna-pico-manual-chassis.service':'底盘桥','luna-maxhub-client.service':'MAXHUB','luna-camera-fast-marmots.service':'电量/动画','luna-battery-voice-warning.service':'充电语音'}

def flatten(value,prefix=''):
    if isinstance(value,dict):
        for key,item in value.items():yield from flatten(item,f'{prefix}.{key}' if prefix else str(key))
    else:yield prefix,value

def text_value(value):
    if value is None:return '—'
    if isinstance(value,(dict,list)):return json.dumps(value,ensure_ascii=False,separators=(', ',': '))
    if isinstance(value,bool):return '是' if value else '否'
    return str(value)

class Console:
    def __init__(self,root,offline=False):
        self.root=root;self.offline=offline;self.profile=json.loads((ROOT/'profile.json').read_text(encoding='utf-8'))
        self.events=queue.SimpleQueue();self.frame_queue=queue.Queue(maxsize=1);self.busy=False;self.polling=False;self.connected=False
        self.last_status=None;self.last_params=None;self.status_time=0;self.frame_time=0;self.param_rows=[];self.selected_file=None;self.closing=False
        self.log_path=ROOT/'logs'/('console-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.jsonl');self.log_path.parent.mkdir(exist_ok=True)
        self.remote=RemoteClient(self.profile,lambda x:self.events.put(('diagnostic',x)))
        self.video=VideoClient(self.profile,self.new_frame,lambda x:self.events.put(('video_notice',x)))
        self.supported=tk.BooleanVar(value=False);self.filter=tk.StringVar();self.connection=tk.StringVar(value='离线预览 · 不连接设备' if offline else '正在读取机器人状态…')
        self.phase=tk.StringVar(value='未发送动作');self.video_notice=tk.StringVar(value='等待摄像头画面');self.param_notice=tk.StringVar(value='尚未读取参数')
        self.build();root.protocol('WM_DELETE_WINDOW',self.close)
        self.log('控制台已打开；只读连接，不自动启动 Robot、Home 或遥操。')
        root.after(100,self.consume)
        if not offline:root.after(250,self.poll);root.after(1600,self.refresh_parameters)
        else:self.connection.set('离线预览 · 所有设备操作已禁用')

    def build(self):
        r=self.root;r.title('Gento Luna · 协作搬运控制台');w=min(1480,int(r.winfo_screenwidth()*.94));h=min(1000,int(r.winfo_screenheight()*.91))
        self.scale=max(1,r.winfo_fpixels('1i')/96)
        r.geometry(f'{w}x{h}');r.minsize(min(int(1100*self.scale),int(r.winfo_screenwidth()*.95)),min(int(740*self.scale),int(r.winfo_screenheight()*.95)));r.state('zoomed');r.configure(bg=BG);r.option_add('*Font',('Microsoft YaHei UI',10))
        style=ttk.Style(r);style.theme_use('clam');style.configure('TFrame',background=BG);style.configure('TLabel',background=BG,foreground=INK)
        style.configure('Card.TFrame',background='white');style.configure('Card.TLabel',background='white',foreground=INK)
        style.configure('TButton',padding=(12,9),font=('Microsoft YaHei UI',10));style.configure('Primary.TButton',background=BLUE,foreground='white')
        style.map('Primary.TButton',background=[('active','#0e5475'),('disabled','#a5b3bf')]);style.configure('Stop.TButton',background=RED,foreground='white')
        style.map('Stop.TButton',background=[('active','#8f1f2c')]);style.configure('Treeview',rowheight=int(26*self.scale),font=('Microsoft YaHei UI',10));style.configure('Treeview.Heading',font=('Microsoft YaHei UI',10,'bold'))
        style.configure('TNotebook',background=BG);style.configure('TNotebook.Tab',padding=(20,9));style.configure('TLabelframe',background='white');style.configure('TLabelframe.Label',background='white',foreground=INK,font=('Microsoft YaHei UI',11,'bold'))
        outer=ttk.Frame(r,padding=16);outer.pack(fill='both',expand=True)
        header=ttk.Frame(outer);header.pack(fill='x',pady=(0,12))
        ttk.Label(header,text='Gento Luna 协作搬运',font=('Microsoft YaHei UI',23,'bold')).pack(side='left')
        ttk.Label(header,textvariable=self.connection,foreground=GRAY,font=('Microsoft YaHei UI',11)).pack(side='right')
        ttk.Label(outer,text='PICO · 双臂 / 躯干 / 夹爪 · 底盘前后、横移与转向',foreground=GRAY).pack(anchor='w',pady=(0,10))
        cards=ttk.Frame(outer);cards.pack(fill='x',pady=(0,12));self.cards={}
        for i,(key,label) in enumerate([('b1','电池 1'),('b2','电池 2'),('robot','机器人模式'),('pico','PICO 连接'),('maxhub','MAXHUB'),('fresh','控制器反馈')]):
            cards.columnconfigure(i,weight=1);f=ttk.Frame(cards,style='Card.TFrame',padding=(12,9));f.grid(row=0,column=i,padx=(0,8),sticky='nsew')
            ttk.Label(f,text=label,style='Card.TLabel',foreground=GRAY).pack(anchor='w')
            v=ttk.Label(f,text='—',style='Card.TLabel',font=('Microsoft YaHei UI',16,'bold'));v.pack(anchor='w',pady=(4,0));self.cards[key]=v
        self.low_notice=ttk.Label(outer,text='',foreground=RED,font=('Microsoft YaHei UI',11,'bold'));self.low_notice.pack(anchor='w')
        self.tabs=ttk.Notebook(outer);self.tabs.pack(fill='both',expand=True,pady=(6,0))
        overview=ttk.Frame(self.tabs,padding=12);params=ttk.Frame(self.tabs,padding=12);joints=ttk.Frame(self.tabs,padding=12);logs=ttk.Frame(self.tabs,padding=12)
        for panel,name in [(overview,'快捷操作'),(params,'所有参数'),(joints,'关节 / 夹爪状态'),(logs,'运行记录')]:self.tabs.add(panel,text=name)
        self.build_overview(overview);self.build_params(params);self.build_joints(joints)
        row=ttk.Frame(logs);row.pack(fill='x');ttk.Button(row,text='导出当前检查记录',command=self.export).pack(side='left');ttk.Button(row,text='打开本地记录目录',command=lambda:self.open_path(self.log_path.parent)).pack(side='left',padx=8)
        self.full_log=tk.Text(logs,bg='white',fg=INK,wrap='word',state='disabled',relief='flat');self.full_log.pack(fill='both',expand=True,pady=(10,0))
        ttk.Label(outer,text='关闭此窗口不会停止机器人或投屏。需要暂停输入时点“暂停遥操”；现场急停使用实体按钮。',foreground=GRAY).pack(anchor='w',pady=(10,0))

    def build_overview(self,p):
        p.columnconfigure(0,weight=0,minsize=int(360*self.scale));p.columnconfigure(1,weight=1);p.rowconfigure(1,weight=1)
        strip=ttk.Frame(p,style='Card.TFrame',padding=10);strip.grid(row=0,column=0,columnspan=2,sticky='ew',pady=(0,10))
        self.config_line=ttk.Label(strip,text='参数尚未读取 · 手部 / 肘部缩放、底盘速度与工具参数将在检查后显示',style='Card.TLabel');self.config_line.pack(anchor='w')
        left=ttk.Frame(p,style='Card.TFrame',padding=8);left.grid(row=1,column=0,sticky='nsew',padx=(0,12));left.columnconfigure(0,weight=1);left.rowconfigure(0,weight=1)
        self.action_canvas=tk.Canvas(left,bg='white',highlightthickness=0,width=int(350*self.scale));self.action_canvas.grid(row=0,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(left,orient='vertical',command=self.action_canvas.yview);scroll.grid(row=0,column=1,sticky='ns');self.action_canvas.configure(yscrollcommand=scroll.set)
        actions=ttk.Frame(self.action_canvas,style='Card.TFrame',padding=6);self.action_window=self.action_canvas.create_window((0,0),window=actions,anchor='nw')
        actions.bind('<Configure>',lambda e:self.action_canvas.configure(scrollregion=self.action_canvas.bbox('all')))
        self.action_canvas.bind('<Configure>',lambda e:self.action_canvas.itemconfigure(self.action_window,width=e.width))
        self.root.bind_all('<MouseWheel>',self.scroll_actions,add='+')
        actions.columnconfigure(0,weight=1);actions.columnconfigure(1,weight=1)
        ttk.Label(actions,text='快捷启动',style='Card.TLabel',font=('Microsoft YaHei UI',14,'bold')).grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,8))
        self.buttons={}
        specs=[('读取状态',self.manual_status,None),('只读预检',self.preflight,None),('连接 PICO USB',self.usb_start,None),('恢复摄像头 / 投屏',lambda:self.action('display'),None),('仅连接 Robot',lambda:self.action('ready'),'support'),('一键就绪（阻抗）',lambda:self.action('prepare'),'support'),('启动 PICO 遥操',lambda:self.action('teleop'),'support'),('HOME 归位',self.home,'home')]
        for i,(label,fn,gate) in enumerate(specs):
            b=ttk.Button(actions,text=label,command=fn,style='Primary.TButton' if label in ['一键就绪（阻抗）','启动 PICO 遥操'] else 'TButton')
            b.grid(row=3+i//2,column=i%2,sticky='ew',padx=3,pady=4);self.buttons[label]=(b,gate)
        ttk.Checkbutton(actions,text='双腕已支撑，手柄已松开',variable=self.supported,command=self.update_buttons).grid(row=1,column=0,columnspan=2,sticky='w',pady=(4,5))
        ttk.Label(actions,text='首次就绪可能产生保持力，请先放稳夹持物。\n一键准备不自动归位；Home 需单独确认。',style='Card.TLabel',foreground=GRAY,wraplength=int(330*self.scale)).grid(row=2,column=0,columnspan=2,sticky='w',pady=(0,9))
        self.stop_button=ttk.Button(left,text='暂停遥操 · 保留 Robot 当前模式',style='Stop.TButton',command=self.pause);self.stop_button.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(8,2))
        modebox=ttk.LabelFrame(actions,text='模式 / 故障',padding=8);modebox.grid(row=7,column=0,columnspan=2,sticky='ew',pady=(12,4))
        for i,(label,mode) in enumerate([('位置',1),('阻抗',3),('待机',0)]):
            b=ttk.Button(modebox,text=label,command=lambda m=mode:self.action('mode',{'mode':m}));b.grid(row=0,column=i,padx=2,sticky='ew');modebox.columnconfigure(i,weight=1);self.buttons['mode'+str(mode)]=(b,'support')
        b=ttk.Button(modebox,text='仅清故障（不归位）',command=lambda:self.action('clear'));b.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(8,0));self.buttons['clear']=(b,'support')
        b=ttk.Button(modebox,text='断开 Robot',command=self.stop_robot);b.grid(row=1,column=2,sticky='ew',pady=(8,0));self.buttons['robot_stop']=(b,'support')
        ttk.Label(actions,textvariable=self.phase,style='Card.TLabel',foreground=BLUE,wraplength=int(330*self.scale)).grid(row=8,column=0,columnspan=2,sticky='w',pady=(10,4))
        right=ttk.Frame(p,style='Card.TFrame',padding=10);right.grid(row=1,column=1,sticky='nsew');right.rowconfigure(1,weight=1);right.columnconfigure(0,weight=1)
        vr=ttk.Frame(right,style='Card.TFrame');vr.grid(row=0,column=0,sticky='ew');ttk.Label(vr,text='实时画面',style='Card.TLabel',font=('Microsoft YaHei UI',13,'bold')).pack(side='left');ttk.Button(vr,text='重新连接画面',command=self.restart_video).pack(side='right')
        self.canvas=tk.Canvas(right,bg='#071522',highlightthickness=0,height=310);self.canvas.grid(row=1,column=0,sticky='nsew',pady=8);self.canvas.bind('<Configure>',lambda e:self.draw_frame())
        ttk.Label(right,textvariable=self.video_notice,style='Card.TLabel',foreground=GRAY).grid(row=2,column=0,sticky='w')
        self.service_line=ttk.Label(right,text='模块状态尚未读取',style='Card.TLabel',foreground=GRAY,wraplength=750);self.service_line.grid(row=3,column=0,sticky='w',pady=8)
        self.preview_log=tk.Text(p,height=5,bg='white',fg=INK,relief='flat',wrap='word',state='disabled');self.preview_log.grid(row=2,column=0,columnspan=2,sticky='ew',pady=(10,0))
        self.draw_frame();self.update_buttons()

    def build_params(self,p):
        top=ttk.Frame(p);top.pack(fill='x');ttk.Label(top,text='筛选参数').pack(side='left');entry=ttk.Entry(top,textvariable=self.filter,width=35);entry.pack(side='left',padx=8);self.filter.trace_add('write',lambda *_:self.render_parameters())
        ttk.Button(top,text='刷新全部参数',command=self.refresh_parameters).pack(side='left');ttk.Button(top,text='导出检查记录',command=self.export).pack(side='left',padx=8)
        ttk.Label(p,textvariable=self.param_notice,foreground=GRAY).pack(anchor='w',pady=8)
        table=ttk.Frame(p);table.pack(fill='both',expand=True);table.columnconfigure(0,weight=1);table.rowconfigure(0,weight=1)
        self.param_tree=ttk.Treeview(table,columns=('file','key','saved','live','state'),show='headings',height=12)
        for key,label,width in [('file','参数组',150),('key','参数名称',290),('saved','已保存值',360),('live','运行中读回',290),('state','检查状态',110)]:self.param_tree.heading(key,text=label);self.param_tree.column(key,width=width,minwidth=70,stretch=True)
        self.param_tree.grid(row=0,column=0,sticky='nsew');self.param_tree.bind('<<TreeviewSelect>>',self.show_parameter_source)
        ys=ttk.Scrollbar(table,orient='vertical',command=self.param_tree.yview);ys.grid(row=0,column=1,sticky='ns')
        xs=ttk.Scrollbar(table,orient='horizontal',command=self.param_tree.xview);xs.grid(row=1,column=0,sticky='ew');self.param_tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        self.param_tree.tag_configure('same',foreground=GREEN);self.param_tree.tag_configure('different',foreground=RED);self.param_tree.tag_configure('file',foreground=GRAY)
        self.source_label=ttk.Label(p,text='选择一行查看原始文件、来源与 SHA-256',foreground=GRAY);self.source_label.pack(anchor='w',pady=(10,3))
        sourcebox=ttk.Frame(p);sourcebox.pack(fill='x');sourcebox.columnconfigure(0,weight=1)
        self.raw_source=tk.Text(sourcebox,height=9,wrap='none',bg='white',fg=INK,state='disabled',relief='flat');self.raw_source.grid(row=0,column=0,sticky='ew')
        raw_y=ttk.Scrollbar(sourcebox,orient='vertical',command=self.raw_source.yview);raw_y.grid(row=0,column=1,sticky='ns')
        raw_x=ttk.Scrollbar(sourcebox,orient='horizontal',command=self.raw_source.xview);raw_x.grid(row=1,column=0,sticky='ew');self.raw_source.configure(yscrollcommand=raw_y.set,xscrollcommand=raw_x.set)

    def build_joints(self,p):
        ttk.Label(p,text='角度/速度来自当前关节反馈；超过 1 秒的数据标为过期。限位列是模型记录，J6 另有厂家实读 ±60° 历史记录。',foreground=GRAY,wraplength=1300).pack(anchor='w',pady=(0,10))
        self.joint_tree=ttk.Treeview(p,columns=('group','joint','position','velocity','effort','min','max','state'),show='headings')
        for key,label,width in [('group','部位',80),('joint','关节',100),('position','角度 °',130),('velocity','速度 °/s',130),('effort','力矩 Nm',130),('min','模型下限 °',140),('max','模型上限 °',140),('state','反馈状态',130)]:self.joint_tree.heading(key,text=label);self.joint_tree.column(key,width=width,stretch=True)
        self.joint_tree.pack(fill='both',expand=True);self.joint_tree.tag_configure('error',foreground=RED);self.joint_tree.tag_configure('stale',foreground=GRAY)
        self.gripper_line=ttk.Label(p,text='夹爪反馈尚未读取',foreground=GRAY);self.gripper_line.pack(anchor='w',pady=10)

    def log(self,text,kind='info'):
        stamp=datetime.now().strftime('%H:%M:%S');line=f'{stamp}  {text}\n'
        for widget in [getattr(self,'preview_log',None),getattr(self,'full_log',None)]:
            if widget is None:continue
            widget.configure(state='normal');widget.insert('end',line);widget.see('end');widget.configure(state='disabled')
        with self.log_path.open('a',encoding='utf-8') as f:f.write(json.dumps({'time':datetime.now().isoformat(),'kind':kind,'message':text},ensure_ascii=False)+'\n')

    def launch_job(self,cmd,args=None,callback=None,quiet=False,emergency=False):
        if self.offline:return
        if self.busy and not emergency:
            if not quiet:self.log('正在处理上一项操作，请稍候。')
            return
        if not quiet and not emergency:self.busy=True;self.phase.set('正在处理…');self.update_buttons()
        def work():
            client=RemoteClient(self.profile) if emergency else self.remote
            try:
                if cmd in {'ready','prepare','teleop','home','mode','clear','robot_stop'} and direct_controller_connection(self.profile):raise RuntimeError('检测到本机直接连接控制器，请先断开 FXPlatform，再使用本控制台。')
                value=client.request(cmd,args)
                self.events.put(('result',(cmd,value,callback,quiet,emergency)))
            except Exception as exc:self.events.put(('error',(cmd,str(exc),quiet,emergency)))
            finally:
                if emergency:client.close()
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        if self.closing:return
        if not self.busy and not self.polling:
            self.polling=True;self.launch_job('status',callback=self.apply_status,quiet=True)
        if time.monotonic()-self.status_time>6:
            self.connected=False;self.connection.set('连接未确认 · 请检查网线/机器人');self.update_buttons()
            for key in ['b1','b2','robot','pico','maxhub','fresh']:self.cards[key].configure(text='未知',foreground=GRAY)
        self.root.after(1600,self.poll)

    def consume(self):
        if self.closing:return
        for _ in range(40):
            try:kind,payload=self.events.get_nowait()
            except queue.Empty:break
            if kind=='result':
                cmd,value,callback,quiet,emergency=payload
                if cmd=='status':self.polling=False
                if callback:callback(value)
                if not quiet:
                    if not emergency:self.busy=False
                    summaries={'status':'状态已刷新','parameters':'全部参数已读取','preflight':'预检通过' if value.get('passed') else '预检有未通过项'}
                    message=summaries.get(cmd) or (value.get('message','操作已完成') if isinstance(value,dict) else str(value))
                    self.phase.set(message);self.log(message);self.update_buttons()
                    if isinstance(value,dict) and value.get('state') and value['state'].get('control_error'):self.log(value['state'].get('control_error_message','控制器报错'),'error')
            elif kind=='error':
                cmd,text,quiet,emergency=payload
                if cmd=='status':self.polling=False;self.connected=False;self.connection.set('连接失败 · '+text[:75])
                if cmd=='status' and text!=getattr(self,'last_connection_error',None):self.log(text,'connection');self.last_connection_error=text
                if not quiet:
                    if not emergency:self.busy=False
                    self.phase.set('操作未完成：'+text);self.log(text,'error')
                self.update_buttons()
            elif kind=='diagnostic':self.log(payload,'diagnostic')
            elif kind=='video_notice':
                if time.monotonic()-self.frame_time>3:self.video_notice.set(payload[:130])
            elif kind=='usb':
                ok,text=payload;self.busy=False;self.phase.set('USB 准备完成' if ok else 'USB 准备未完成');self.log(text,'info' if ok else 'error');self.update_buttons()
        try:
            frame=self.frame_queue.get_nowait();self.original_image=Image.open(io.BytesIO(base64.b64decode(frame['frame']))).convert('RGB');self.frame_time=time.monotonic();self.video_stale=False;self.draw_frame();self.video_notice.set('实时预览 · 约 2 帧/秒 · 原摄像头采集设置保持不变')
        except queue.Empty:pass
        except (tk.TclError,OSError,ValueError) as exc:self.video_notice.set('画面解码失败：'+str(exc)[:100])
        if self.frame_time and time.monotonic()-self.frame_time>3 and not getattr(self,'video_stale',False):
            self.video_stale=True;self.video_notice.set('画面已过期，不能作为实时画面判断');self.draw_frame()
        self.root.after(90,self.consume)

    def apply_status(self,value):
        self.last_status=value;self.status_time=time.monotonic();self.connected=True;self.connection.set('已连接  '+self.profile['robot_ip']+'  ·  '+datetime.now().strftime('%H:%M:%S'))
        b=value.get('battery') or {};rows=b.get('batteries',[]) if b.get('fresh') else [];low=False
        for i,key in enumerate(['b1','b2']):
            row=next((x for x in rows if x.get('id')==i+1 and x.get('is_connected') and x.get('is_in_place')),None)
            text='未知';color=GRAY
            if row:
                n=row.get('energy');text=f'{n}%'+(' · 充电中' if row.get('is_charging') else ' · 使用中');color=RED if n<30 else GREEN;low=low or n<30
            self.cards[key].configure(text=text,foreground=color)
        self.low_notice.configure(text='电量低于 30%，请优先充电；本项目有低电量相关报警历史' if low else ('电量反馈未知，无法判断是否低于 30%' if len(rows)!=2 else ''))
        state=value.get('robot') or {};age=state.get('arm_state_age_sec');fresh=age is not None and age<1
        arms=state.get('arm_state') or [];mode=state.get('current_mode');name={0:'待机 · 无保持',1:'位置模式',2:'阻抗模式',3:'阻抗请求'}.get(mode,'未就绪')
        if state.get('control_error'):name='故障';color=RED
        else:color=GREEN if fresh and state.get('control_ready') else GRAY
        self.cards['robot'].configure(text=name if fresh else '未连接/过期',foreground=color)
        self.cards['fresh'].configure(text=f'{age:.3f} 秒' if fresh else '无新鲜反馈',foreground=GREEN if fresh else GRAY)
        vr=value.get('topics',{}).get('/info/vr_connected',{});active=vr.get('age',999)<1 and vr.get('data',{}).get('data') is True
        self.cards['pico'].configure(text='已连接' if active else '未连接/休眠',foreground=GREEN if active else GRAY)
        services=value.get('services',{});mh=services.get('luna-maxhub-client.service',{}).get('ActiveState')=='active' and (value.get('maxhub') or {}).get('state')=='running'
        self.cards['maxhub'].configure(text='客户端运行' if mh else '待恢复',foreground=GREEN if mh else GRAY)
        self.service_line.configure(text='  ·  '.join(label+(' ✓' if services.get(unit,{}).get('ActiveState')=='active' else ' —') for unit,label in MODULES.items()))
        self.update_joints(value);self.update_buttons()
        if services.get('apex-camera.service',{}).get('ActiveState')=='active':self.video.start()

    def update_joints(self,value):
        fb=value.get('topics',{}).get('/info/joint_feedback',{});fresh=fb.get('age',999)<1;data=fb.get('data',{});limits=value.get('model_limits_deg',{})
        rows=[]
        for group,prefix,count,key in [('左臂','Arm_L',7,'arm'),('右臂','Arm_R',7,'arm'),('躯干','Leg_J',6,'body'),('头部','Head_J',2,'head')]:
            for j in range(count):
                index=j+(7 if group=='右臂' else 0);name=f'{prefix}{j+1}_Joint' if key=='arm' else f'{prefix}{j+1}' + ('_joint' if key=='head' else '_Joint')
                def item(suffix,angle=False):
                    vs=data.get(key+'_'+suffix,[])
                    if not fresh or len(vs)<=index:return '—'
                    n=vs[index];return f'{math.degrees(n) if angle else n:.3f}'
                bounds=limits.get(name);tag='stale' if not fresh else ''
                if key=='arm' and j==5 and fresh and abs(float(item('positions',True)))>60:tag='error'
                rows.append((group,'J'+str(j+1),item('positions',True),item('velocities',True),item('efforts'),f'{bounds[0]:.1f}' if bounds else '—',f'{bounds[1]:.1f}' if bounds else '—','新鲜' if fresh else '过期/未读'))
                iid=f'{key}-{group}-{j}'
                if self.joint_tree.exists(iid):self.joint_tree.item(iid,values=rows[-1],tags=(tag,))
                else:self.joint_tree.insert('', 'end',iid=iid,values=rows[-1],tags=(tag,))
        parts=[]
        for side,topic in [('左','/info/wrist485_L'),('右','/info/wrist485_R')]:
            v=value.get('topics',{}).get(topic,{})
            parts.append(side+'夹爪：'+(text_value(v.get('data',{}).get('data')) if v.get('age',999)<2 else '无新鲜反馈'))
        self.gripper_line.configure(text='  |  '.join(parts)+'   （位置、速度、状态、故障、报警）')

    def update_buttons(self):
        for name,(button,gate) in getattr(self,'buttons',{}).items():
            enabled=not self.offline and not self.busy
            if gate:enabled=enabled and self.connected and self.supported.get()
            if name=='启动 PICO 遥操':enabled=enabled and ((self.last_status or {}).get('robot',{}).get('arm_state') or [])[:2]==[2,2]
            button.configure(state='normal' if enabled else 'disabled')
        if hasattr(self,'stop_button'):self.stop_button.configure(state='normal' if self.connected and not self.offline else 'disabled')

    def manual_status(self):self.launch_job('status',callback=self.apply_status)
    def preflight(self):self.launch_job('preflight',callback=self.show_preflight)
    def show_preflight(self,result):
        self.apply_status(result['status']);self.log('\n'.join(('✓ ' if c['level']=='ok' else '！ ')+c['text'] for c in result['checks']))
        self.phase.set('预检通过' if result['passed'] else '预检有未通过项')
        messagebox.showinfo('只读预检', '\n'.join(c['text'] for c in result['checks']),parent=self.root)
    def action(self,cmd,args=None):
        values=dict(args or {},supported=self.supported.get());self.log('请求：'+{'ready':'连接 Robot','prepare':'一键就绪（阻抗）','teleop':'启动 PICO 遥操','display':'恢复显示服务','clear':'仅清故障','mode':'切换模式'}.get(cmd,cmd))
        self.launch_job(cmd,values)
    def pause(self):self.log('请求暂停遥操输入');self.launch_job('pause',emergency=True)
    def home(self):
        if messagebox.askyesno('确认 HOME 归位','Home 会移动双臂/躯干。请确认夹持物已放稳、归位路径畅通、现场有人监督。\n\n现在发送 Home？',parent=self.root):self.action('home',{'home_confirmed':True})
    def stop_robot(self):
        if messagebox.askyesno('断开 Robot','腕部无抱闸，停止 Robot 后没有关节保持。确认双腕有稳固支撑，再断开？\n\n摄像头、MAXHUB 和电量提示将继续运行。',parent=self.root):self.action('robot_stop')

    def refresh_parameters(self):self.launch_job('parameters',callback=self.apply_parameters)
    def apply_parameters(self,value):
        self.last_params=value;self.param_rows=[];used=set()
        for index,f in enumerate(value.get('files',[])):
            parsed=f.get('values');live_node='marvin_robot_node' if f['label'].startswith('Robot ') else 'VR_reader' if f['label'].startswith('PICO ') else None
            runtime=value.get('live',{}).get(live_node) if live_node else None
            if f.get('error'):self.param_rows.append((index,f['label'],'文件读取','—','—','不可读','different'));continue
            fields=list(flatten(parsed)) if parsed is not None else [('原始文件',f.get('text','')[:130])]
            for key,saved in fields:
                short=key.split('ros__parameters.',1)[-1];current=runtime.get(short) if runtime else None
                readable=runtime is not None and short in runtime and current is not None
                if readable:used.add((live_node,short))
                same=readable and saved==current;state='一致' if same else '有差异' if readable else '仅保存值'
                self.param_rows.append((index,f['label'],short,saved,current,state,'same' if same else 'different' if readable else 'file'))
        for node,values in value.get('live',{}).items():
            for key,current in (values or {}).items():
                if (node,key) not in used:self.param_rows.append((None,'运行参数 · '+node,key,None,current,'运行读回','same'))
        robot=next((f.get('values') for f in value.get('files',[]) if f['label'].startswith('PICO ')),{}) or {}
        params=(robot.get('/**') or {}).get('ros__parameters',{});table=params.get('human_scale_table',{})
        caps=value.get('chassis_effective_caps');cap_text=f"{caps['linear']:g} m/s · {caps['angular']:g} rad/s" if caps else '当前配置未读回（原桥封顶 0.2 / 0.2）'
        self.config_line.configure(text=f"已保存映射 · 手部 L/R {table.get('left_hand','—')} / {table.get('right_hand','—')}    肘部 L/R {table.get('left_elbow','—')} / {table.get('right_elbow','—')}    底盘有效上限 {cap_text}")
        self.param_notice.set('只读检查 · '+datetime.now().strftime('%H:%M:%S')+' · 文件值与运行读回分开标记；未运行的模块显示“仅保存值”。')
        self.render_parameters();self.phase.set('参数读取完成')
    def render_parameters(self):
        for item in self.param_tree.get_children():self.param_tree.delete(item)
        query=self.filter.get().strip().casefold()
        for n,row in enumerate(self.param_rows):
            index,label,key,saved,live,state,tag=row
            if query and query not in (label+' '+key+' '+text_value(saved)).casefold():continue
            self.param_tree.insert('','end',iid=str(n),values=(label,key,text_value(saved),text_value(live),state),tags=(tag,))
    def show_parameter_source(self,event=None):
        selected=self.param_tree.selection()
        if not selected or not self.last_params:return
        row=self.param_rows[int(selected[0])]
        if row[0] is None:
            self.source_label.configure(text=row[1]+' · ROS 运行参数读回，不是磁盘配置文件')
            self.raw_source.configure(state='normal');self.raw_source.delete('1.0','end');self.raw_source.insert('1.0',text_value(row[4]));self.raw_source.configure(state='disabled');return
        f=self.last_params['files'][row[0]]
        self.source_label.configure(text=f['path']+'  |  SHA-256: '+f.get('sha256','不可读'))
        self.raw_source.configure(state='normal');self.raw_source.delete('1.0','end');self.raw_source.insert('1.0',f.get('text',f.get('error','')));self.raw_source.configure(state='disabled')

    def usb_start(self):
        if self.busy or self.offline:return
        self.busy=True;self.phase.set('正在建立 PICO USB 网络…');self.update_buttons()
        def work():
            try:
                path=Path(self.profile['usb_dir'])/'Start-Luna-USB.ps1'
                if not path.exists():raise FileNotFoundError('未找到原 PICO USB 准备程序')
                p=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(path)],cwd=path.parent,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',timeout=120,creationflags=NO_WINDOW)
                self.events.put(('usb',(p.returncode==0,p.stdout[-4000:])))
            except Exception as exc:self.events.put(('usb',(False,str(exc))))
        threading.Thread(target=work,daemon=True).start()
    def new_frame(self,value):
        try:self.frame_queue.put_nowait(value)
        except queue.Full:
            try:self.frame_queue.get_nowait()
            except queue.Empty:pass
            try:self.frame_queue.put_nowait(value)
            except queue.Full:pass
    def draw_frame(self):
        if not hasattr(self,'canvas'):return
        self.canvas.delete('all');w=max(1,self.canvas.winfo_width());h=max(1,self.canvas.winfo_height())
        if hasattr(self,'original_image'):
            ratio=min(w/self.original_image.width,h/self.original_image.height);size=(max(1,int(self.original_image.width*ratio)),max(1,int(self.original_image.height*ratio)))
            self.display_photo=ImageTk.PhotoImage(self.original_image.resize(size,Image.Resampling.BILINEAR))
            self.canvas.create_image(w/2,h/2,image=self.display_photo,anchor='center')
            if getattr(self,'video_stale',False):
                self.canvas.create_rectangle(0,0,w,38,fill=RED,outline='');self.canvas.create_text(w/2,19,text='画面已过期 · 等待新鲜视频帧',fill='white',font=('Microsoft YaHei UI',11,'bold'))
        else:self.canvas.create_text(w/2,h/2,text='摄像头预览\n不启动额外采集、不占用 PICO 视频房间',fill='#a2b3c5',font=('Microsoft YaHei UI',12),justify='center')
    def scroll_actions(self,event):
        x,y=self.root.winfo_pointerxy()
        c=self.action_canvas
        if c.winfo_rootx()<=x<c.winfo_rootx()+c.winfo_width() and c.winfo_rooty()<=y<c.winfo_rooty()+c.winfo_height():
            c.yview_scroll(-int(event.delta/120),'units')
    def restart_video(self):
        if self.offline:return
        self.video.close();self.video_notice.set('正在重新订阅画面…');self.video.start()
    def export(self):
        path=filedialog.asksaveasfilename(parent=self.root,title='保存参数与状态检查记录',defaultextension='.json',initialfile='Luna-check-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json',filetypes=[('JSON 记录','*.json')])
        if path:
            Path(path).write_text(json.dumps({'exported_at':datetime.now().isoformat(),'status':self.last_status,'parameters':self.last_params,'read_only_snapshot':True},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');self.log('检查记录已保存：'+path)
    def open_path(self,path):
        import os
        os.startfile(str(path))
    def close(self):
        self.closing=True;self.remote.close();self.video.close();self.root.destroy()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');args=parser.parse_args()
    # DPI-aware native UI; no desktop automation or external SDK process.
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:pass
    root=tk.Tk()
    instance_lock=None
    if sys.platform=='win32':
        import msvcrt
        instance_lock=(ROOT/'ui.lock').open('a+b')
        if instance_lock.tell()==0:instance_lock.write(b'1');instance_lock.flush()
        instance_lock.seek(0)
        try:msvcrt.locking(instance_lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            root.withdraw();messagebox.showinfo('控制台已打开','控制台已经在运行，请切回现有窗口。');root.destroy();return
    try:root.iconbitmap(str(ROOT/'luna-console.ico'))
    except tk.TclError:pass
    Console(root,args.offline);root.mainloop()

if __name__=='__main__':main()
