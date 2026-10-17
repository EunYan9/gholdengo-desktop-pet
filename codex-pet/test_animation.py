"""Real WebP decoding: emotions, original pose bridges and lifecycle races."""
import os,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QEventLoop,QTimer
from PySide6.QtWidgets import QApplication
from sprite_player import SpritePlayer,IDLE_ACTIONS
from main import quota_stage,Pet,ActivityWorker

app=QApplication([])
class Clock:
    value=1000.
    def __call__(self):return self.value
clock=Clock();player=SpritePlayer(clock=clock);player.automatic=False
seen=[];invalid=[]
def record(clip):
    seen.append((player.stage,clip,player.mode))
    if not player.animation.isValid():invalid.append(clip)
    player.animation.setSpeed(1000)
player.clip_changed.connect(record)
def run_for(ms):
    loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
def until(check,ms=5000):
    end=time.monotonic()+ms/1000
    while not check() and time.monotonic()<end:run_for(10)
    assert check(),seen[-25:]
    assert not invalid,invalid
def clips():return [clip for _,clip,_ in seen]
def ready(mode='idle'):until(lambda:player.resting and player.mode==mode)
def focus():
    player.set_working(True);ready('focus')
    assert player.current==('battlewait01_loop' if player.stage=='roaming' else 'focus01_loop')
def quiet():
    player.set_working(False,outcome='unknown');ready('idle')

assert [quota_stage(x) for x in (0,2.99,3,19.99,20,79.99,80,100)]==[
    'depleted','depleted','roaming','roaming','chest','chest','gholdengo','gholdengo']
assert quota_stage(98,True)=='depleted'

player.set_stage('chest');seen.clear()
start=time.monotonic();player.request()
assert player.current=='glad01' and time.monotonic()-start<.1
ready();assert clips()==['glad01','defaultwait01_loop']
clock.value+=10;seen.clear();player.request()
for _ in range(15):player.request()
ready();assert clips()==['glad01','glad01','hate01','defaultwait01_loop'],seen
assert player.click_count==16

# A rolling one-second window is not a chain of pairwise click intervals.
for offsets,should_annoy in [([0,.65,1.1],False),([0,.45,.9],True),([0,.5,1.0],True)]:
    base=clock.value+10;seen.clear()
    for offset in offsets:
        clock.value=base+offset
        epoch=player.epoch;serial=player.tap_serial
        started=time.monotonic();player.request()
        assert player.tap_serial==serial+1 and player.tap_time==clock()
        assert time.monotonic()-started<.1 and player.epoch>epoch
    assert (player.mode=='annoyed')==should_annoy,(offsets,seen)
    if should_annoy:
        epoch=player.epoch;player.request();assert player.epoch==epoch
    ready()
clock.value+=10
# A second single click during a manual action reacts immediately, without idle.
player.request();run_for(30);epoch=player.epoch;player.request()
assert player.epoch>epoch and player.mode=='happy' and not player.resting
ready()

seen.clear();focus()
assert clips()==['focus01_start','focus01_loop'],seen
assert player.pose=='focus' and player.badge_text()=='专注'
seen.clear();player.request('small');player.perform_pending();ready('focus')
assert clips()[0] in ('focus01_ack','focus01_glance') and clips()[-1]=='focus01_loop',seen
assert 'focus01_end' not in clips() and 'focus01_start' not in clips(),seen
player.animation.setSpeed(100)
until(lambda:player.animation.currentFrameNumber()>=8)
before=player.animation.currentImage().copy()
player.request('happy')
assert player.current=='focus01_ack' and player.animation.currentImage()==before
assert player.old_frame is None,'Matching original poses should not need a dissolve'
ready('focus')
seen.clear();player.request('happy');ready('focus')
assert clips()==['focus01_ack','focus01_loop'],seen
assert player.badge_text()=='专注'
seen.clear();player.request('small');player.perform_pending();epoch=player.epoch;player.request('happy')
assert player.epoch>epoch and player.mode=='happy'
ready('focus');assert clips()[0] in ('focus01_ack','focus01_glance') and clips()[1:]==['focus01_ack','focus01_loop'],seen

# Every actual phase can be interrupted on the identical decoded source pose.
# This covers opening, closing and already interrupted reactions, not just the
# loop's first frame. Nothing is hidden behind a dissolve or an idle detour.
max_focus_click=0
for name in ('focus01_start','focus01_loop','focus01_end','focus01_ack','focus01_glance'):
    for frame in range(player.frame_meta['chest'][name]['frames']):
        player.play(name,blend=False,start_frame=frame,speed=1)
        player.animation.setSpeed(1)
        before=player.animation.currentImage().copy();epoch=player.epoch
        began=time.monotonic();player.request('happy')
        max_focus_click=max(max_focus_click,time.monotonic()-began)
        assert player.current=='focus01_ack' and player.epoch>epoch,(name,frame)
        assert player.animation.currentImage()==before,(name,frame)
        assert player.old_frame is None and player.badge_text()=='收到',(name,frame)
        run_for(1)
ready('focus')
assert max_focus_click<.15,max_focus_click
print('All focus phases preserve the displayed pose; slowest click:',round(max_focus_click*1000),'ms')
# The third tap still interrupts a focused acknowledgement with an immediate,
# matching-pose exit into the distinct annoyed animation.
clock.value+=10;seen.clear()
for _ in range(3):
    player.request();clock.value+=.15;run_for(10)
