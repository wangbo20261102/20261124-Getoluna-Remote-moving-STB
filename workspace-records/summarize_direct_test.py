import collections,json,math,pathlib,sys,time
p=pathlib.Path(sys.argv[1])
events=[]
for line in p.read_text().splitlines():
    try: events.append(json.loads(line))
    except json.JSONDecodeError: pass
commands=[x for x in events if x['event']=='command_sent']
feedback=[x for x in events if x['event']=='feedback']
max_cmd=[0.,0.,0.]
min_cmd=[0.,0.,0.]
max_feedback=[0.,0.,0.]
peaks=[None,None,None]
current=[0.,0.,0.]
for e in events:
    if e['event']=='command_sent':
        current=e['command']
        max_cmd=[max(a,b) for a,b in zip(max_cmd,current)]
        min_cmd=[min(a,b) for a,b in zip(min_cmd,current)]
    if e['event']=='feedback':
        v=e.get('velocity') or {}
        vals=[float(v.get('x',0)),float(v.get('y',0)),float(e.get('angular') or 0)]
        for i,value in enumerate(vals):
            if abs(value)>max_feedback[i]:
                max_feedback[i]=abs(value)
                peaks[i]={'mono':e['mono'],'feedback':vals,'preceding_command':current}
start=next((e for e in events if e['event']=='start'),{})
last=feedback[-1] if feedback else {}
print(json.dumps({'elapsed_sec':round(time.monotonic()-start.get('mono',time.monotonic()),1),'events':len(events),'command_count':len(commands),'stop_count':sum(e['command']==[0,0,0] for e in commands),'cmd_min':min_cmd,'cmd_max':max_cmd,'max_abs_feedback':max_feedback,'peaks':peaks,'last_feedback':last,'last_command':commands[-1] if commands else None,'exited':any(e['event']=='exit' for e in events)},ensure_ascii=False))
