"""Observed weekly quota budget, with Beijing 02:00 business days."""
from datetime import datetime, timedelta, timezone
import json, math, time
from pathlib import Path

BEIJING = timezone(timedelta(hours=8))
DAY = 86400

def day_start(timestamp):
    local = datetime.fromtimestamp(timestamp, BEIJING)-timedelta(hours=2)
    return local.replace(hour=2,minute=0,second=0,microsecond=0).timestamp()

def valid_number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

class DailyBudget:
    def __init__(self, path=None, clock=time.time):
        self.path = Path(path) if path else None
        self.clock = clock; self.records = []; self.samples = []; self.current = None; self.save_failed = False
        if self.path:
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                self.samples=[p for p in data.get('samples',[]) if isinstance(p,dict)
                              and all(valid_number(p.get(k)) for k in ('at','remaining','reset'))
                              and 0<=p['remaining']<=100][-10000:]
                for row in data['records'][-60:]:
                    if not isinstance(row,dict):continue
                    if not all(valid_number(row.get(k)) for k in ('day','reset','observed_at','began_at','baseline','limit','used','days')):continue
                    if not (0<=row['baseline']<=100 and 0<=row['limit']<=100 and 0<=row['used']<=100 and 1<=row['days']<=7):continue
                    row['alerts'] = [level for level in row.get('alerts',[]) if level in (80,100)]
                    row['partial'] = bool(row.get('partial',True))
                    self.records.append(row)
                if self.records:self.current = self.records[-1]
            except (OSError,ValueError,TypeError,KeyError):pass

    def save(self):
        if not self.path:return
        try:
            temporary = self.path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps({'version':2,'records':self.records[-60:],'samples':self.samples},ensure_ascii=False,indent=2),encoding='utf-8')
            temporary.replace(self.path); self.save_failed = False
        except OSError:self.save_failed = True

    def observe(self, snapshot, history=()):
        weekly = next((w for w in snapshot.get('windows',[]) if w.get('minutes')==10080),None)
        if not weekly:return []
        observed = snapshot.get('retrieved_at'); remaining = weekly.get('remaining'); reset = weekly.get('resets_at')
        if not all(valid_number(v) for v in (observed,remaining,reset)):return []
        if not 0<=remaining<=100 or reset<=observed or observed>self.clock()+300:return []
        if reset-7*DAY>observed+120:return []
        if self.current and observed<self.current['observed_at']:return []
        day = day_start(observed)
        points=list(self.samples)+[{'at':observed,'remaining':remaining,'reset':reset}]
        for old in self.records:
            points.append({'at':old['began_at'],'remaining':old['baseline'],'reset':old['reset']})
        points.extend(p for p in history if isinstance(p,dict)
                      and all(valid_number(p.get(k)) for k in ('at','remaining','reset'))
                      and 0<=p['remaining']<=100 and p['at']<=observed)
        self.samples=sorted({(p['at'],p['remaining'],p['reset']):p for p in points
                            if day-8*DAY<=p['at']<=observed}.values(),key=lambda p:p['at'])[-10000:]
        cycle_start=reset-7*DAY;anchor=max(day,cycle_start)
        candidates=[p for p in self.samples if abs(p['reset']-reset)<=120 and p['at']>=cycle_start-120]
        candidates.extend({'at':r['began_at'],'remaining':r['baseline'],'reset':r['reset']}
                          for r in self.records if abs(r['reset']-reset)<=120 and r['began_at']>=cycle_start-120)
        before=[p for p in candidates if p['at']<=anchor]
        if not candidates:return []
        reference=max(before,key=lambda p:p['at']) if before else min(candidates,key=lambda p:p['at'])
        # Prefer a recorded zero-use snapshot near a weekly reset: it proves
        # the whole new cycle's consumption, even if installed much later.
        if cycle_start>day:
            zero=[p for p in candidates if p['remaining']==100 and p['at']>=cycle_start]
            if zero:reference=min(zero,key=lambda p:p['at'])
        coverage=('boundary' if anchor-reference['at']<=180 else 'estimated') if before else ('boundary' if reference['at']<=anchor+180 else 'lower_bound')
        gap_before_reset=cycle_start>day and not any(r['day']==day and r['reset']<reset-120 for r in self.records)
        if gap_before_reset:coverage='lower_bound'
        row = self.current
        if not row or row['day']!=day or abs(row['reset']-reset)>120:
            # Anchor the 7 -> 6 -> ... -> 1 schedule to the real weekly cycle,
            # rather than the day the pet happened to be installed.
            first_day = day_start(reset-7*DAY)
            days = max(1,min(7,7-round((day-first_day)/DAY)))
            row = {'day':day,'reset':reset,'observed_at':observed,'began_at':observed,
                   'baseline':reference['remaining'],'limit':reference['remaining']/days,'used':0.,'days':days,'alerts':[],
                   'partial':coverage!='boundary'}
            self.records.append(row); self.records = self.records[-60:]; self.current = row
        row['baseline']=reference['remaining'];row['began_at']=reference['at'];row['limit']=row['baseline']/row['days']
        row['coverage']=coverage;row['partial']=coverage!='boundary';row['gap_before_reset']=gap_before_reset
        row['used'] = max(row['used'],max(0.,row['baseline']-remaining))
        row['observed_at'] = observed
        alerts = []
        if row['limit']>0:
            today=[r for r in self.records if r['day']==day]
            percent = sum(r['used'] for r in today)/sum(r['limit'] for r in today)*100
            row['alerts']=sorted({v for r in today for v in r['alerts']})
            level = 100 if percent>=100 else (80 if percent>=80 else None)
            if level and level not in row['alerts']:
                alerts.append(level)
                # Crossing both thresholds in one quota update gives one notice.
                row['alerts'] = sorted(set(row['alerts']+[v for v in (80,100) if v<=level]))
        self.save(); return alerts

    def view(self, now=None):
        now = self.clock() if now is None else now
        row = self.current
        if not row:return {'status':'missing'}
        if day_start(now)!=row['day'] or now>=row['reset']:return {'status':'stale'}
        today=[r for r in self.records if r['day']==row['day']]
        used=sum(r['used'] for r in today);limit=sum(r['limit'] for r in today)
        coverage=('lower_bound' if any(r.get('coverage','lower_bound')=='lower_bound' for r in today)
                  else ('estimated' if any(r.get('coverage')=='estimated' for r in today) else 'boundary'))
        return {**row,'coverage':coverage,'used':used,'limit':limit,'segment_limit':row['limit'],'cycle_count':len(today),
                'status':'ready','left':max(0.,limit-used),
                'ratio':min(1.,used/limit) if limit else 1.,
                'over':max(0.,used-limit),'save_failed':self.save_failed}
