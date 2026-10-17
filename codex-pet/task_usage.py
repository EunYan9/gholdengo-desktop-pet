"""Read task metadata; parse only token counters from bounded rollout tails."""
import json, os, sqlite3
from contextlib import closing
from pathlib import Path

def counter(value):
    return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else None

def last_token_event(path, end=None, empty_zero=False):
    """Scan a bounded tail for complete token_count metadata records only."""
    try:
        with path.open('rb') as stream:
            stream.seek(0,2); end = min(end,stream.tell()) if end is not None else stream.tell()
            amount = 65536
            while True:
                start = max(0,end-amount);stream.seek(start);lines = stream.read(end-start).splitlines()
                if start:lines = lines[1:]
                for line in reversed(lines):
                    if b'"token_count"' not in line:continue
                    try:record = json.loads(line)
                    except ValueError:continue
                    if not isinstance(record,dict):continue
                    payload = record.get('payload',{})
                    if not isinstance(payload,dict):continue
                    if record.get('type')!='event_msg' or payload.get('type')!='token_count':continue
                    info = payload.get('info')
                    if not isinstance(info,dict):continue
                    total = info.get('total_token_usage')
                    if not isinstance(total,dict) or counter(total.get('total_tokens')) is None:continue
                    return {'total':{key:counter(total.get(key)) for key in
                            ('total_tokens','input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens')},
                            'timestamp':record.get('timestamp')}
                if not start:
                    return {'total':{'total_tokens':0},'timestamp':None} if empty_zero else None
                if amount>=8*1024*1024:return None
                amount *= 2
    except (OSError,ValueError,TypeError):return None

class TaskUsageReader:
    def __init__(self,home=None):
        self.home = Path(home) if home else Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))
        self.latest = {};self.baselines = {}

    def safe_rollout(self,raw):
        try:
            # Codex stores extended Windows paths; normalize their prefix before
            # comparing against the ordinary CODEX_HOME path.
            raw = str(raw)
            if raw.startswith('\\\\?\\UNC\\'):raw = '\\\\'+raw[8:]
            elif raw.startswith('\\\\?\\'):raw = raw[4:]
            path = Path(raw).resolve()
            if any(path.is_relative_to((self.home/folder).resolve()) for folder in ('sessions','archived_sessions')):
                return path
        except (OSError,ValueError,TypeError):pass
        return None

    def read(self, active_ids):
        tasks = {id:{'id':id,'title':f'任务 {id[:8]}','total_tokens':None,'turn_tokens':None} for id in active_ids}
        if not tasks:
            self.latest.clear();self.baselines.clear();return []
        marks = ','.join('?' for _ in tasks)
        turns = {}
        try:
            with closing(sqlite3.connect((self.home/'thread_history_1.sqlite').as_uri()+'?mode=ro',uri=True,timeout=.3)) as con:
                rows = con.execute(f'''SELECT thread_id,turn_id,started_at,rollout_byte_offset
                    FROM thread_turns AS t WHERE thread_id IN ({marks}) AND status='inProgress'
                    AND NOT EXISTS (SELECT 1 FROM thread_turns AS n WHERE n.thread_id=t.thread_id
                        AND n.rollout_ordinal>t.rollout_ordinal)''',list(tasks)).fetchall()
                turns = {id:(turn,start,offset) for id,turn,start,offset in rows}
        except (OSError,sqlite3.Error):pass
        try:
            with closing(sqlite3.connect((self.home/'state_5.sqlite').as_uri()+'?mode=ro',uri=True,timeout=.3)) as con:
                # Read a deliberately narrow projection, never first_user_message/preview.
                rows = con.execute(f'SELECT id,name,title,tokens_used,rollout_path FROM threads WHERE id IN ({marks})',list(tasks)).fetchall()
        except (OSError,sqlite3.Error):rows = []
        for id,name,title,indexed_tokens,raw in rows:
            task = tasks[id]
            task['title'] = ' '.join(str(name or title or task['title']).split())[:300]
            task['total_tokens'] = counter(indexed_tokens)
            path = self.safe_rollout(raw); event = None
            if path:
                try:
                    stat = path.stat(); signature = (str(path),stat.st_size,stat.st_mtime_ns)
                    cached = self.latest.get(id)
                    if not cached or cached[0]!=signature:self.latest[id] = (signature,last_token_event(path))
                    event = self.latest[id][1]
                except OSError:pass
            if event:
                task.update(event['total']);task['total_tokens'] = event['total']['total_tokens']
                task['usage_at'] = event['timestamp']
            if id in turns:
                turn,start,offset = turns[id];task['started_at'] = start
                key = (id,turn,offset)
                if path and counter(offset) is not None:
                    if key not in self.baselines:
                        before = last_token_event(path,offset,empty_zero=True)
                        self.baselines[key] = before['total']['total_tokens'] if before else None
                    base = self.baselines[key]
                    if base is not None and task['total_tokens'] is not None and task['total_tokens']>=base:
                        task['turn_tokens'] = task['total_tokens']-base
        self.latest = {id:value for id,value in self.latest.items() if id in tasks}
        current_turns = {(id,turn,offset) for id,(turn,start,offset) in turns.items()}
        self.baselines = {key:value for key,value in self.baselines.items() if key in current_turns}
        return sorted(tasks.values(),key=lambda row:(row['title'],row['id']))
