import unittest
from battery_voice import low_batteries, Schedule

def data(a=40,b=40):
    return {'fresh':True,'seconds_since_feedback':.1,
            'batteries':[{'id':n,'energy':v,'is_connected':True,'is_in_place':True,
                          'is_charging':True} for n,v in [(1,a),(2,b)]]}

class Tests(unittest.TestCase):
    def test_threshold_boundary_and_either_battery(self):
        self.assertFalse(low_batteries(data(30,30),0))
        self.assertEqual(low_batteries(data(29,80),0),[{'id':1,'energy':29}])
        self.assertEqual(low_batteries(data(80,29),0),[{'id':2,'energy':29}])

    def test_stale_or_disconnected_never_speaks(self):
        self.assertFalse(low_batteries(data(29,29),6))
        d=data(29,80);d['batteries'][0]['is_connected']=False
        self.assertFalse(low_batteries(d,0))

    def test_no_duplicate_for_two_low_batteries(self):
        schedule=Schedule();low=low_batteries(data(29,29),0)
        self.assertTrue(schedule.due(low,100));schedule.started(100)
        self.assertFalse(schedule.due(low,109.999))
        self.assertTrue(schedule.due(low,110))
        self.assertFalse(schedule.due([],110))

    def test_invalid_percent_never_speaks(self):
        for value in [-1,101,float('nan'),None,True,'29']:
            self.assertFalse(low_batteries(data(value,80),0))

if __name__=='__main__':unittest.main()
