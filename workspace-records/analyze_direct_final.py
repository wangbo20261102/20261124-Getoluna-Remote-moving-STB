import json,math,pathlib
base=pathlib.Path(r'E:\Github\Mubea-EV-Gentoluna\teleop-20261123\reports')
events=[json.loads(line) for line in (base/'pico-chassis-direct-5min-20261124-run2.jsonl').read_text().splitlines()]
start=next(e for e in events if e['event']=='start')
end=next(e for e in reversed(events) if e['event']=='exit')
commands=[e for e in events if e['event']=='command_sent']
feedback=[e for e in events if e['event']=='feedback']
max_linear=max(math.hypot(*e['command'][:2]) for e in commands)
max_angular=max(abs(e['command'][2]) for e in commands)
norms=sorted(math.hypot(float((e.get('velocity') or {}).get('x',0)),float((e.get('velocity') or {}).get('y',0))) for e in feedback)
quantile=lambda p:norms[min(len(norms)-1,int(p*(len(norms)-1)))]
report=json.loads((base/'pico-chassis-direct-20261124.json').read_text(encoding='utf-8-sig'))
report.update(test_status='Completed full 300-second supervised window; operator confirmed all mapping and direct-stick behavior correct',timer_seconds=300,recorded_seconds=round(end['mono']-start['mono'],3),events=len(events),command_count=len(commands),stop_count=sum(e['command']==[0,0,0] for e in commands),max_command_planar_m_s=max_linear,max_command_angular_rad_s=max_angular,command_caps_verified=max_linear<=.0800001 and max_angular<=.1000001,feedback_samples=len(feedback),feedback_planar_quantiles_m_s={'p50':quantile(.50),'p95':quantile(.95),'p99':quantile(.99),'peak':max(norms)},last_feedback=feedback[-1],last_command=commands[-1],operator_acceptance='All directions and no-press control confirmed normal; continue requested during test',configuration_timeouts=1,hardware_speed_acceptance='Not established; feedback exceeds command magnitude in some samples. Do not equate command caps with guaranteed physical speed.',bridge_exited=True,final_chassis_velocity=[0,0,0],maxhub='DongleClient PID7497 active; preview guard active; preview counter advanced through11760',test_log=str(base/'pico-chassis-direct-5min-20261124-run2.jsonl'))
(base/'pico-chassis-direct-20261124.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ('recorded_seconds','command_count','stop_count','max_command_planar_m_s','max_command_angular_rad_s','command_caps_verified','feedback_samples','feedback_planar_quantiles_m_s')},ensure_ascii=False))
