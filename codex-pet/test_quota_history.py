import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from quota_history import QuotaHistory

class HistoryTests(unittest.TestCase):
    def test_only_quota_metadata_and_incremental_partial_lines(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            home=Path(d);folder=home/'sessions/2026/10/17';folder.mkdir(parents=True)
            path=folder/'log.jsonl';when=datetime(2026,10,17,3,tzinfo=timezone.utc).timestamp()
            def event(used,bucket='codex'):
                return json.dumps({'timestamp':'2026-10-17T03:00:00Z','type':'event_msg','payload':{
                    'type':'token_count','rate_limits':{'limit_id':bucket,'secondary':{
                        'window_minutes':10080,'used_percent':used,'resets_at':when+604800}}}}).encode()+b'\n'
            path.write_bytes(b'{"type":"response_item","payload":{"text":"private"}}\n'+event(0)+event(20,'other'))
            reader=QuotaHistory(home);points=reader.read(when-3600,when+10)
            self.assertEqual([p['remaining'] for p in points],[100]);self.assertNotIn('private',str(points))
            more=event(17)
            with path.open('ab') as f:f.write(more[:30])
            self.assertEqual(len(reader.read(when-3600,when+10)),1)
            with path.open('ab') as f:f.write(more[30:])
            self.assertEqual([p['remaining'] for p in reader.read(when-3600,when+10)],[100,83])

if __name__=='__main__':unittest.main()
