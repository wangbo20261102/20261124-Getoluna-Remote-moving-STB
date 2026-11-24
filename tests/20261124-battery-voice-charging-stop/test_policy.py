import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import battery_voice as voice
from battery_voice import low_batteries, Schedule, AlarmPolicy, charging_detected

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

    def test_charging_overrides_even_below_threshold(self):
        d=data(20,20)
        p=AlarmPolicy(latched=True)
        self.assertTrue(charging_detected(d,0))
        p.observe(low_batteries(d,0),charging_detected(d,0))
        self.assertFalse(p.latched)
        self.assertFalse(p.due(100))

    def test_repeat_until_charging_despite_soc_rebound_or_data_loss(self):
        p=AlarmPolicy()
        p.observe([{'id':1,'energy':29}],False)
        self.assertTrue(p.due(100));p.started(100)
        p.observe([],False)  # SOC rebounded; no charging detected.
        self.assertFalse(p.due(109.9));self.assertTrue(p.due(110))
        p.observe([],None)  # Missing data cannot invent a charging event.
        self.assertTrue(p.due(120))
        p.observe([],True)
        self.assertFalse(p.due(130))

    def test_stale_charging_does_not_clear_latch(self):
        p=AlarmPolicy(True)
        self.assertIsNone(charging_detected(data(20,20),6))
        p.observe([],charging_detected(data(20,20),6))
        self.assertTrue(p.latched)

    def test_rearm_if_charging_stops_while_still_low(self):
        p=AlarmPolicy()
        p.observe([{'id':1,'energy':20}],True)
        self.assertFalse(p.latched)
        p.observe([{'id':1,'energy':20}],False)
        self.assertTrue(p.due(100))

    def test_one_connected_battery_charging_is_enough(self):
        d=data(20,20);d['batteries'][0]['is_charging']=False
        self.assertTrue(charging_detected(d,0))

    def test_latch_survives_service_restart_but_not_new_boot(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(voice,'RUNTIME',Path(folder)):
            p=AlarmPolicy(True);p.started(10)
            with patch.object(voice,'boot_id',return_value='same-boot'):
                voice.save_policy(p)
                restored=voice.load_policy()
                self.assertTrue(restored.latched)
                self.assertEqual(restored.last_started,10)
            with patch.object(voice,'boot_id',return_value='new-boot'):
                self.assertFalse(voice.load_policy().latched)

    def test_charging_cancels_inflight_playback_without_real_audio(self):
        class Player:
            returncode=None
            terminated=False
            def poll(self):return self.returncode
            def terminate(self):self.terminated=True;self.returncode=-15
            def communicate(self,timeout=None):return None,b''
        player=Player()
        turns=[]
        def tick(seconds):
            turns.append(seconds)
            if len(turns)==2:voice.stopping=True
        with tempfile.TemporaryDirectory() as folder, patch.object(voice,'RUNTIME',Path(folder)), \
             patch.object(voice,'read_feedback',side_effect=[([{'id':1,'energy':20}],False,True),
                                                            ([{'id':1,'energy':20}],True,True)]), \
             patch.object(voice,'play',return_value=player) as play, \
             patch.object(voice.time,'sleep',side_effect=tick):
            voice.stopping=False
            try:voice.live()
            finally:voice.stopping=False
            self.assertTrue(player.terminated)
            self.assertEqual(play.call_count,1)
            state=json.loads((Path(folder)/'status.json').read_text())
            self.assertFalse(state['playing'])
            self.assertFalse(state['alarm_latched'])
            self.assertTrue(state['charging_detected'])

if __name__=='__main__':unittest.main()
