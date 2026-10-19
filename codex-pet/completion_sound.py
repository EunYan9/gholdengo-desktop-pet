"""Observed-turn completion tracking and a quiet, optional local chime."""
from collections import deque
import time


class CompletionTracker:
    def __init__(self):
        self.pending = {}
        self.seen = set()
        self.order = deque()

    def observe(self, snapshot):
        completed = []
        for record in snapshot.get('finished_turns', []):
            turn = record.get('turn_id')
            if self.pending.get(turn) != record.get('thread_id'):
                continue
            if record.get('status') not in ('completed', 'failed', 'interrupted'):
                continue
            self.pending.pop(turn, None)
            if turn in self.seen:
                continue
            self.seen.add(turn); self.order.append(turn)
            if record['status'] == 'completed':
                completed.append(turn)
        while len(self.order) > 2048:
            self.seen.discard(self.order.popleft())
        for thread, turn in snapshot.get('active_turns', {}).items():
            if turn and turn not in self.seen:
                self.pending[turn] = thread
        while len(self.pending) > 512:
            self.pending.pop(next(iter(self.pending)))
        return completed


class CompletionSound:
    def __init__(self, parent, source, clock=time.monotonic):
        self.parent = parent
        self.source = source
        self.clock = clock
        self.enabled = False
        self.last_played = float('-inf')
        self.effect = None

    def play(self, preview=False):
        now = self.clock()
        if (not self.enabled and not preview) or now-self.last_played < 1.2:
            return False
        if self.effect is None:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect
            self.effect = QSoundEffect(self.parent)
            self.effect.setVolume(.32)
            self.effect.setLoopCount(1)
            self.effect.setSource(QUrl.fromLocalFile(str(self.source)))
        self.last_played = now
        self.effect.play()
        return True

    def stop(self):
        if self.effect is not None:
            self.effect.stop()
