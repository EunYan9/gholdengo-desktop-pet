from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import threading
import time

from PySide6.QtCore import QObject, QLockFile, QPoint, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMenu, QSystemTrayIcon, QVBoxLayout, QWidget
from codex_usage import QuotaError, fetch_limits
from sprite_player import SpritePlayer
from codex_activity import read_activity
from daily_budget import DailyBudget, day_start
from task_usage import TaskUsageReader
from quota_history import QuotaHistory
from companion_panels import DailyCard, TaskPopup
from completion_sound import CompletionTracker, CompletionSound

ROOT = Path(__file__).resolve().parent


def quota_stage(remaining: float, blocked: bool = False) -> str:
    if blocked or remaining < 3:
        return 'depleted'
    if remaining < 20:
        return 'roaming'
    if remaining < 80:
        return 'chest'
    return 'gholdengo'


class QuotaWorker(QObject):
    updated = Signal(object)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.stop = threading.Event()
        self.refresh = threading.Event()
        self.thread = threading.Thread(target=self.run, name='codex-quota')
        self.history = QuotaHistory()

    def run(self):
        while not self.stop.is_set():
            self.refresh.clear()
            try:
                snapshot = fetch_limits(self.stop)
                if not self.stop.is_set():
                    try:snapshot['quota_history'] = self.history.read(day_start(snapshot['retrieved_at']),snapshot['retrieved_at'])
                    except (OSError,ValueError,TypeError):snapshot['quota_history'] = []
                if not self.stop.is_set():
                    self.updated.emit(snapshot)
            except QuotaError as exc:
                if not self.stop.is_set():
                    self.failed.emit(str(exc))
            except Exception:
                if not self.stop.is_set():
                    self.failed.emit('同步失败；保留上次读数。')
            self.refresh.wait(180)

    def close(self):
        self.stop.set()
        self.refresh.set()
        if self.thread.is_alive():
            self.thread.join()


class ActivityWorker(QObject):
    updated = Signal(object)

    def __init__(self):
        super().__init__()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name='codex-activity')
        self.details = TaskUsageReader()

    def run(self):
        previous = None
        watching = set()
        completions = CompletionTracker()
        while not self.stop.is_set():
            snapshot = read_activity(watching=watching, watched_turns=completions.pending)
            visible = {'state':snapshot['state'], 'count':snapshot['count'],
                       'tasks':self.details.read(snapshot['active_ids']),
                       'completed_turns':completions.observe(snapshot)}
            if previous and previous['state'] == 'working' and visible['state'] == 'idle':
                outcomes = snapshot['outcomes']
                statuses = [outcomes.get(thread_id, 'unknown') for thread_id in watching]
                visible['outcome'] = ('completed' if statuses and all(status == 'completed' for status in statuses)
                                      else ('failed' if 'failed' in statuses else
                                            ('interrupted' if 'interrupted' in statuses else 'unknown')))
            watching.update(snapshot['active_ids'])
            if visible['state'] != 'working': watching.clear()
            if visible['completed_turns'] or previous is None or any(visible[key] != previous[key] for key in ('state','count','tasks')):
                self.updated.emit(visible)
            previous = visible
            self.stop.wait(1)

    def close(self):
        self.stop.set()
        if self.thread.is_alive(): self.thread.join()


