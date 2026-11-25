import ast
import pathlib
import math
import sys
import threading
import types
import unittest


class Clock:
    def __init__(self): self.t = 100.0
    def time(self): return self.t
    def monotonic(self): return self.t
    def sleep(self, value): self.t += value


class Manager:
    active = False
    events = []
    def get_status(self, _): return {'active_state': 'active' if self.active else 'inactive'}
    def stop(self, _): Manager.events.append('stop'); Manager.active = False
    def start(self, _): Manager.events.append('start'); Manager.active = True


sys.modules['apex_backend.service_manager'] = types.SimpleNamespace(ServiceManager=Manager)
source = ast.parse(pathlib.Path(__file__).with_name('ros_state.py').read_text())
method = next(m for c in source.body if isinstance(c, ast.ClassDef) and c.name == 'ApexStateNode'
              for m in c.body if isinstance(m, ast.FunctionDef) and m.name == 'set_mode')
helpers = [m for c in source.body if isinstance(c, ast.ClassDef) and c.name == 'ApexStateNode'
           for m in c.body if isinstance(m, ast.FunctionDef) and m.name in ('_require_static_mode_entry', '_confirm_mode_feedback', '_wait_static_mode_entry')]


class BackendModeTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        Manager.active = False; Manager.events = []
        env = {'Any': object, 'time': self.clock, 'math': math,
               'Int': types.SimpleNamespace(Request=lambda: types.SimpleNamespace()),
               '_int_response_success': lambda r: r.success,
               '_response_error_code': lambda r: 0,
               '_int_response_error': lambda r: {'success': False, 'message': 'failure'}}
        exec(compile(ast.Module(body=helpers+[method], type_ignores=[]), '<mode method>', 'exec'), env)
        self.node = types.SimpleNamespace(_mode_change_lock=threading.Lock(), mode_client=None,
                                         _current_mode=0, _lock=threading.Lock(),
                                         _joint_feedback_time=self.clock.t,
                                         _joint_feedback=([0.0]*14,[0.0]*14))
        for helper in helpers:
            setattr(self.node, helper.name, types.MethodType(env[helper.name], self.node))
        self.calls = []; self.response_success = True; self.fault = False; self.stuck = False
        self.node.snapshot = self.snapshot
        self.node._call = self.call
        self.run_mode = types.MethodType(env['set_mode'], self.node)

    def snapshot(self):
        state = [0, 0] if not self.calls or self.stuck else [{0: 0, 1: 1, 3: 2}[self.calls[-1][0]]] * 2
        return dict(arm_state=state, arm_state_age_sec=0, control_ready=True,
                    control_error=self.fault, control_error_message='drive fault')

    def call(self, _, request, __, timeout_sec):
        self.calls.append((request.data, timeout_sec))
        return types.SimpleNamespace(success=self.response_success)

    def test_mode_rpc_has_bounded_transition_deadline(self):
        result = self.run_mode(3)
        self.assertTrue(result['success']); self.assertEqual(self.calls, [(1, 12.0), (3, 12.0)])
        self.assertEqual(self.node._current_mode, 0)

    def test_tool_restored_only_after_feedback_success(self):
        Manager.active = True
        self.assertTrue(self.run_mode(3)['success'])
        self.assertEqual(Manager.events, ['stop', 'start'])

    def test_fault_never_cleared_or_enabled_implicitly(self):
        self.fault = True
        with self.assertRaises(RuntimeError): self.run_mode(3)
        self.assertEqual(self.calls, []); self.assertEqual(Manager.events, [])

    def test_failed_mode_keeps_tool_paused(self):
        Manager.active = True; self.response_success = False
        self.assertFalse(self.run_mode(3)['success'])
        self.assertEqual(Manager.events, ['stop'])

    def test_success_reply_without_controller_state_is_rejected(self):
        self.stuck = True
        with self.assertRaises(TimeoutError): self.run_mode(3)
        self.assertFalse(self.node._mode_change_lock.locked())

    def test_simultaneous_mode_changes_rejected(self):
        self.node._mode_change_lock.acquire()
        with self.assertRaises(RuntimeError): self.run_mode(3)
        self.assertEqual(self.calls, [])

    def test_invalid_mode_never_sent(self):
        with self.assertRaises(RuntimeError): self.run_mode(2)
        self.assertEqual(self.calls, [])

    def test_idle_and_position_remain_explicit_modes(self):
        self.assertTrue(self.run_mode(0)['success'])
        self.assertTrue(self.run_mode(1)['success'])
        self.assertEqual([v[0] for v in self.calls], [0, 1])

    def test_moving_wrist_prevents_enable(self):
        self.node._joint_feedback[1][12] = math.radians(10)
        with self.assertRaises(RuntimeError): self.run_mode(3)
        self.assertEqual(self.calls, [])

    def test_stale_joint_feedback_prevents_enable(self):
        self.node._joint_feedback_time = self.clock.t - 2
        with self.assertRaises(RuntimeError): self.run_mode(3)
        self.assertEqual(self.calls, [])

    def test_wrist_limit_guard(self):
        self.node._joint_feedback[0][12] = math.radians(60)
        with self.assertRaises(RuntimeError): self.run_mode(3)
        self.assertEqual(self.calls, [])

    def test_settle_wait_does_not_repeat_mode_requests(self):
        self.node._joint_feedback[1][12] = math.radians(5)
        original_sleep = self.clock.sleep
        def settle(value):
            original_sleep(value)
            if self.clock.t >= 100.1:
                self.node._joint_feedback[1][12] = 0
                self.node._joint_feedback_time = self.clock.t
        self.clock.sleep = settle
        self.node._wait_static_mode_entry()
        self.assertEqual(self.calls, [])

    def test_temporary_normal_state_mismatch_waits_for_confirmation(self):
        rows = [dict(arm_state=[0,1], arm_state_age_sec=0, control_error=True),
                dict(arm_state=[1,1], arm_state_age_sec=0, control_error=False)]
        self.node.snapshot = lambda: rows.pop(0) if len(rows)>1 else rows[0]
        self.node._confirm_mode_feedback(1, self.clock.t)

    def test_real_drive_fault_is_terminal(self):
        self.node.snapshot = lambda: dict(arm_state=[2,100], arm_state_age_sec=0,
                                         control_error=True, control_error_message='right drive fault')
        with self.assertRaisesRegex(RuntimeError, 'right drive fault'):
            self.node._confirm_mode_feedback(2, self.clock.t)


if __name__ == '__main__': unittest.main()
