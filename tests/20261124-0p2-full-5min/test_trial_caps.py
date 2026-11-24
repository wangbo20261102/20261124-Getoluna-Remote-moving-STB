import io,json,math,unittest
from types import SimpleNamespace
from unittest.mock import patch
from pico_chassis_bridge import read_limits,DriveGate,STOP
class TrialCaps(unittest.TestCase):
    def read(self,linear,angular,avoid=True):
        data={'ErrorCode':0,'Content':{'robot.manual_move.enable_avoid':avoid,'max_speed.linear':linear,'max_speed.angular':angular}}
        with patch('pico_chassis_bridge.urllib.request.build_opener') as fake:
            fake.return_value.open.return_value=io.StringIO(json.dumps(data))
            return read_limits()
    def test_requested_caps(self):
        self.assertEqual(self.read(.2,.2),(.2,.2))
        self.assertEqual(self.read(1.,1.),(.2,.2))
    def test_lower_vendor_caps_respected(self):
        self.assertEqual(self.read(.1,.15),(.1,.15))
    def test_avoidance_still_required(self):
        with self.assertRaises(ValueError):self.read(.2,.2,False)
    def test_diagonal_and_turn_at_new_caps(self):
        neutral=SimpleNamespace(axes=[0.,0.],buttons=[])
        left=SimpleNamespace(axes=[1.,1.],buttons=[])
        right=SimpleNamespace(axes=[1.,0.],buttons=[])
        gate=DriveGate(2,-1,-1)
        self.assertEqual(gate.command(neutral,neutral,True,.2,.2),STOP)
        x,y,w=gate.command(left,right,True,.2,.2)
        self.assertAlmostEqual(math.hypot(x,y),.2)
        self.assertEqual(w,-.2)
if __name__=='__main__':unittest.main()
