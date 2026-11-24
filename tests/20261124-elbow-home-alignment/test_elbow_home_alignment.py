import unittest,tempfile,pathlib
import numpy as np
from elbow_home_alignment import ElbowHomeAlignment,HOME,rotation

Q={'w':1.,'x':0.,'y':0.,'z':0.}
def pose():return {'torso':np.array([.1,.2,1.]),'left_elbow':np.array([.22,.57,1.]),'right_elbow':np.array([.2,-.16,.98]),'head':np.array([.1,.2,1.4])}
def calibrate(a,p=None):
    p=pose() if p is None else p;a.request()
    for i in range(81):out=a.observe(p,Q,True,i*.01)
    return out
class Tests(unittest.TestCase):
    def test_neutral_equals_home(self):
        a=ElbowHomeAlignment(True);p=pose();out=calibrate(a,p)
        self.assertTrue(a.ready(.8))
        for k in HOME:np.testing.assert_allclose(out[k]-out['torso'],HOME[k],atol=1e-10)
        np.testing.assert_array_equal(out['head'],p['head'])
    def test_one_to_one_motion_and_torso_rotation(self):
        a=ElbowHomeAlignment(True);p=pose();calibrate(a,p)
        moved={k:v.copy() for k,v in p.items()};moved['left_elbow']+=np.array([.02,0,.01])
        out=a.observe(moved,Q,False,.9)
        np.testing.assert_allclose(out['left_elbow']-out['torso'],HOME['left_elbow']+[.02,0,.01])
        q={'w':np.sqrt(.5),'x':0.,'y':0.,'z':np.sqrt(.5)};R=rotation(q)
        origin=np.array([1.,2.,3.]);turned={k:origin+R@(v-p['torso']) for k,v in p.items()}
        out=a.observe(turned,q,False,1.)
        for k in HOME:np.testing.assert_allclose(R.T@(out[k]-origin),HOME[k],atol=1e-10)
    def test_grips_held_never_calibrate(self):
        a=ElbowHomeAlignment(True);a.request()
        for i in range(100):a.observe(pose(),Q,False,i*.01)
        self.assertFalse(a.ready(1.))
    def test_unsteady_pose_never_calibrates(self):
        a=ElbowHomeAlignment(True);a.request()
        for i in range(100):
            p=pose();p['left_elbow'][0]+=.1*(i%2);a.observe(p,Q,True,i*.01)
        self.assertFalse(a.ready(1.))
    def test_tracking_loss_disables_enable(self):
        a=ElbowHomeAlignment(True);calibrate(a)
        a.observe({},Q,True,1.)
        self.assertFalse(a.ready(1.2))
    def test_load_saved_calibration_requires_fresh_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/'state.json';a=ElbowHomeAlignment(True,path);calibrate(a)
            b=ElbowHomeAlignment(True,path);self.assertFalse(b.ready(.8))
            out=b.observe(pose(),Q,False,1.)
            self.assertTrue(b.ready(1.))
            for k in HOME:np.testing.assert_allclose(out[k]-out['torso'],HOME[k])
    def test_disabled_passthrough(self):
        a=ElbowHomeAlignment(False);p=pose()
        self.assertIs(a.observe(p,Q,False,0.),p);self.assertTrue(a.ready(0.))
if __name__=='__main__':unittest.main()
