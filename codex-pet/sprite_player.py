"""Original-pose animation player with queued emotions and work companionship."""
from pathlib import Path
from collections import deque
import json
import math
import random
import time
from PySide6.QtCore import QElapsedTimer, QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QMovie, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel
from coin_effects import CoinBurst

ROOT = Path(__file__).resolve().parent
IDLE_ACTIONS = {
    'chest': ('notice01', 'defaultidle01'),
    'roaming': ('notice01', 'defaultidle02', 'refresh01'),
}
WORK_ACTIONS = {'chest': ('focus01_ack', 'focus01_glance'), 'roaming': ('notice01', 'refresh01')}
POSE_END = {'sleep': 'sleep01_end', 'rest': 'rest01_end', 'focus': 'focus01_end'}
POSE_AFTER = {'sleep01_start': 'sleep', 'sleep01_end': 'awake',
              'rest01_start': 'rest', 'rest01_end': 'awake',
              'focus01_start': 'focus', 'focus01_end': 'awake',
              'focus01_ack': 'focus', 'focus01_glance': 'focus',
              'sleep01_cancel': 'awake', 'rest01_cancel': 'awake'}


class SpritePlayer(QLabel):
    context_requested = Signal(object)
    clip_changed = Signal(str)
    mood_changed = Signal(str)
    task_hovered = Signal(object)
    task_left = Signal()

    def __init__(self, parent=None, clock=time.monotonic):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName('petSprite')
        self.setStyleSheet('QLabel#petSprite{background:transparent}')
        self.setMouseTracking(True); self.over_badge = False
        self.clock = clock; self.rng = random.Random()
        self.frame_meta = json.loads((ROOT/'sprites/manifest.json').read_text(encoding='utf-8'))['models']
        self.movie_model = None
        self.stage = ''; self.current = ''; self.animation = None; self.epoch = 0
        self.resting = False; self.mode = 'idle'; self.pose = 'awake'; self.stopped = False
        self.pending = None; self.pending_emotion = None; self.work_event = None
        self.action_kind = None; self.last_small = {}
        self.canvas_size = 270; self.automatic = True; self.working = False
        self.dozing = False; self.last_touch = self.clock()
        self.nap_after = self.rng.uniform(110, 170)
        self.click_times = deque(); self.click_count = 0
        self.tap_time = -100.; self.tap_point = QPointF(); self.tap_serial = 0
        self.coins = CoinBurst(self,clock=self.clock)
        self.status_text = ''; self.status_until = 0.; self.thought_phase = 0
        self.thought = QTimer(self); self.thought.setInterval(50)
        self.thought.timeout.connect(self.think)
        self.old_frame = None; self.fade_clock = QElapsedTimer(); self.fade_ms = 160
        self.fade = QTimer(self); self.fade.setInterval(16); self.fade.timeout.connect(self.update_fade)
        self.small = QTimer(self); self.small.setSingleShot(True)
        self.small.timeout.connect(lambda: self.request('small'))
        self.boundary = QTimer(self); self.boundary.setSingleShot(True)
        self.boundary.timeout.connect(self.perform_pending)
        self.nap = QTimer(self); self.nap.setSingleShot(True); self.nap.timeout.connect(self.finish_nap)

    def set_stage(self, stage):
        if self.stage == stage and self.animation is not None and not self.stopped: return
        self.small.stop(); self.boundary.stop(); self.nap.stop()
        self.coins.clear()
        self.pending = None; self.pending_emotion = None
        self.stage = stage; self.pose = 'awake'; self.dozing = False; self.stopped = False
        self.resting = False
        self.work_event = 'start' if self.working else None
        self.last_touch = self.clock(); self.click_count = 0
        self.click_times.clear()
        self.settle()

    def path(self, clip):
        model = self.stage if self.stage in ('roaming','gholdengo') else 'chest'
        return ROOT / 'sprites' / model / (clip + '.webp')

    def source_pose(self):
        if not self.animation or self.movie_model not in self.frame_meta: return None
        meta = self.frame_meta[self.movie_model].get(self.current,{})
        frame = max(0,self.animation.currentFrameNumber())
        indices = meta.get('source_indices',meta.get('frame_indices'))
        source_frame = indices[min(frame,len(indices)-1)] if indices else frame
        return self.movie_model,meta.get('source',self.current),source_frame

    def visible_frame(self):
        if not self.animation: return QPixmap()
        current = self.animation.currentPixmap()
        if self.old_frame is None or not self.fade.isActive(): return current.copy()
        progress = min(1.,self.fade_clock.elapsed()/self.fade_ms)
        progress = progress*progress*(3-2*progress)
        frame = QPixmap(self.old_frame.size()); frame.fill(Qt.GlobalColor.transparent)
        painter = QPainter(frame); painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for source,opacity in ((self.old_frame,1-progress),(current,progress)):
            painter.setOpacity(opacity); painter.drawPixmap(0,0,source)
        painter.end(); return frame

    def play(self, clip, done=None, blend=True, start_frame=0, speed=None):
        model = 'roaming' if self.stage == 'roaming' else ('gholdengo' if self.stage == 'gholdengo' else 'chest')
        meta = self.frame_meta.get(model,{}).get(clip,{})
        indices = meta.get('source_indices',meta.get('frame_indices'))
        source_frame = indices[min(start_frame,len(indices)-1)] if indices else start_frame
        target_pose = (model,meta.get('source',clip),source_frame)
        if self.source_pose() == target_pose and not self.fade.isActive(): blend=False
        previous = self.visible_frame() if blend else None
        self.epoch += 1; token = self.epoch
        self.fade.stop(); self.old_frame = previous
        if self.animation:
            self.animation.stop(); self.animation.deleteLater()
        self.current = clip; self.movie_model = model
        movie = self.animation = QMovie(str(self.path(clip)))
        if start_frame: movie.setCacheMode(QMovie.CacheMode.CacheAll)
        movie.setScaledSize(QSize(self.canvas_size, self.canvas_size))
        self.setMovie(movie)
        if not movie.isValid():
            self.setText('本地动作素材缺失'); return
        # Opening, closing and loop poses retain original timing.
        if speed is not None: movie.setSpeed(speed)
        elif self.mode in ('happy', 'annoyed') and clip in ('glad01', 'hate01', 'refresh01'):
            movie.setSpeed(125)
        def frame_changed(frame):
            if token != self.epoch: return
            if self.resting and self.pending and frame == movie.frameCount()-1:
                self.boundary.start(max(1, movie.nextFrameDelay()))
        def finished():
            if token != self.epoch or self.stopped: return
            self.pose = POSE_AFTER.get(clip, self.pose)
            if done: done()
        movie.frameChanged.connect(frame_changed)
        if done: movie.finished.connect(finished)
        if self.old_frame is not None and not self.old_frame.isNull():
            self.fade_clock.start(); self.fade.start()
        else: self.old_frame = None
        movie.start()
        # The WebP reader does not support arbitrary jumps into an uncached
        # movie. Decode the short transition prefix synchronously; paints are
        # queued, so only the requested matching pose reaches the screen.
        while movie.currentFrameNumber() < start_frame:
            if not movie.jumpToNextFrame():
                raise RuntimeError('Cannot seek original pose in '+clip)
        self.clip_changed.emit(clip)

    def sequence(self, clips, done, blend=True):
        self.resting = False
        if not clips:
            done(); return
        def advance():
            remaining = clips[1:]
            urgent = self.pending_emotion or self.work_event
            ended_work = self.mode == 'ambient' and not self.working and 'focus01_start' in remaining
            if remaining and self.pose == 'awake' and (urgent or ended_work) and self.mode not in ('happy','annoyed','peek'):
                self.settle()
            else:
                self.sequence(remaining, done, blend)
        item = clips[0]
        clip,start_frame,speed = item if isinstance(item,tuple) else (item,0,None)
        self.play(clip, advance, blend=blend, start_frame=start_frame, speed=speed)

    def set_mode(self, mode):
        if self.mode != mode:
            self.mode = mode; self.mood_changed.emit(mode)
        if self.badge_text() and not self.thought.isActive(): self.thought.start()
        self.update()

    def run_action(self, clips, mode='ambient', done=None):
        self.small.stop(); self.boundary.stop(); self.pending = None
        self.action_kind = mode; self.set_mode(mode)
        self.sequence(clips, done or self.settle)

    def ensure_awake(self):
        if self.pose == 'awake': return True
        self.nap.stop()
        clip = POSE_END[self.pose]
        self.run_action([(clip,self.focus_exit_frame(),None)] if self.pose == 'focus' else [clip], 'transition')
        return False

    def focus_exit_frame(self):
        pose = self.source_pose()
        model = 'gholdengo' if self.stage == 'gholdengo' else 'chest'
        meta = self.frame_meta[model]['focus01_end']
        indices = meta['source_indices']
        if pose and pose[1] == meta['source']:
            return min(range(len(indices)),key=lambda index:abs(indices[index]-pose[2]))
        return 0

    def focus_reaction_frame(self, clip):
        """Resume the reaction from the pose actually on screen."""
        pose = self.source_pose()
        model = 'gholdengo' if self.stage == 'gholdengo' else 'chest'
        meta = self.frame_meta[model][clip]
        indices = meta['source_indices']
        source_frame = pose[2] if pose and pose[1] == meta['source'] else (12 if model == 'gholdengo' else 24)
        # Prefer the look-up stroke over replaying the entry prefix.
        offset = (12 if clip == 'focus01_ack' and source_frame >= 12 else 0) if model == 'gholdengo' else (24 if clip == 'focus01_ack' and source_frame >= 8 else 0)
        return min(range(offset,len(indices)),key=lambda index:abs(indices[index]-source_frame))

    def set_loop(self, clip, mode):
        same = self.current == clip and self.resting
        self.resting = True; self.action_kind = None; self.pending = None
        self.set_mode(mode)
        if not same: self.play(clip)
        self.schedule_small()

    def settle(self):
        """Reconcile queued events only at a complete original-pose boundary."""
        if self.stopped: return
        if self.stage == 'gholdengo':
            # Only the verified native surfing loop is available. Status
            # changes must not replace, accelerate or restart this animation.
            event = self.work_event; self.work_event = None
            self.pending_emotion = None; self.dozing = False; self.pose = 'awake'
            if not self.working and event in ('completed','interrupted','failed'):
                self.status_text = '收工' if event == 'completed' else '稍歇'
                self.status_until = self.clock()+(4 if event == 'completed' else 3)
            self.set_loop('defaultwait01_loop','focus' if self.working else 'idle')
            return
        if self.work_event:
            if not self.ensure_awake(): return
            event = self.work_event; self.work_event = None
            if event == 'start' and self.working:
                self.run_action(['notice01' if self.stage == 'roaming' else 'focus01_start'], 'greeting'); return
            if event == 'completed' and not self.working:
                self.status_text = '收工'; self.status_until = self.clock()+4
                self.run_action(['notice01' if self.stage == 'depleted' else 'finish01'], 'celebrate'); return
            if event in ('interrupted', 'failed') and not self.working:
                self.status_text = '稍歇'; self.status_until = self.clock()+3
                self.run_action(['defaultidle01' if self.stage != 'roaming' else 'refresh01'], 'settling'); return
        if self.pending_emotion:
            if not self.ensure_awake(): return
            emotion = self.pending_emotion; self.pending_emotion = None
            self.dozing = False; self.nap.stop()
            if self.stage == 'depleted' or emotion == 'peek':
                self.run_action(['notice01'], 'peek'); return
            if emotion == 'annoyed':
                self.run_action(['refresh01' if self.stage == 'roaming' else 'hate01'], 'annoyed'); return
            self.run_action(['glad01'], 'happy'); return
        if self.working:
            if self.stage != 'roaming':
                if self.pose != 'focus':
                    if not self.ensure_awake(): return
                    self.run_action(['focus01_start'], 'transition'); return
            elif not self.ensure_awake(): return
            self.set_loop('battlewait01_loop' if self.stage == 'roaming' else 'focus01_loop', 'focus'); return
        if self.stage == 'depleted':
            if self.pose != 'sleep':
                if not self.ensure_awake(): return
                self.run_action(['sleep01_start'], 'sleep-entry'); return
            self.set_loop('sleep01_loop', 'sleep'); return
        if self.dozing:
            nap_pose = 'rest' if self.stage == 'roaming' else 'sleep'
            if self.pose != nap_pose:
                if not self.ensure_awake(): return
                self.run_action(['rest01_start' if nap_pose == 'rest' else 'sleep01_start'], 'sleep-entry'); return
            self.set_loop('rest01_loop' if nap_pose == 'rest' else 'sleep01_loop', 'nap')
            if not self.nap.isActive(): self.nap.start(self.rng.randint(18000, 28000))
            return
        if not self.ensure_awake(): return
        self.set_loop('defaultwait01_loop', 'idle')

    def idle(self):
        self.settle()

    def set_working(self, value, outcome='completed'):
        value = bool(value)
        if value == self.working: return
        self.working = value; self.dozing = False; self.nap.stop()
        self.last_touch = self.clock(); self.pending = None; self.boundary.stop()
        if value:
            self.work_event = 'start'; self.status_text = ''; self.status_until = 0
        else:
            self.work_event = outcome if outcome in ('completed', 'interrupted', 'failed') else None
        if not self.thought.isActive(): self.thought.start()
        self.update()
        if self.resting: self.settle()

    def finish_nap(self):
        self.nap.stop()
        self.dozing = False; self.last_touch = self.clock()
        self.nap_after = self.rng.uniform(110, 170)
        if self.resting: self.settle()

    def schedule_small(self):
        self.small.stop()
        if not self.automatic or not self.resting or self.dozing or self.stage == 'gholdengo': return
        interval = (9000, 16000) if self.working else ((30000, 42000) if self.stage == 'depleted' else (16000, 30000))
        self.small.start(self.rng.randint(*interval))

    def choose_small(self):
        pool = WORK_ACTIONS[self.stage if self.stage == 'roaming' else 'chest'] if self.working else IDLE_ACTIONS[self.stage]
        key = (self.stage, self.working)
        choices = [clip for clip in pool if clip != self.last_small.get(key)]
        clip = self.rng.choice(choices); self.last_small[key] = clip
        return clip

    def request(self, kind='emotion', point=None):
        if self.stopped: return
        if self.stage == 'gholdengo' and kind in ('small','drowsy'): return
        if kind == 'small':
            if self.resting and not self.dozing: self.pending = kind
            return
        if kind == 'drowsy':
            if self.working or self.stage == 'depleted': return
            self.dozing = True
            if self.resting: self.settle()
            return
        now = self.clock(); self.last_touch = now
        self.tap_time = now; self.tap_serial += 1
        self.tap_point = QPointF(point) if point is not None else QPointF(self.width()/2,self.height()/2)
        if not self.thought.isActive(): self.thought.start()
        self.update()
        self.dozing = False; self.nap.stop()
        while self.click_times and now-self.click_times[0] > 1.: self.click_times.popleft()
        if kind == 'emotion': self.click_times.append(now)
        else: self.click_times.clear()
        self.click_count = len(self.click_times)
        annoyed = kind == 'annoyed' or self.click_count >= 3
        if self.stage == 'gholdengo':
            self.coins.burst(self.tap_point,self.rect(),self.canvas_size/270)
            self.status_text = '别戳啦' if annoyed else ('收到' if self.working else '你好')
            self.status_until = now+(2 if annoyed else 1.4)
            return
        # Every click has immediate feedback. Extra clicks during the same
        # annoyed reaction do not pin it forever on its first frame.
        if annoyed and self.mode == 'annoyed': return
        emotion = 'annoyed' if annoyed else ('peek' if self.stage == 'depleted' or self.pose in ('sleep','rest') else 'happy')
        self.interrupt_emotion(emotion)

    def interrupt_emotion(self, emotion):
        prefix=[]
        focused_clip = self.stage != 'roaming' and self.current.startswith('focus01_')
        if focused_clip and self.working and emotion != 'annoyed':
            self.pending_emotion = None; self.pending = None; self.status_until = 0
            self.run_action([('focus01_ack',self.focus_reaction_frame('focus01_ack'),125)], 'happy')
            return
        if focused_clip:
            prefix=[('focus01_end',self.focus_exit_frame(),250)]
        elif self.current in ('sleep01_start','rest01_start'):
            cancel = self.current.replace('_start','_cancel')
            indices = self.frame_meta[self.movie_model][cancel]['source_indices']
            source_frame = self.source_pose()[2]
            frame = min(range(len(indices)),key=lambda index:abs(indices[index]-source_frame))
            prefix=[(cancel,frame,250)]
        elif self.current in ('sleep01_end','rest01_end','sleep01_cancel','rest01_cancel'):
            prefix=[(self.current,max(0,self.animation.currentFrameNumber()),250)]
        elif self.pose in ('sleep','rest'):
            prefix=[(POSE_END[self.pose],0,250)]
        self.pending_emotion = None; self.pending = None
        self.status_until = 0
        if emotion == 'annoyed': clip='refresh01' if self.stage == 'roaming' else 'hate01'
        else: clip='notice01' if emotion == 'peek' else 'glad01'
        self.run_action(prefix+[clip], 'annoyed' if emotion == 'annoyed' else ('peek' if emotion == 'peek' else 'happy'))

    def perform_pending(self):
        if not self.pending or not self.resting: return
        self.pending = None; self.small.stop(); self.boundary.stop()
        if not self.working and self.stage != 'depleted' and self.clock()-self.last_touch >= self.nap_after:
            self.request('drowsy'); return
        if self.stage == 'depleted' and not self.working:
            self.run_action(['sleep01_end','notice01','sleep01_start'], 'peek'); return
        clip = self.choose_small()
        if self.pose == 'focus' and self.stage != 'roaming':
            self.run_action([(clip,self.focus_reaction_frame(clip),None)])
            return
        clips = [('focus01_end',self.focus_exit_frame(),None),clip,'focus01_start'] if self.pose == 'focus' else [clip]
        self.run_action(clips)

    def badge_text(self):
        if self.stage == 'gholdengo' and self.clock() < self.status_until:
            return self.status_text
        labels = {'greeting':'开工', 'happy':'开心', 'annoyed':'别戳啦', 'peek':'醒啦',
                  'celebrate':'收工', 'settling':'稍歇', 'sleep-entry':'困了'}
        if self.mode == 'happy' and self.working and self.current == 'focus01_ack': return '收到'
        if self.mode in labels: return labels[self.mode]
        if self.working: return '专注'
        if self.pose in ('sleep','rest'): return '省电' if self.stage == 'depleted' else '小憩'
        if self.clock() < self.status_until: return self.status_text
        return ''

    def think(self):
        self.thought_phase += 1
        if not self.badge_text() and self.clock()-self.tap_time >= .3: self.thought.stop()
        self.update()

    def update_fade(self):
        if self.fade_clock.elapsed() >= self.fade_ms:
            self.fade.stop(); self.old_frame = None
        self.update()

    def badge_rect(self):
        x = min(self.width()-80, self.width()/2+self.canvas_size*.22)
        y = max(8,(self.height()-self.canvas_size)/2+12)
        return QRectF(x,y,74,26)

    def paintEvent(self, event):
        if self.old_frame is None or not self.animation:
            super().paintEvent(event)
        else:
            painter = QPainter(self)
            frame = self.visible_frame()
            painter.drawPixmap((self.width()-frame.width())//2,(self.height()-frame.height())//2,frame)
            painter.end()
        age = self.clock()-self.tap_time
        if 0 <= age < .3:
            tap = QPainter(self); tap.setRenderHint(QPainter.RenderHint.Antialiasing)
            tap.setPen(QPen(QColor(242,211,133,round(210*(1-age/.3))),1.6))
            radius = 5+age*48
            tap.drawEllipse(self.tap_point,radius,radius);tap.end()
        if self.coins.coins or self.coins.glints:
            effects=QPainter(self);self.coins.paint(effects);effects.end()
        label = self.badge_text()
        if not label: return
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        badge = self.badge_rect(); x = badge.x(); y = badge.y()
        phase = self.thought_phase*.12
        gold = QColor('#e2c47e'); quiet = self.pose in ('sleep','rest') and not self.working
        painter.setPen(QPen(QColor('#64777c' if quiet else '#8f7c4e'),1))
        painter.setBrush(QColor(24,34,40,237)); painter.drawRoundedRect(QRectF(x,y,74,26),11,11)
        painter.setFont(QFont('Microsoft YaHei',8)); painter.setPen(QColor('#c5d4d8' if quiet else '#f1dfaf'))
        painter.drawText(QRectF(x+25,y,45,26),Qt.AlignmentFlag.AlignCenter,label)
        painter.setPen(QPen(gold,1.4)); painter.setBrush(Qt.BrushStyle.NoBrush)
        if quiet:
            painter.setFont(QFont('Arial',10)); painter.drawText(QRectF(x+6,y+3,18,20),Qt.AlignmentFlag.AlignCenter,'z')
        elif self.mode == 'annoyed' or label == '别戳啦':
            painter.drawLine(int(x+9),int(y+7),int(x+14),int(y+11))
            painter.drawLine(int(x+20),int(y+7),int(x+16),int(y+11))
            painter.drawArc(QRectF(x+10,y+12,10,8),20*16,140*16)
        elif self.mode == 'celebrate' or (not self.working and label == '收工'):
            painter.drawLine(int(x+8),int(y+13),int(x+12),int(y+17))
            painter.drawLine(int(x+12),int(y+17),int(x+21),int(y+8))
        elif self.mode == 'happy' or label in ('你好','收到'):
            painter.drawEllipse(QRectF(x+8,y+8,13,11))
            painter.drawArc(QRectF(x+11,y+10,7,6),180*16,180*16)
        else:
            # A moving pen over a small ledger replaces the old ellipsis.
            painter.drawRoundedRect(QRectF(x+8,y+6,12,15),2,2)
            for row in range(3): painter.drawLine(int(x+11),int(y+10+row*4),int(x+17),int(y+10+row*4))
            shift = math.sin(phase)*2
            painter.drawLine(int(x+16+shift),int(y+12),int(x+22+shift),int(y+6))
        if self.working or label == '收工':
            for index in range(2):
                angle = phase*.6+index*math.pi
                sx = x+37+math.cos(angle)*42; sy = y+13+math.sin(angle)*19
                painter.setOpacity(.35+.35*(1+math.sin(phase+index))/2)
                painter.drawLine(int(sx-2),int(sy),int(sx+2),int(sy))
                painter.drawLine(int(sx),int(sy-2),int(sx),int(sy+2))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.request(point=event.position())
        elif event.button() == Qt.MouseButton.RightButton: self.context_requested.emit(event.globalPosition().toPoint())

    def mouseMoveEvent(self,event):
        over = self.working and self.badge_rect().contains(event.position())
        if over and not self.over_badge:
            self.task_hovered.emit(self.mapToGlobal(self.badge_rect().bottomRight().toPoint()))
        elif self.over_badge and not over:self.task_left.emit()
        self.over_badge = over
        super().mouseMoveEvent(event)

    def leaveEvent(self,event):
        if self.over_badge:self.task_left.emit()
        self.over_badge = False
        super().leaveEvent(event)

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            if self.working and hasattr(event,'pos') and self.badge_rect().contains(QPointF(event.pos())):
                self.task_hovered.emit(self.mapToGlobal(self.badge_rect().bottomRight().toPoint()))
            event.accept(); return True
        return super().event(event)

    def stop(self):
        self.coins.clear()
        self.stopped = True; self.epoch += 1
        self.pending = None; self.pending_emotion = None; self.work_event = None
        for timer in (self.small,self.boundary,self.fade,self.thought,self.nap): timer.stop()
        self.old_frame = None
        if self.animation: self.animation.stop()
