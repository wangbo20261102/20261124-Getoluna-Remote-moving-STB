import json,math,pathlib
base=pathlib.Path(__file__).parent
lines=(base/'telemetry.jsonl').read_text().splitlines()
events=[json.loads(line) for line in lines if line.strip()]
start=next(e for e in events if e['event']=='start')
end=next(e for e in reversed(events) if e['event']=='exit')
commands=[e for e in events if e['event']=='command_sent']
feedback=[e for e in events if e['event']=='feedback']
values=[e['command'] for e in commands]
max_linear=max((math.hypot(*v[:2]) for v in values),default=0.)
max_angular=max((abs(v[2]) for v in values),default=0.)
fb_linear=sorted(math.hypot(float((e.get('velocity') or {}).get('x',0)),float((e.get('velocity') or {}).get('y',0))) for e in feedback)
fb_angular=sorted(abs(float(e.get('angular') or 0)) for e in feedback)
q=lambda vals,p:vals[min(len(vals)-1,int(p*(len(vals)-1)))] if vals else None
verification=json.loads((base/'baseline-verification-after.json').read_text(encoding='utf-8'))
pre=json.loads((base/'preflight-chassis-config.json').read_text(encoding='utf-8-sig')).get('Content',{})
post=json.loads((base/'postflight-chassis-config.json').read_text(encoding='utf-8-sig')).get('Content',{})
changed_config=[k for k in sorted(set(pre)|set(post)) if pre.get(k)!=post.get(k)]
report={'date':'2026-11-24','baseline':r'E:\Github\Mubea-EV-Gentoluna-baselines\20261124-before-0p2','trial_directory':str(base),'runtime':'/home/nvidia/luna-test-runs/20261124-0p2-0p2/pico_chassis_bridge.py','program_sha256':'2dcbbf8b8c7e2ff5c1647e4545e693cd8e13fe2e16aa75e4d54dce1b6f040862','limits':{'planar_m_s':.2,'angular_rad_s':.2},'timer_seconds':300,'recorded_seconds':round(end['mono']-start['mono'],3),'command_count':len(commands),'stop_count':sum(v==[0,0,0] for v in values),'feedback_count':len(feedback),'max_command_planar_m_s':max_linear,'max_command_angular_rad_s':max_angular,'command_caps_verified':max_linear<=.2000001 and max_angular<=.2000001,'command_axis_min':[min(v[i] for v in values) if values else 0 for i in range(3)],'command_axis_max':[max(v[i] for v in values) if values else 0 for i in range(3)],'feedback_planar_m_s':{'p95':q(fb_linear,.95),'p99':q(fb_linear,.99),'peak':q(fb_linear,1)},'feedback_angular_rad_s':{'p95':q(fb_angular,.95),'p99':q(fb_angular,.99),'peak':q(fb_angular,1)},'last_feedback':feedback[-1] if feedback else None,'last_command':commands[-1] if commands else None,'final_live_velocity':[0,0,0],'bridge_exited':True,'baseline_verification':verification,'controller_configuration_changed_keys':changed_config,'maxhub':'Client PID7497 and preview guard checked active; preview frames still increasing','hardware_speed_note':'These are firmware-reported speeds. Command caps are verified separately; physical speed calibration and transient interpretation remain separate acceptance work.'}
report['status']='interrupted_by_user_for_right_wrist_fault'
report['completed_full_5_minutes']=False
report['interruption_reason']='User reported right wrist/gripper drooping and requested teleoperation stop. Do not resume PICO automatically.'
report['final_live_velocity_note']='The final recorded chassis feedback was zero; this is not a new live speed measurement at report generation.'
report.pop('final_live_velocity',None)
report['clock_note']='Use monotonic recorded_seconds. Robot wall clock is approximately 15 minutes ahead of the Windows host.'
(base/'trial-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['recorded_seconds','command_count','stop_count','feedback_count','max_command_planar_m_s','max_command_angular_rad_s','command_caps_verified','feedback_planar_m_s','feedback_angular_rad_s','controller_configuration_changed_keys']},ensure_ascii=False))
