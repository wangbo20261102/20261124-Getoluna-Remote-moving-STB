"""Guard tests with all actuation APIs mocked. No SDK or hardware commands."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import robot_agent as m

class Guards(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.run=Path(self.temp.name)
        self.patches=[patch.object(m,'RUN',self.run),patch.object(m,'CANCEL',self.run/'cancel')]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        self.agent=m.Agent.__new__(m.Agent)
        self.agent.lock=__import__('threading').Lock();self.agent.latest={}
        self.agent.services=lambda:{}
        self.agent.service_time=0
    def test_support_requires_explicit_true(self):
        for value in [None,False,1,'true']:
            with self.assertRaises(RuntimeError):self.agent.support({'supported':value})
        self.agent.support({'supported':True})
    def test_no_legacy_reset_command(self):
        with patch.object(m,'api') as api:
            with self.assertRaises(RuntimeError):self.agent.dispatch('reset',{})
            api.assert_not_called()
    def test_home_needs_separate_confirmation(self):
        self.agent.robot_fresh=lambda:{'control_ready':True}
        with patch.object(m,'api') as api:
            with self.assertRaises(RuntimeError):self.agent.action('home',{'supported':True})
            api.assert_not_called()
    def test_home_refuses_without_planning_service(self):
        self.agent.robot_fresh=lambda:{'control_ready':True}
        with patch.object(m,'api') as api:
            with self.assertRaises(RuntimeError):self.agent.action('home',{'supported':True,'home_confirmed':True})
            api.assert_not_called()
    def test_failed_preflight_starts_nothing(self):
        self.agent.preflight=lambda:{'passed':False,'checks':[{'level':'error','text':'SDK mismatch'}]}
        with patch.object(m,'api') as api:
            with self.assertRaises(RuntimeError):self.agent.action('prepare',{'supported':True})
            api.assert_not_called()
    def test_prepare_never_calls_home_or_teleop(self):
        self.agent.preflight=lambda:{'passed':True,'checks':[]}
        self.agent.wait_robot=lambda predicate,seconds=10:{}
        self.agent.robot_fresh=lambda:{'arm_state':[0,0,0,0,0,0]}
        self.agent.require_arm_feedback=lambda:None
        calls=[]
        def fake_api(path,body=None):calls.append((path,body));return {}
        with patch.object(m,'api',side_effect=fake_api):self.agent.action('prepare',{'supported':True})
        self.assertEqual([b['mode'] for p,b in calls if p=='/robot/mode'],[1,3])
        self.assertFalse(any('home' in p or 'reset' in p or '/teleop/' in p for p,b in calls))
    def test_pause_preserves_robot_and_display(self):
        with patch.object(m,'api',return_value={}) as api:self.agent.action('pause',{})
        paths=[c.args[0] for c in api.call_args_list]
        self.assertIn('/modules/teleop/stop',paths);self.assertIn('/modules/tool/stop',paths)
        self.assertFalse(any('/robot/stop' in p or '/robot/mode' in p or '/camera/stop' in p for p in paths))
        self.assertTrue((self.run/'cancel').exists())
    def test_teleop_rejects_non_impedance(self):
        self.agent.robot_fresh=lambda:{'control_ready':True,'arm_state':[0,0,0,0,0,0]}
        with patch.object(m,'api') as api:
            with self.assertRaises(RuntimeError):self.agent.action('teleop',{'supported':True})
            api.assert_not_called()
    def test_unknown_mode_cannot_be_sent(self):
        self.agent.robot_fresh=lambda:{'control_ready':True}
        with patch.object(m,'api') as api:
            with self.assertRaises(RuntimeError):self.agent.action('mode',{'supported':True,'mode':99})
            api.assert_not_called()
    def test_stop_robot_refuses_active_teleop(self):
        self.agent.services=lambda:{'apex-teleop.service':{'ActiveState':'active'}}
        with patch.object(m,'api') as api:
            with self.assertRaises(RuntimeError):self.agent.action('robot_stop',{'supported':True})
            api.assert_not_called()
    def test_low_battery_warns_without_automatic_disable(self):
        for percent in [29,30]:
            self.agent.status=lambda p=percent:{'battery':{'fresh':True,'batteries':[{'id':1,'energy':p,'is_connected':True,'is_in_place':True},{'id':2,'energy':85,'is_connected':True,'is_in_place':True}]},'sdk_approved':True,'robot':{'control_error':False},'topics':{}}
            with patch.object(m,'api') as api:
                result=self.agent.preflight();api.assert_not_called()
            self.assertTrue(result['passed'])
            self.assertEqual(any('低于 30%' in c['text'] and '历史' in c['text'] for c in result['checks']),percent<30)
    def test_invalid_battery_does_not_pass(self):
        self.agent.status=lambda:{'battery':{'fresh':True,'batteries':[{'energy':85,'is_connected':False},{'energy':85,'is_connected':True,'is_in_place':True}]},'sdk_approved':True,'robot':{},'topics':{}}
        self.assertFalse(self.agent.preflight()['passed'])
    def test_j6_out_of_range_is_rejected(self):
        positions=[0.0]*14;positions[5]=__import__('math').radians(61)
        self.agent.latest={'/info/joint_feedback':{'age_base':__import__('time').monotonic(),'data':{'arm_positions':positions}}}
        with self.assertRaisesRegex(RuntimeError,'J6'):self.agent.require_arm_feedback()
    def test_nonfinite_joint_feedback_is_rejected(self):
        positions=[0.0]*14;positions[0]=float('nan')
        self.agent.latest={'/info/joint_feedback':{'age_base':__import__('time').monotonic(),'data':{'arm_positions':positions}}}
        with self.assertRaises(RuntimeError):self.agent.require_arm_feedback()

if __name__=='__main__':unittest.main()
