import json, math, pathlib

base = pathlib.Path(__file__).resolve().parent
events = [json.loads(s) for s in (base / 'telemetry.jsonl').read_text().splitlines()]
checks = [json.loads(s) for s in (base / 'safety-monitor.jsonl').read_text().splitlines()]
result = json.loads((base / 'run-result.json').read_text())
commands = [e['command'] for e in events if e['event'] == 'command_sent']
feedback = [e for e in events if e['event'] == 'feedback']
summary = {
    'completed': result['completed'], 'reason': result['reason'],
    'recorded_seconds': events[-1]['mono'] - events[0]['mono'],
    'command_count': len(commands), 'feedback_count': len(feedback),
    'max_command_linear_m_s': max((math.hypot(c[0], c[1]) for c in commands), default=0),
    'max_command_angular_rad_s': max((abs(c[2]) for c in commands), default=0),
    'command_caps_respected': all(math.hypot(c[0], c[1]) <= .200001 and abs(c[2]) <= .200001 for c in commands),
    'command_directions_observed': {name: any(c[i] * sign > .001 for c in commands)
        for name, i, sign in [('forward',0,1),('backward',0,-1),('left',1,1),('right',1,-1),('turn_left',2,1),('turn_right',2,-1)]},
    'zero_commands': sum(not any(c) for c in commands),
    'safety_check_count': len(checks),
    'all_arm_checks_healthy': all(not s['robot']['control_error'] and s['robot']['control_ready'] and s['robot']['arm_state'][:2] == [2,2] for s in checks),
    'feedback_with_driver_errors': sum(bool(e.get('driver_errors')) for e in feedback),
    'feedback_with_unsafe_flags': sum(any(e.get('flags',{}).values()) for e in feedback),
    'final_batteries': checks[-1]['batteries']['batteries'] if checks else [],
    'last_command': commands[-1] if commands else None,
    'last_event': events[-1]['event'],
    'bridge_exit_code': result.get('bridge_exit_code'),
}
(base / 'test-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
