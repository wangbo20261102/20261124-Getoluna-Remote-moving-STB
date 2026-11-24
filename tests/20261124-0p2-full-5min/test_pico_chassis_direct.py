"""Offline checks for the requested direct-stick control; no ROS or sockets."""
import math
import unittest
from types import SimpleNamespace as Joy
from pico_chassis_bridge import DriveGate, STOP, usable_state

def joy(x=0., y=0., buttons=()):
    return Joy(axes=[x, y], buttons=list(buttons))

class DirectStickTests(unittest.TestCase):
    def setUp(self):
        self.gate = DriveGate(2, -1, -1)

    def command(self, left=None, right=None, permitted=True):
        return self.gate.command(left or joy(), right or joy(), permitted, .08, .10)

    def center(self):
        self.assertEqual(self.command(), STOP)

    def test_initial_deflection_cannot_start_until_centered(self):
        self.assertEqual(self.command(joy(y=1)), STOP)
        self.center()
        self.assertEqual(self.command(joy(y=1)), (.08, 0., 0.))

    def test_no_button_data_or_press_required(self):
        self.center()
        self.assertEqual(self.command(joy(y=-1)), (-.08, 0., 0.))
        self.assertEqual(self.command(joy(y=1, buttons=[0])), (.08, 0., 0.))
        self.assertEqual(self.command(joy(y=1, buttons=[1])), (.08, 0., 0.))

    def test_lateral_and_turn_mapping(self):
        self.center()
        self.assertEqual(self.command(joy(x=1)), (0., -.08, 0.))
        self.assertEqual(self.command(joy(x=-1)), (0., .08, 0.))
        self.assertEqual(self.command(right=joy(x=1)), (0., 0., -.10))
        self.assertEqual(self.command(right=joy(x=-1)), (0., 0., .10))

    def test_centering_stops_without_disarming_next_motion(self):
        self.center()
        self.command(joy(y=1))
        self.assertEqual(self.command(), STOP)
        self.assertEqual(self.command(joy(y=-1)), (-.08, 0., 0.))

    def test_permission_loss_requires_new_center(self):
        self.center()
        self.command(joy(y=1))
        self.assertEqual(self.command(joy(y=1), permitted=False), STOP)
        self.assertEqual(self.command(joy(y=1)), STOP)
        self.center()
        self.assertEqual(self.command(joy(y=1)), (.08, 0., 0.))

    def test_diagonal_translation_remains_within_cap(self):
        self.center()
        x,y,w = self.command(joy(x=1, y=1), joy(x=-1))
        self.assertAlmostEqual(math.hypot(x,y), .08)
        self.assertEqual(w, .10)

    def test_invalid_or_missing_input_stops_and_resets(self):
        self.center()
        self.assertEqual(self.command(joy(y=float('nan'))), STOP)
        self.assertEqual(self.command(joy(y=1)), STOP)
        self.center()
        self.assertEqual(self.gate.command(None, joy(), True, .08, .10), STOP)

    def test_optional_legacy_press_mode(self):
        gate = DriveGate(2,-1,-1,hold_button=0)
        self.assertEqual(gate.command(joy(buttons=[0]),joy(),True,.08,.10), STOP)
        self.assertEqual(gate.command(joy(y=1,buttons=[0]),joy(),True,.08,.10), STOP)
        gate.command(joy(buttons=[0]),joy(),True,.08,.10)
        self.assertEqual(gate.command(joy(y=1,buttons=[1]),joy(),True,.08,.10), (.08,0.,0.))

    def test_scram_and_auto_modes_are_not_permitted(self):
        state = dict(id=1,isNormal=True,workStatus=14,isScram=False,isSoftAuto=False,
                     isPause=False,isSuspend=False,isParkingMode=False,isReseting=False,isFallback=False)
        self.assertTrue(usable_state(state))
        self.assertFalse(usable_state({**state,'isScram':True}))
        self.assertFalse(usable_state({**state,'isSoftAuto':True}))

if __name__ == '__main__':
    unittest.main()
