import argparse, datetime, json, math, pathlib, subprocess, sys, time

p = argparse.ArgumentParser()
p.add_argument('--attempt-position', action='store_true')
p.add_argument('--attempt-impedance', action='store_true')
args = p.parse_args()
attempt = args.attempt_position or args.attempt_impedance
if args.attempt_position and args.attempt_impedance:
    raise SystemExit('Choose only one diagnostic mode')
for service in ('apex-robot', 'apex-teleop', 'apex-tool'):
    if subprocess.run(['systemctl', 'is-active', '--quiet', service]).returncode == 0:
        raise SystemExit('Refusing second SDK owner: ' + service)
sys.path.insert(0, '/home/nvidia/tianji-robot-SDK/PYTHON_SDK')
from GentoRobot import GentoRobot, FXObjType, FXLogMask

out = pathlib.Path('/home/nvidia/luna-incidents/20261124-right-gripper-power')
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
result = {'attempt_position': args.attempt_position, 'attempt_impedance': args.attempt_impedance, 'time_robot': stamp,
          'parameter_writes': 0, 'home_or_trajectory_calls': 0, 'events': []}
robot = GentoRobot(precision=6)
right = FXObjType.OBJ_ARM1

def snapshot(label):
    data = {'label': label, 'mono': time.monotonic(), 'rt': robot.get_rt_dict(),
            'sg': robot.get_sg_dict(), 'servo_errors': {}, 'physical_state': {}}
    for name, obj in [('left', FXObjType.OBJ_ARM0), ('right', right)]:
        ret, message = robot.get_servo_error_codes(obj)
        data['servo_errors'][name] = {'ret': ret, 'text': message}
        data['physical_state'][name] = robot.get_ctrl_obj_physical_state(obj)
    result['events'].append(data)
    (out / ('exclusive-right-' + stamp + '.json')).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'label': label, 'states': [a['state'] for a in data['rt']['arms']],
                      'servo_errors': data['servo_errors'], 'physical_state': data['physical_state']},
                     ensure_ascii=False), flush=True)
    return data

try:
    result['link'] = robot.link(6, 6, 7, 190, FXLogMask.FX_LOG_ALL_FLAG)
    if result['link'] < 0:
        raise RuntimeError('Controller link failed')
    time.sleep(.5)
    before = snapshot('before')
    if attempt:
        if any(a['state']['cur'] != 0 for a in before['rt']['arms']):
            raise RuntimeError('Both arms must be idle before right-only diagnostic')
        error_lines = before['servo_errors']['right']['text'].splitlines()
        if before['servo_errors']['right']['ret'] or len(error_lines) != 7 or any('0x0000 - No error' not in line for line in error_lines):
            raise RuntimeError('Read right drive error before attempting enable')
        limits = []
        for j in range(7):
            row = {'joint': j + 1}
            for key in ('LimitNeg', 'LimitPos'):
                ret, value = robot.param_get_float(f'R.A1.L{j}.BASIC.{key}')
                if ret:
                    raise RuntimeError('Right joint limit read failed')
                row[key] = value
            limits.append(row)
        result['right_limits'] = limits
        fresh = robot.get_rt_dict()
        angles = fresh['arms'][1]['fb']['fb_pos']
        velocities = fresh['arms'][1]['fb']['fb_vel']
        if any(not math.isfinite(a) or not lim['LimitNeg'] + 1 <= a <= lim['LimitPos'] - 1
               for a, lim in zip(angles, limits)):
            raise RuntimeError('Right joint outside limit margin; no enable sent')
        if max(abs(v) for v in velocities) > .5:
            raise RuntimeError('Right arm is moving; no enable sent')
        result['hold_target_deg'] = angles
        result['seed_current_position_ret'] = robot.runtime_set_joint_pos_cmd(right, angles)
        if result['seed_current_position_ret']:
            raise RuntimeError('Failed to seed static hold at current position')
        time.sleep(.05)
        if args.attempt_impedance:
            gains = before['sg']['arms'][1]['set']
            k, d = gains['joint_k'], gains['joint_d']
            if any(not math.isfinite(v) or v < 0 for v in k + d) or not any(k):
                raise RuntimeError('Existing impedance gains invalid; no enable sent')
            result['impedance_gains_from_existing_runtime'] = {'k': k, 'd': d}
            result['impedance_ret'] = robot.switch_to_imp_joint_mode(right, 2000, 1, 1, k, d)
        else:
            result['position_ret'] = robot.switch_to_position_mode(right, 2000, 1, 1)
        time.sleep(.3)
        snapshot('after_right_impedance_request' if args.attempt_impedance else 'after_right_position_request')
except BaseException as exc:
    result['exception'] = repr(exc)
    print('DIAGNOSTIC:', repr(exc), flush=True)
finally:
    if robot._connected:
        if attempt and robot.current_state(right) in (1, 2):
            result['right_idle_ret'] = robot.switch_to_idle(right, 1500)
            time.sleep(.2)
        snapshot('final_before_unlink')
        robot.unlink()
    (out / ('exclusive-right-' + stamp + '.json')).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
