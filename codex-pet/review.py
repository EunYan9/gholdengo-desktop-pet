"""Offline review window using exactly the desktop pet's animation player."""
import sys
from PySide6.QtCore import QSignalBlocker, Qt, QTimer
from PySide6.QtWidgets import (QApplication,QCheckBox,QHBoxLayout,QLabel,QPushButton,
                              QTextEdit,QVBoxLayout,QWidget)
from sprite_player import SpritePlayer


class Review(QWidget):
    def __init__(self,stage='chest'):
        super().__init__()
        self.setWindowTitle('索财灵 · 本地动作审片')
        self.resize(980,860)
        self.setStyleSheet('QWidget{background:#152127;color:#e5e4d9;font:14px "Microsoft YaHei";}'
            'QPushButton{background:#293940;border:1px solid #65716b;border-radius:7px;padding:9px 15px;}'
            'QPushButton:checked{border-color:#dbba68;background:#50452d;}'
            'QPushButton:disabled{color:#697b7d;background:#1e2b30;border-color:#35464a;}'
            'QTextEdit{color:#a3b4b6;border:1px solid #425050;border-radius:8px;}')
        layout=QVBoxLayout(self);layout.setContentsMargins(28,24,28,24);layout.setSpacing(14)
        eyebrow=QLabel('CODEX QUOTA COMPANION  /  EMOTIONS & WORK');eyebrow.setStyleSheet('color:#a3b4b6;font-size:11px;')
        layout.addWidget(eyebrow)
        title=QLabel('索财灵 · 情绪与工作陪伴');title.setStyleSheet('font-size:26px;font-weight:bold;')
        layout.addWidget(title)
        self.subtitle=QLabel();layout.addWidget(self.subtitle)
        row=QHBoxLayout();self.buttons=[]
        for name,value in [('宝箱常态','chest'),('徒步常态','roaming'),('低于 3% · 休眠','depleted'),('赛富豪','gholdengo')]:
            button=QPushButton(name);button.setCheckable(True);button.clicked.connect(lambda checked=False,s=value:self.select(s))
            self.buttons.append((button,value));row.addWidget(button)
        layout.addLayout(row)
        self.player=SpritePlayer(self);self.player.canvas_size=360;self.player.setMinimumHeight(365)
        layout.addWidget(self.player,1)
        self.track=QLabel();self.track.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.track.setStyleSheet('color:#d8be7c;font-size:16px;');layout.addWidget(self.track)
        tools=QHBoxLayout();self.action_buttons={}
        for label,kind in [('随机小动作','small'),('开心','happy'),('连点嫌弃','annoyed'),('困倦小憩','drowsy')]:
            button=QPushButton(label);button.clicked.connect(lambda checked=False,k=kind:self.player.request(k));tools.addWidget(button);self.action_buttons[kind]=button
        automatic=self.automatic=QCheckBox('自动小动作');automatic.setChecked(True);automatic.toggled.connect(self.set_auto);tools.addWidget(automatic)
        layout.addLayout(tools)
        work_tools=QHBoxLayout()
        self.working=QCheckBox('模拟 Codex 工作中');self.working.toggled.connect(self.player.set_working);work_tools.addWidget(self.working)
        demo=QPushButton('一键演示');demo.clicked.connect(self.start_demo);work_tools.addWidget(demo)
        for name,outcome in [('成功收工','completed'),('中断稍歇','interrupted')]:
            button=QPushButton(name);button.clicked.connect(lambda checked=False,o=outcome:self.finish_work(o));work_tools.addWidget(button)
        work_tools.addWidget(QLabel('取消工作勾选也会模拟成功结束'))
        layout.addLayout(work_tools)
        self.description=QLabel();self.description.setWordWrap(True);layout.addWidget(self.description)
        self.log=QTextEdit();self.log.setReadOnly(True);self.log.setFixedHeight(85);self.log.document().setMaximumBlockCount(60);layout.addWidget(self.log)
        credit=QLabel('索财灵：Mariokart07 / Sketchfab · 赛富豪：PokeStats / 朱紫原生动画   |   Pokémon / GAME FREAK')
        credit.setStyleSheet('font-size:10px;color:#899d9e;');layout.addWidget(credit)
        self.player.clip_changed.connect(self.record)
        self.demo_timer=QTimer(self);self.demo_timer.setSingleShot(True)
        self.demo_timer.timeout.connect(self.demo_next);self.demo_steps=[]
        self.select(stage)

    def start_demo(self):
        self.demo_timer.stop();self.finish_work('unknown')
        self.select('gholdengo')
        self.demo_steps=[(2600,lambda:self.player.request('happy')),
                         (1700,lambda:self.working.setChecked(True)),
                         (2700,lambda:self.player.request('happy')),
                         (4200,lambda:self.finish_work('completed')),
                         (2700,lambda:self.player.request('annoyed'))]
        self.demo_next()

    def demo_next(self):
        if not self.demo_steps:return
        delay,action=self.demo_steps.pop(0);action();self.demo_timer.start(delay)

    def record(self,clip):
        self.track.setText('朱紫原生 · 冲浪循环' if self.player.stage == 'gholdengo' else clip)
        self.log.append(self.player.stage+' → '+clip)

    def set_auto(self,value):
        self.player.automatic=value
        if not value:
            self.player.small.stop();self.player.boundary.stop();self.player.pending=None
        else:self.player.schedule_small()

    def finish_work(self,outcome):
        with QSignalBlocker(self.working):self.working.setChecked(False)
        self.player.set_working(False,outcome=outcome)

    def select(self,stage):
        for button,value in self.buttons:button.setChecked(value==stage)
        limited=stage=='gholdengo'
        self.action_buttons['small'].setEnabled(not limited)
        self.action_buttons['drowsy'].setEnabled(not limited)
        self.automatic.setEnabled(not limited)
        self.action_buttons['happy'].setText('点击爆金币' if limited else '开心')
        self.action_buttons['annoyed'].setText('连点反馈' if limited else '连点嫌弃')
        self.subtitle.setText('原生冲浪循环 · 点击爆金币 · 工作状态实时陪伴' if limited else '完整原动作 · 连续专注姿态 · 所有互动与桌宠一致')
        if stage=='depleted':
            text='低额度时长睡，点击会醒来张望后再睡。Codex 工作时抬盖专注陪伴；成功收工后收回注意力，再次入睡。'
        elif stage=='gholdengo':text='点击会弹出一小簇翻转金币，带细齿压边与金色微光，沿弧线散开后淡出。工作与连点仍有气泡回应，原生冲浪循环持续播放。可直接点角色，或点“点击爆金币”体验。'
        else:text='每次点击立即反馈；任意 1 秒内三次点击触发嫌弃，后续连点不反复重置。宝箱开工直接开盖进入专注，工作中单击从当前姿势抬盖回应“收到”，不先合箱；回应后接回专注。收工使用独立动作。'
        self.description.setText(text)
        self.player.set_stage(stage)

    def closeEvent(self,event):
        self.demo_timer.stop();self.player.stop();event.accept()


if __name__=='__main__':
    app=QApplication(sys.argv)
    view=Review('gholdengo' if '--gholdengo' in sys.argv else 'chest');view.show()
    if '--demo' in sys.argv:QTimer.singleShot(500,view.start_demo)
    sys.exit(app.exec())
