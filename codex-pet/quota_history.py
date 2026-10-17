"""Recover timestamped quota metadata from local Codex token_count events."""
from datetime import datetime
import json,os,time
from pathlib import Path
from daily_budget import valid_number,DAY

class QuotaHistory:
    def __init__(self,home=None):
        self.home=Path(home) if home else Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))
        self.files={}

    def read(self,since,until=None):
        until=time.time() if until is None else until
        result=[];live=set()
        for folder in ('sessions','archived_sessions'):
            for path in (self.home/folder).rglob('*.jsonl'):
                try:
                    stat=path.stat()
                    if stat.st_mtime<since-DAY:continue
                    live.add(path);cached=self.files.get(path)
                    offset,points=(cached if cached and cached[0]<=stat.st_size else (0,[]))
                    with path.open('rb') as stream:
                        stream.seek(offset)
                        while True:
                            start=stream.tell();line=stream.readline()
                            if not line:break
                            if not line.endswith(b'\n'):
                                stream.seek(start);break
                            if b'"token_count"' not in line:continue
                            try:record=json.loads(line)
                            except ValueError:continue
                            if not isinstance(record,dict) or record.get('type')!='event_msg':continue
                            payload=record.get('payload')
                            if not isinstance(payload,dict) or payload.get('type')!='token_count':continue
                            rate=payload.get('rate_limits')
                            if not isinstance(rate,dict) or rate.get('limit_id') not in (None,'codex'):continue
                            for window in (rate.get('primary'),rate.get('secondary')):
                                if not isinstance(window,dict) or window.get('window_minutes')!=10080:continue
                                used=window.get('used_percent');reset=window.get('resets_at')
                                if not all(valid_number(v) for v in (used,reset)) or not 0<=used<=100:continue
                                stamp=record.get('timestamp')
                                if not isinstance(stamp,str):continue
                                try:at=datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()
                                except (ValueError,TypeError,KeyError):continue
                                if at<reset:points.append({'at':at,'remaining':100-used,'reset':reset})
                        offset=stream.tell()
                    points=[p for p in points if p['at']>=since-DAY]
                    self.files[path]=(offset,points);result.extend(p for p in points if p['at']<=until)
                except OSError:continue
        self.files={path:value for path,value in self.files.items() if path in live}
        # Repeated token events often carry identical snapshots; preserve times
        # around the day boundary, but never conversation text or credentials.
        return sorted(result,key=lambda p:p['at'])