assert player.mode=='annoyed' and player.current in ('focus01_end','hate01'),seen
ready('focus');assert 'hate01' in clips() and clips()[-2:]==['focus01_start','focus01_loop'],seen
seen.clear();player.set_working(False,outcome='completed');ready()
assert clips()==['focus01_end','finish01','defaultwait01_loop'],seen
assert any(mode=='celebrate' for _,_,mode in seen)
focus();player.set_working(False,outcome='completed')
until(lambda:player.current=='finish01')
epoch=player.epoch;clock.value+=10;player.request()
assert player.epoch>epoch and player.current=='glad01' and player.mode=='happy'
ready()
for outcome in ['interrupted','failed','unknown']:
    focus();seen.clear();player.set_working(False,outcome=outcome);ready()
    assert 'glad01' not in clips() and 'finish01' not in clips(),(outcome,seen)

# Idle nap has complete original entry/exit and yields to both clicks and work.
seen.clear();player.request('drowsy');ready('nap')
assert clips()==['sleep01_start','sleep01_loop'] and player.nap.isActive()
clock.value+=20;seen.clear();player.request();ready()
assert clips()==['sleep01_end','notice01','defaultwait01_loop'],seen
assert not player.nap.isActive()
clock.value+=player.nap_after+1;seen.clear();player.request('small');player.perform_pending();ready('nap')
player.finish_nap();ready();assert 'sleep01_end' in clips()
player.request('drowsy');ready('nap');seen.clear();focus()
assert clips()==['sleep01_end','focus01_start','focus01_loop'],seen
quiet()

# Clicking during sleep entry reverses from the current original pose immediately.
player.request('drowsy');run_for(10)
if not player.resting:
    epoch=player.epoch;player.request('happy')
    assert player.epoch>epoch and player.mode=='happy'
    ready()
else:
    player.finish_nap();ready()

# A new task arriving during an entry transition waits for the original pose.
player.set_stage('depleted');seen.clear();player.set_working(True);ready('focus')
assert clips()==['sleep01_end','focus01_start','focus01_loop'],seen
seen.clear();player.set_working(False,outcome='completed');ready('sleep')
assert clips()==['focus01_end','notice01','sleep01_start','sleep01_loop'],seen
clock.value+=20;seen.clear();player.request();ready('sleep')
assert clips()==['sleep01_end','notice01','sleep01_start','sleep01_loop'],seen
assert 'glad01' not in clips()

# A short real task may finish before the greeting; no stale focus loop remains.
player.set_stage('chest');seen.clear();player.set_working(True);player.set_working(False,outcome='completed');ready()
assert any(mode=='celebrate' and clip=='finish01' for _,clip,mode in seen) and player.current=='defaultwait01_loop'
assert 'focus01_loop' not in clips(),seen
for stage,pool in IDLE_ACTIONS.items():
    player.set_stage(stage);ready();player.rng.seed(3)
    picks=[player.choose_small() for _ in range(30)]
    assert set(picks)==set(pool) and all(a!=b for a,b in zip(picks,picks[1:]))
    for clip in pool:
        player.run_action([clip]);ready()
    player.automatic=True;intervals=[]
    for _ in range(10):player.schedule_small();intervals.append(player.small.interval())
    assert len(set(intervals))>1 and all(16000<=x<=30000 for x in intervals)
    player.automatic=False;player.small.stop()
player.set_stage('roaming');ready()
player.request('drowsy');ready('nap');assert player.current=='rest01_loop'
player.finish_nap();ready();assert player.pose=='awake'
player.request('happy');seen.clear();player.set_stage('chest');run_for(700)
assert all(stage=='chest' for stage,_,_ in seen) and player.resting
assert player.path(player.current).parent.name=='chest'
player.stop();assert not any(timer.isActive() for timer in [player.small,player.boundary,player.fade,player.thought,player.nap])

# Actual worker dispatch distinguishes successful completion from interruptions.
import main as main_module
original=main_module.read_activity
class Stop:
    index=0
    def is_set(self):return self.index>=len(snapshots)
    def wait(self,_):self.index+=1
snapshots=[{'state':'working','count':2,'active_ids':['abc','def'],'outcomes':{}},
           {'state':'working','count':1,'active_ids':['abc'],'outcomes':{'def':'completed'}},
           {'state':'idle','count':0,'active_ids':[],'outcomes':{'abc':'interrupted','def':'completed'}}]
worker=ActivityWorker();worker.stop=Stop();events=[];worker.updated.connect(events.append)
main_module.read_activity=lambda **kwargs:snapshots[worker.stop.index]
try:worker.run()
finally:main_module.read_activity=original
assert events[-1]['outcome']=='interrupted',events

pet=Pet(demo=True,stage='chest');pet.header.setText('5小时 79% │ 周 97%');pet.show();run_for(50)
assert pet.header.width()<220
pet.update_activity({'state':'working','count':1});run_for(50)
assert not pet.view.toolTip() and '工作中' in pet.activity_status.text()
pet.shutdown();pet.close()
print('PASS: instant clicks; strict rolling clicks; immediate interruption; pose bridges; focus gestures; success vs interruption; naps; rapid work changes; stage changes; random pools; hover regression; timers stopped')
