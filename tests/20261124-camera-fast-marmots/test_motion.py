import unittest
from animation_control import config,track

class MotionTests(unittest.TestCase):
    def test_preserves_each_previous_forward_speed(self):
        for b in config()['batteries'].values():
            if b['motion']!='forward_wrap':continue
            expected=1920*b['travel_fraction']/(b['cycle_seconds']/2)
            self.assertAlmostEqual(track(b,6)-track(b,5),expected)

    def test_vanishes_then_reappears_on_left_without_reversing(self):
        for b in config()['batteries'].values():
            if b['motion']!='forward_wrap':continue
            duration=b['cycle_seconds']/2
            self.assertGreater(track(b,duration-.1),track(b,1))
            self.assertIsNone(track(b,duration+.2))
            self.assertAlmostEqual(track(b,duration+b['restart_pause_seconds']),1920*b['x_fraction'])
            self.assertGreater(track(b,duration+b['restart_pause_seconds']+.1),1920*b['x_fraction'])

    def test_marmots_move_on_the_same_track_with_independent_speed(self):
        b=config()['batteries']
        self.assertEqual(b['2']['kind'],'marmots')
        self.assertEqual(track(b['1'],0),track(b['2'],0))
        self.assertGreater(track(b['2'],10),track(b['2'],0))
        self.assertEqual(b['1']['trail_dots'],b['2']['trail_dots'])
        self.assertGreater(track(b['1'],10),track(b['2'],10))

    def test_trail_is_dense_with_small_visible_gaps(self):
        for b in config()['batteries'].values():
            gap=1920*b['travel_fraction']/b['trail_dots']-b['trail_dot_size']
            self.assertTrue(0<gap<2)

if __name__=='__main__':unittest.main()
