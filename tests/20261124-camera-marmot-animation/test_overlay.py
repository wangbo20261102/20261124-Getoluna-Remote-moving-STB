import unittest
from battery_overlay import display_state

def data(a=50, b=50, charging=False):
    return {'fresh': True, 'seconds_since_feedback': .1,
            'batteries': [{'id': n, 'energy': e, 'is_connected': True, 'is_in_place': True,
                           'is_charging': charging, 'error_code': 0} for n,e in [(1,a),(2,b)]]}

class OverlayTests(unittest.TestCase):
    def test_29_red_and_30_normal(self):
        s = display_state(data(29,30))
        self.assertEqual([r['color'] for r in s['rows']], ['red','normal'])
        self.assertIn('请优先充电', s['texts']['warning'])

    def test_either_battery_triggers_even_charging(self):
        s = display_state(data(60,29,True))
        self.assertEqual(s['rows'][1]['color'], 'red')
        self.assertIn('充电中', s['rows'][1]['text'])
        self.assertNotEqual(s['texts']['warning'], ' ')

    def test_stale_hides_old_percent(self):
        for state in [display_state(data(29,30), False), display_state({**data(), 'fresh':False})]:
            self.assertTrue(all(r['energy'] is None for r in state['rows']))
            self.assertEqual(state['texts']['warning'], ' ')
            self.assertIn('不可用',state['texts']['stale'])

    def test_missing_or_disconnected_battery_unknown(self):
        s=data(); s['batteries']=s['batteries'][:1]
        self.assertEqual(display_state(s)['rows'][1]['color'],'unknown')
        s=data(); s['batteries'][0]['is_connected']=False
        self.assertEqual(display_state(s)['rows'][0]['color'],'unknown')

    def test_invalid_values_unknown(self):
        for value in [None, -1, 101, float('nan'), True, '29']:
            self.assertFalse(display_state(data(value,50))['rows'][0]['valid'])

if __name__=='__main__': unittest.main()
