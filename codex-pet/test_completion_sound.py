import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from completion_sound import CompletionTracker, CompletionSound
from codex_activity import read_activity


class CompletionTests(unittest.TestCase):
    def test_exact_turns_parallel_restart_and_unknown(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            home = Path(folder)
            with closing(sqlite3.connect(home/'thread_history_1.sqlite')) as con:
                con.execute('CREATE TABLE thread_turns(thread_id TEXT,turn_id TEXT,status TEXT,completed_at INTEGER,rollout_ordinal INTEGER)')
                con.executemany('INSERT INTO thread_turns VALUES (?,?,?,?,?)', [
                    ('abc','a1','inProgress',None,1), ('def','d1','inProgress',None,1),
                    ('eee','old','completed',10,1)])
                con.commit()
            tracker = CompletionTracker()
            def poll():return read_activity(home, lambda p:True, watched_turns=tracker.pending)
            self.assertEqual(tracker.observe(poll()), [])
            self.assertEqual(tracker.pending, {'a1':'abc','d1':'def'})
            with closing(sqlite3.connect(home/'thread_history_1.sqlite')) as con:
                con.execute("UPDATE thread_turns SET status='completed',completed_at=20 WHERE turn_id='a1'")
                # A new turn may already exist when the previous turn completes.
                con.execute("INSERT INTO thread_turns VALUES ('abc','a2','inProgress',NULL,2)")
                con.commit()
            snapshot = poll()
            self.assertEqual(snapshot['state'], 'working')
            self.assertEqual(tracker.observe(snapshot), ['a1'])
            self.assertEqual(tracker.observe(snapshot), [])
            tracker.observe({'state':'unknown'})
            self.assertIn('d1', tracker.pending)
            with closing(sqlite3.connect(home/'thread_history_1.sqlite')) as con:
                con.execute("UPDATE thread_turns SET status='interrupted' WHERE turn_id='d1'")
                con.execute("UPDATE thread_turns SET status='failed' WHERE turn_id='a2'")
                con.commit()
            self.assertEqual(tracker.observe(poll()), [])
            self.assertFalse(tracker.pending)
            self.assertEqual(CompletionTracker().observe(poll()), [])

    def test_muted_by_default_and_coalesced(self):
        class Clock:
            value=100.
            def __call__(self):return self.value
        class Effect:
            count=0
            def play(self):self.count+=1
            def stop(self):pass
        clock=Clock();sound=CompletionSound(None,Path('unused'),clock);sound.effect=Effect()
        self.assertFalse(sound.enabled)
        self.assertFalse(sound.play()); self.assertEqual(sound.effect.count,0)
        self.assertTrue(sound.play(preview=True))
        sound.enabled=True
        clock.value+=.5;self.assertFalse(sound.play())
        clock.value+=1.;self.assertTrue(sound.play())
        self.assertEqual(sound.effect.count,2)


if __name__ == '__main__':unittest.main()
