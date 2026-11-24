import ctypes,json,pathlib,subprocess,sys
sys.path.insert(0,'/home/nvidia/tianji-robot-SDK/PYTHON_SDK')
import GentoRobot as g
base=pathlib.Path('/home/nvidia/luna-incidents/20261124-right-gripper-power')
raw=subprocess.check_output(['tshark','-r',str(base/'live-rt-3721-error.pcap'),'-T','fields','-e','udp.payload'],text=True)
samples=[]
for line in raw.splitlines():
    payload=bytes.fromhex(line.replace(':',''))
    if len(payload)!=ctypes.sizeof(g.ROBOT_RT)+2:continue
    rt=g.ROBOT_RT.from_buffer_copy(payload[2:])
    sample={'frame':rt.m_RT_FrameSerial,'arms':[]}
    for idx in (0,1):
        arm=rt.m_ARMS[idx]
        st=arm.m_ARM_State
        sample['arms'].append({'side':idx,'current_state':st.m_CurState,'command_state':st.m_CmdState,'error_code':st.m_ERRCode,'error_description':g.error_dict.get(st.m_ERRCode,'unknown'),'position_deg':list(arm.m_ARM_OUT.m_ARM_FBK_Joint_Pos),'command_deg':list(arm.m_ARM_IN.m_ARM_CMD_Joint_Pos)})
    samples.append(sample)
(base/'passive-live-error-decoded.json').write_text(json.dumps(samples,indent=2),encoding='utf-8')
print(json.dumps({'samples':len(samples),'first':samples[0] if samples else None,'payload_lengths':sorted({len(bytes.fromhex(x.replace(':',''))) for x in raw.splitlines() if x})}))
