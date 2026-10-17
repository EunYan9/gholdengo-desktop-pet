import sqlite3,tempfile,unittest
from contextlib import closing
from pathlib import Path
from codex_activity import read_activity,writer_is_live

class ActivityTests(unittest.TestCase):
    def test_metadata(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            home=Path(d);db=home/'thread_history_1.sqlite'
            self.assertEqual(read_activity(home)['state'],'unknown')
            with closing(sqlite3.connect(db)) as c:
                c.execute('CREATE TABLE thread_turns(thread_id TEXT,status TEXT,completed_at INTEGER,rollout_ordinal INTEGER)')
                c.execute("INSERT INTO thread_turns VALUES ('abc','inProgress',NULL,1)")
                c.commit()
            snapshot=read_activity(home,lambda p:True)
            self.assertEqual((snapshot['state'],snapshot['count'],snapshot['active_ids']),('working',1,['abc']))
            self.assertEqual(read_activity(home,lambda p:False)['state'],'idle')
            self.assertEqual(read_activity(home,lambda p:None)['state'],'unknown')
            with closing(sqlite3.connect(db)) as c:
                c.execute("INSERT INTO thread_turns VALUES ('abc','completed',12,2)")
                c.execute("INSERT INTO thread_turns VALUES ('def','interrupted',NULL,1)")
                c.commit()
            self.assertEqual(read_activity(home,lambda p:True)['state'],'idle')
            snapshot=read_activity(home,lambda p:True,watching=['abc','def','missing'])
            self.assertEqual(snapshot['outcomes'],{'abc':'completed','def':'interrupted'})
            with closing(sqlite3.connect(db)) as c:
                c.execute("INSERT INTO thread_turns VALUES ('bad/path','inProgress',NULL,1)")
                c.commit()
            self.assertEqual(read_activity(home,lambda p:True)['state'],'unknown')
            lock=home/'free.lock';lock.touch()
            self.assertFalse(writer_is_live(lock))

if __name__=='__main__':unittest.main()
