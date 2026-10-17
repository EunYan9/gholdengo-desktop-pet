"""Verify native source and uninterrupted playback for supported feedback."""
import hashlib,json,os,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QEventLoop,QTimer
from PySide6.QtWidgets import QApplication
from sprite_player import SpritePlayer,ROOT
from review import Review
app=QApplication([])
class Clock:
    value=1000.
    def __call__(self):return self.value
clock=Clock();p=SpritePlayer(clock=clock);p.set_stage('gholdengo')
assert set(p.frame_meta['gholdengo'])=={'defaultwait01_loop'}
assert p.animation.isValid() and p.animation.frameCount()==80
info=json.loads((ROOT/'gholdengo-sources.json').read_text(encoding='utf-8'))['active']
assert hashlib.sha256(p.path(p.current).read_bytes()).hexdigest()==info['sha256']
movie=p.animation;epoch=p.epoch
loop=QEventLoop();QTimer.singleShot(200,loop.quit);loop.exec()
assert movie.currentFrameNumber()>0
slowest=0
for _ in range(80):
    before=p.animation.currentImage().copy();clock.value+=2
    started=time.monotonic();p.request();slowest=max(slowest,time.monotonic()-started)
    assert p.animation is movie and p.epoch==epoch and p.animation.currentImage()==before
    assert p.badge_text()=='你好'
    assert p.coins.coins and p.coins.timer.isActive()
assert slowest<.1
clock.value+=5
for _ in range(3):p.request();clock.value+=.15
assert p.badge_text()=='别戳啦' and p.click_count==3
clock.value+=3;p.set_working(True);assert p.badge_text()=='专注'
p.request('happy');assert p.badge_text()=='收到'
clock.value+=2;assert p.badge_text()=='专注'
for outcome,label in [('completed','收工'),('interrupted','稍歇'),('failed','稍歇')]:
    p.set_working(False,outcome);assert p.badge_text()==label
    clock.value+=5;assert p.badge_text()==''
    p.set_working(True)
assert p.animation is movie and p.epoch==epoch and p.animation.speed()==100
for kind in ('small','drowsy'):p.request(kind)
assert not p.small.isActive() and not p.nap.isActive() and p.pose=='awake'
p.set_stage('chest');assert p.path(p.current).parent.name=='chest'
assert not p.coins.coins and not p.coins.timer.isActive()
p.stop()
v=Review('gholdengo')
assert not v.action_buttons['small'].isEnabled() and not v.action_buttons['drowsy'].isEnabled()
assert not v.automatic.isEnabled()
v.select('chest');assert all(b.isEnabled() for b in v.action_buttons.values()) and v.automatic.isEnabled()
v.close()
print('PASS: source hash, real native playback, uninterrupted feedback, rolling clicks, supported controls, stage changes; slowest click',round(slowest*1000),'ms')
