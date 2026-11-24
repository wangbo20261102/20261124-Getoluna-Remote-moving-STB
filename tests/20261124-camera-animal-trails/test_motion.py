import unittest
from animation_control import config,track

class MotionTests(unittest.TestCase):
    def test_preserves_each_previous_forward_speed(self):
        for b in config()['batteries'].values():
            expected=1920*b['travel_fraction']/(b['cycle_seconds']/2)
            self.assertAlmostEqual(track(b,6)-track(b,5),expected)

    def test_vanishes_then_reappears_on_left_without_reversing(self):
        for b in config()['batteries'].values():
            duration=b['cycle_seconds']/2
            self.assertGreater(track(b,duration-.1),track(b,1))
            self.assertIsNone(track(b,duration+.2))
            self.assertAlmostEqual(track(b,duration+b['restart_pause_seconds']),1920*b['x_fraction'])
            self.assertGreater(track(b,duration+b['restart_pause_seconds']+.1),1920*b['x_fraction'])

    def test_speeds_remain_different(self):
        b=config()['batteries']
        self.assertGreater(track(b['1'],6)-track(b['1'],5),track(b['2'],6)-track(b['2'],5))

if __name__=='__main__':unittest.main()