class Header(QLabel):
    def __init__(self, pet):
        super().__init__('Codex · 正在同步', pet)
        self.pet = pet
        self.origin = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(32)
        self.setObjectName('quotaHeader')
        self.setStyleSheet('QLabel#quotaHeader{background:rgba(22,29,34,225);color:#e9e5ce;'
                           'border:1px solid #746642;border-radius:12px;'
                           'font:12px "Microsoft YaHei";padding:0 8px;}'
                           'QToolTip{background-color:#243139;color:#f2ecd8;'
                           'border:1px solid #746642;padding:6px;'
                           'font:12px "Microsoft YaHei";}')
        self.setText(self.text())

    def setText(self, text):
        super().setText(text)
        self.ensurePolished()
        self.setFixedWidth(min(286, max(150, self.fontMetrics().horizontalAdvance(text) + 22)))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.globalPosition().toPoint() - self.pet.pos()
        elif event.button() == Qt.MouseButton.RightButton:
            self.pet.menu.exec(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if self.origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.pet.move(event.globalPosition().toPoint() - self.origin)

    def mouseReleaseEvent(self, event):
        self.origin = None
        self.pet.save_position()


class Pet(QWidget):
    def __init__(self, demo=False, stage=None):
        super().__init__()
        self.setWindowTitle('Codex 索财灵')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(428, 310)
        self.closed = False
        self.forced_stage = stage
        self.stage = 'gholdengo'
        self.last_snapshot = None
        self.quota_offline = False
        self.sound = CompletionSound(self, ROOT/'sounds'/'task-complete.wav')
        self.budget = DailyBudget(None if demo else ROOT/'daily_budget.json')
        self.daily = DailyCard(self)
        self.tasks_popup = TaskPopup(self)
        self.task_hide = QTimer(self);self.task_hide.setSingleShot(True);self.task_hide.setInterval(220)
        self.task_hide.timeout.connect(self.tasks_popup.hide)
        self.tasks_popup.entered.connect(self.task_hide.stop)
        self.tasks_popup.left.connect(self.task_hide.start)
        self.header = Header(self)
        self.view = SpritePlayer(self)
        self.view.context_requested.connect(lambda point:self.menu.exec(point))
        self.view.task_hovered.connect(self.show_tasks)
        self.view.task_left.connect(self.task_hide.start)
        outer = QHBoxLayout(self);outer.setContentsMargins(4,0,4,0);outer.setSpacing(8)
        outer.addWidget(self.daily,0,Qt.AlignmentFlag.AlignVCenter)
        layout = QVBoxLayout();outer.addLayout(layout,1)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.addWidget(self.header, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.view, 1)
        self.menu = QMenu(self)
        self.activity_status = self.menu.addAction('Codex · 状态同步中')
        self.activity_status.setEnabled(False)
        self.menu.addSeparator()
        self.menu.addAction('与 ChatGPT 对话', self.open_chatgpt)
        self.menu.addAction('与 Codex 对话', self.open_codex)
        self.sound_toggle = self.menu.addAction('任务完成音效')
        self.sound_toggle.setCheckable(True); self.sound_toggle.setChecked(False)
        self.sound_toggle.toggled.connect(self.toggle_sound)
        self.menu.addSeparator()
        self.menu.addAction('立即同步额度', self.request_refresh)
        self.daily_toggle = self.menu.addAction('显示每日建议')
        self.daily_toggle.setCheckable(True);self.daily_toggle.setChecked(True)
        self.daily_toggle.toggled.connect(self.toggle_daily)
        self.menu.addSeparator()
        self.menu.addAction('退出灵宠', QApplication.instance().quit)
        icon = QIcon()
        pixmap = QPixmap(str(ROOT / 'gholdengo.webp'))
        if not pixmap.isNull():
            icon = QIcon(pixmap)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip('Codex 索财灵 · 拖动额度条移动，右键退出')
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.tray_clicked)
        self.tray.show()
        self.view.set_stage(stage or self.stage)
        self.move(120, 160)
        try:
            position = json.loads((ROOT / 'position.json').read_text(encoding='utf-8'))
            if position.get('daily_visible') is False:self.daily_toggle.setChecked(False)
            if position.get('completion_sound') is True:self.sound_toggle.setChecked(True)
            point = QPoint(int(position['x'])-(118 if position.get('layout_version')!=2 else 0), int(position['y']))
            if any(screen.availableGeometry().intersects(self.geometry().translated(point-self.pos()))
                   for screen in QApplication.screens()):
                self.move(point)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        self.worker = QuotaWorker()
        self.worker.updated.connect(self.update_quota)
        self.worker.failed.connect(self.error)
        self.activity = ActivityWorker()
        self.activity.updated.connect(self.update_activity)
        self.day_timer = QTimer(self);self.day_timer.setInterval(15000)
        self.day_timer.timeout.connect(self.check_day);self.day_timer.start()
        self.requested_day = day_start(time.time());self.requested_week = None
        self.daily.display(self.budget.view())
        if demo:
            self.header.setText('预览模式 · 未查询额度')
            self.activity_status.setText('Codex · 预览模式')
        else:
            self.worker.thread.start()
            self.activity.thread.start()

    def update_activity(self, snapshot):
        if snapshot.get('completed_turns'):
            # Exact-turn completions are already deduplicated by the tracker.
            # The worker Event coalesces a batch and queues a refresh even if
            # a quota read is still running; this is independent of sound.
            self.request_refresh()
            self.sound.play()
        self.tasks_popup.set_tasks(snapshot.get('tasks',[]),snapshot['state'])
        if snapshot['state']!='working':self.tasks_popup.hide();self.task_hide.stop()
        self.view.set_working(snapshot['state'] == 'working', outcome=snapshot.get('outcome', 'unknown'))
        if snapshot['state'] == 'working':
            self.activity_status.setText(f"Codex · 工作中（{snapshot['count']} 个会话）")
        elif snapshot['state'] == 'unknown':
            self.activity_status.setText('Codex · 工作状态暂不可用')
        else:
            self.activity_status.setText('Codex · 当前空闲')

    def show_tasks(self,point):
        self.task_hide.stop();self.tasks_popup.show_at(point)

    def toggle_sound(self, enabled):
        self.sound.enabled = enabled
        if not enabled:self.sound.stop()
        self.save_position()

    def toggle_daily(self,visible):
        old_x=self.view.mapToGlobal(QPoint()).x()
        self.daily.setVisible(visible);self.setFixedWidth(428 if visible else 310)
        self.layout().setSpacing(8 if visible else 0);self.layout().activate()
        self.move(self.x()+old_x-self.view.mapToGlobal(QPoint()).x(),self.y())

    def check_day(self):
        now=time.time();day=day_start(now)
        reset=self.budget.current['reset'] if self.budget.current else None
        if day!=self.requested_day or (reset and now>=reset and self.requested_week!=reset):
            self.requested_day=day;self.requested_week=reset;self.worker.refresh.set()
        self.daily.display(self.budget.view(now),self.quota_offline)

    def set_stage(self, value):
        self.view.set_stage(value)

    def force(self, value):
        self.forced_stage = value
        self.set_stage(value or self.stage)
        if self.last_snapshot:
            self.show_text(self.last_snapshot)

    def show_text(self, snapshot):
        parts = [f"{w['label'].replace('额度', '')} {w['remaining']:g}%" for w in snapshot['windows']]
        self.header.setText(('预览 · ' if self.forced_stage else '') + ' │ '.join(parts))
        detail = ['Codex 剩余额度（非 token 个数）']
        for window in snapshot['windows']:
            reset = window['resets_at']
            when = datetime.fromtimestamp(reset).strftime('%m-%d %H:%M') if reset else '未知'
            detail.append(f"{window['label']}剩余 {window['remaining']:g}% · 重置 {when}")
        detail.append('上次同步 ' + datetime.fromtimestamp(snapshot['retrieved_at']).strftime('%H:%M:%S'))
        detail.append('每 3 分钟同步；拖动此条移动；右键查看菜单')
        if snapshot['blocked']:
            detail.append('服务端目前不允许普通包含额度使用。')
        self.header.setToolTip('\n'.join(detail))
        self.tray.setToolTip('Codex · ' + ' | '.join(parts))

    def update_quota(self, snapshot):
        self.quota_offline = False
        alerts = self.budget.observe(snapshot,snapshot.get('quota_history',[]))
        if self.budget.current and self.budget.current['observed_at']!=snapshot['retrieved_at']:
            self.quota_offline = True
        data = self.budget.view();self.daily.display(data,self.quota_offline)
        for level in (alerts if data['status']=='ready' else []):
            text = (f"今日建议已用约 {data['used']/data['limit']*100:.0f}%，累计消耗约 {data['used']:.1f}% 周额度。"
                    '可以稍作休息；继续使用不受影响。')
            self.tray.showMessage('索财灵 · 今日用量提醒',text,QSystemTrayIcon.MessageIcon.Information,8000)
        self.last_snapshot = snapshot
        next_stage = quota_stage(snapshot['remaining'], snapshot['blocked'])
        changed = next_stage != self.stage
        self.stage = next_stage
        self.show_text(snapshot)
        if changed and not self.forced_stage:
            self.set_stage(next_stage)

    def error(self, text):
        self.quota_offline = True;self.daily.display(self.budget.view(),True)
        if self.last_snapshot:
            self.show_text(self.last_snapshot)
            self.header.setText(self.header.text() + ' · 离线')
            self.header.setToolTip(self.header.toolTip() + '\n' + text)
        else:
            self.header.setText('Codex · 尚未读到额度')
            self.header.setToolTip(text)

    def request_refresh(self):
        self.worker.refresh.set()

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.setVisible(not self.isVisible())

    def open_chatgpt(self):
        self.open_desktop('chatgpt')

    def open_codex(self):
        self.open_desktop('codex')

    def open_desktop(self, mode):
        from desktop_chat import NativeChatBridge
        if not hasattr(self,'desktop_bridge'):
            self.desktop_bridge=NativeChatBridge(self)
            self.desktop_bridge.failed.connect(lambda text:self.tray.showMessage(
                '赛富豪 · 打开对话', text, QSystemTrayIcon.MessageIcon.Warning, 6000))
        self.desktop_bridge.open(mode)

    def save_position(self):
        temporary = ROOT / 'position.json.tmp'
        try:
            temporary.write_text(json.dumps({'x':self.x(), 'y':self.y(),'layout_version':2,
                                              'daily_visible':self.daily_toggle.isChecked(),
                                              'completion_sound':self.sound_toggle.isChecked()}), encoding='utf-8')
            temporary.replace(ROOT / 'position.json')
        except OSError:
            pass

    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self.day_timer.stop();self.task_hide.stop();self.tasks_popup.close()
        self.save_position()
        self.worker.close()
        self.activity.close()
        self.tray.hide()
        self.view.stop()
        self.sound.stop()
        if hasattr(self,'desktop_bridge'):self.desktop_bridge.cancel()

    def closeEvent(self, event):
        QApplication.instance().quit()
        event.accept()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--stage', choices=['chest','roaming','depleted','gholdengo'])
    parser.add_argument('--quit-after', type=int, default=0)
    parser.add_argument('--chatgpt', action='store_true', help='Open desktop Chat mode after startup')
    args = parser.parse_args()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    lock = QLockFile(str(ROOT / '.instance.lock'))
    if not lock.tryLock(0):
        return 0
    pet = Pet(args.demo, args.stage)
    app.aboutToQuit.connect(pet.shutdown)
    pet.show()
    if args.chatgpt:QTimer.singleShot(200,pet.open_chatgpt)
    if args.quit_after:
        QTimer.singleShot(args.quit_after * 1000, app.quit)
    result = app.exec()
    lock.unlock()
    return result


if __name__ == '__main__':
    raise SystemExit(main())
