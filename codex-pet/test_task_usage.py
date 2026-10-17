from pathlib import Path
from contextlib import closing
import json,os,sqlite3,tempfile,unittest
from task_usage import TaskUsageReader,last_token_event

def event(total):return json.dumps({'type':'event_msg','timestamp':'2026-10-17T06:00:00Z','payload':{'type':'token_count','info':{'total_token_usage':{'total_tokens':total,'input_tokens':total-20,'cached_input_tokens':50,'output_tokens':20}}}}).encode()+b'\n'

class TaskTests(unittest.TestCase):
    def test_per_turn_cumulative_and_live_updates(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            home=Path(d);(home/'sessions').mkdir();path=home/'sessions/log.jsonl'
            prefix=event(100)+b'{"type":"response_item","payload":{"text":"private"}}\n'
            path.write_bytes(prefix+event(160)+b'{"type":"event_msg","payload":')
            with closing(sqlite3.connect(home/'state_5.sqlite')) as c:
                c.execute('CREATE TABLE threads(id TEXT,name TEXT,title TEXT,tokens_used INTEGER,rollout_path TEXT)')
                c.execute('INSERT INTO threads VALUES (?,?,?,?,?)',('abc','可见名称','first prompt',150,str(path)));c.commit()
            with closing(sqlite3.connect(home/'thread_history_1.sqlite')) as c:
                c.execute('CREATE TABLE thread_turns(thread_id TEXT,turn_id TEXT,status TEXT,started_at INTEGER,rollout_byte_offset INTEGER,rollout_ordinal INTEGER)')
                c.execute('INSERT INTO thread_turns VALUES (?,?,?,?,?,?)',('abc','turn1','inProgress',123,len(prefix),2));c.commit()
            reader=TaskUsageReader(home);task=reader.read(['abc'])[0]
            if os.name=='nt':self.assertEqual(reader.safe_rollout('\\\\?\\'+str(path)),path.resolve())
            self.assertEqual((task['title'],task['total_tokens'],task['turn_tokens']),('可见名称',160,60))
            self.assertNotIn('private',str(task));self.assertEqual(task['cached_input_tokens'],50)
            path.write_bytes(prefix+event(190));task=reader.read(['abc'])[0]
            self.assertEqual((task['total_tokens'],task['turn_tokens']),(190,90))
            self.assertEqual(reader.read([]),[]);self.assertEqual(reader.baselines,{})

    def test_missing_schema_and_untrusted_paths(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            reader=TaskUsageReader(d);task=reader.read(['abc'])[0]
            self.assertIsNone(task['total_tokens']);self.assertIsNone(task['turn_tokens'])
            self.assertIsNone(reader.safe_rollout(Path(d).parent/'elsewhere.jsonl'))
            self.assertIsNone(last_token_event(Path(d)/'missing',empty_zero=True))

if __name__=='__main__':unittest.main()
