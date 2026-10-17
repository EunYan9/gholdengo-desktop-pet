import json,tempfile,unittest
from datetime import datetime
from pathlib import Path
from daily_budget import DailyBudget,BEIJING,day_start,DAY

def at(day,hour=2,minute=0):return datetime(2026,10,day,hour,minute,tzinfo=BEIJING).timestamp()
def snapshot(remaining,when,reset=None):
    return {'retrieved_at':when,'windows':[{'remaining':remaining,'minutes':10080,'resets_at':reset or at(24,6)}]}

class DailyTests(unittest.TestCase):
    def test_backfill_repairs_installed_midday_zero(self):
        now=[at(17,14)];b=DailyBudget(clock=lambda:now[0])
        b.observe(snapshot(83,now[0]));self.assertEqual(b.current['used'],0)
        history=[{'at':at(17,6,1),'remaining':100,'reset':at(24,6)},
                 {'at':at(17,10),'remaining':91,'reset':at(24,6)+2}]
        now[0]+=60;self.assertEqual(b.observe(snapshot(83,now[0]),history),[100])
        self.assertEqual(b.view()['used'],17);self.assertAlmostEqual(b.view()['limit'],100/7)
        self.assertEqual(b.view()['coverage'],'lower_bound')
        self.assertTrue(b.view()['gap_before_reset'])

    def test_02_boundary_before_snapshot_and_cross_reset(self):
        now=[at(23,10)];b=DailyBudget(clock=lambda:now[0])
        history=[{'at':at(23,1,59),'remaining':30,'reset':at(24,2)}]
        b.observe(snapshot(25,now[0],at(24,2)),history)
        self.assertEqual((b.current['day'],b.current['baseline'],b.view()['used']),(at(23),30,5))
        now[0]=at(23,12)
        # A reset inside the same 02:00 day must not erase confirmed consumption.
        b.observe(snapshot(95,now[0],at(30,11)),[{'at':at(23,11,1),'remaining':100,'reset':at(30,11)}])
        self.assertEqual(b.view()['used'],10)

    def test_beijing_boundary_and_weekly_schedule(self):
        self.assertEqual(day_start(at(18,1,59)),at(17))
        self.assertEqual(day_start(at(18)),at(18))
        now=[at(17,14)];b=DailyBudget(clock=lambda:now[0])
        b.observe(snapshot(84,now[0]));self.assertEqual((b.current['days'],b.current['limit']),(7,12))
        now[0]=at(17,16);b.observe(snapshot(81,now[0]));self.assertEqual((b.view()['used'],b.view()['left']),(3,9))
        self.assertTrue(b.current['partial'])
        now[0]=at(18);self.assertEqual(b.view()['status'],'stale')
        b.observe(snapshot(78,now[0]));self.assertEqual((b.current['days'],b.current['limit'],b.current['used']),(6,13,0))
        for day,days in [(19,5),(20,4),(21,3),(22,2),(23,1),(24,1)]:
            now[0]=at(day);b.observe(snapshot(60,now[0]));self.assertEqual(b.current['days'],days)

    def test_limits_fixed_alerts_and_restart(self):
        now=[at(17,7)]
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            path=Path(d)/'budget.json';b=DailyBudget(path,lambda:now[0])
            b.observe(snapshot(70,now[0]));self.assertEqual(b.current['limit'],10)
            now[0]+=60;self.assertEqual(b.observe(snapshot(62,now[0])),[80])
            now[0]+=60;self.assertEqual(b.observe(snapshot(62,now[0])),[])
            b=DailyBudget(path,lambda:now[0]);now[0]+=60
            self.assertEqual(b.observe(snapshot(60,now[0])),[100])
            now[0]+=60;self.assertEqual(b.observe(snapshot(59,now[0])),[])
            self.assertEqual(b.view()['over'],1)
            # A correction cannot erase usage or repeatedly notify.
            now[0]+=60;b.observe(snapshot(65,now[0]));self.assertEqual(b.view()['used'],11)

    def test_reset_gaps_missing_and_out_of_order(self):
        now=[at(17,13)];b=DailyBudget(clock=lambda:now[0]);b.observe(snapshot(84,now[0]))
        now[0]+=60;self.assertEqual(b.observe(snapshot(60,now[0])),[100])
        old=b.current.copy();b.observe(snapshot(99,at(17,12)));self.assertEqual(b.current,old)
        b.observe({'retrieved_at':now[0]+1,'windows':[]});self.assertEqual(b.current,old)
        now[0]=at(24,6);self.assertEqual(b.view()['status'],'stale')
        b.observe(snapshot(100,now[0],at(31,6)));self.assertEqual((b.current['days'],b.current['used']),(7,0))
        self.assertAlmostEqual(b.current['limit'],100/7)

    def test_corrupt_state_and_zero_allowance(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            path=Path(d)/'budget.json';path.write_text('{"records":["bad",{}]}')
            b=DailyBudget(path,lambda:at(17,7));self.assertEqual(b.view()['status'],'missing')
            self.assertEqual(b.observe(snapshot(0,at(17,7))),[])
            self.assertEqual(b.view()['left'],0)

if __name__=='__main__':unittest.main()
