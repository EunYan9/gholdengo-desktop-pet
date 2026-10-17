"""Small quota card and a readable, bounded task hover panel."""
from datetime import datetime
from html import escape
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QScrollArea, QVBoxLayout, QWidget
from daily_budget import BEIJING,DAY

def tokens(value):
    return f'{value:,}' if isinstance(value,int) else '暂不可用'

class DailyCard(QFrame):
    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('dailyCard');self.setFixedWidth(110)
        self.setStyleSheet('QFrame#dailyCard{background:rgba(24,34,40,237);border:1px solid #736541;border-radius:13px;}'
            'QLabel{background:transparent;border:0;color:#e7dbb7;font:10px "Microsoft YaHei";}'
            'QProgressBar{background:#3a484b;border:0;border-radius:2px;}'
            'QProgressBar::chunk{background:#d9bb71;border-radius:2px;}'
            'QToolTip{background:#243139;color:#f2ecd8;border:1px solid #746642;padding:8px;font:12px "Microsoft YaHei";}')
        layout=QVBoxLayout(self);layout.setContentsMargins(10,10,10,10);layout.setSpacing(4)
        title=QLabel('今日建议');title.setStyleSheet('color:#b8b5a3;font-size:11px;');layout.addWidget(title)
        self.amount=QLabel('—');self.amount.setStyleSheet('color:#eed696;font:bold 21px "Microsoft YaHei";');layout.addWidget(self.amount)
        self.caption=QLabel('等待周额度');layout.addWidget(self.caption)
        self.progress=QProgressBar();self.progress.setRange(0,1000);self.progress.setTextVisible(False);self.progress.setFixedHeight(4);layout.addWidget(self.progress)
        self.detail=QLabel('已用 — / —');layout.addWidget(self.detail)
        self.foot=QLabel('02:00 换日');self.foot.setStyleSheet('color:#9ba9aa;font-size:10px;');layout.addWidget(self.foot)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(),self.sizePolicy().Policy.Fixed)

    def display(self,data,offline=False):
        if data['status']!='ready':
            self.amount.setText('—');self.caption.setText('等待换日同步' if data['status']=='stale' else '等待周额度')
            self.detail.setText('已用 — / —');self.progress.setValue(0)
            self.setToolTip('北京时间每日 02:00 换日。收到有效周额度及重置时间后，计算当日建议。');return
        over=data['over']>0
        reached=data['ratio']>=1
        lower=data.get('coverage')=='lower_bound'
        self.amount.setText(f"{data['over'] if over else data['left']:.1f}%")
        self.amount.setStyleSheet(f'color:{"#eda38c" if reached else "#eed696"};font:bold 21px "Microsoft YaHei";')
        self.caption.setText(('至少超出 · 周额度' if lower else '已超建议 · 周额度') if over else
                             ('今日建议已用完' if reached else ('最多可用 · 周额度' if lower else '还可用 · 周额度')))
        self.progress.setValue(round(data['ratio']*1000))
        mark='≥' if data.get('coverage')=='lower_bound' else '≈'
        self.detail.setText(f"已用 {mark}{data['used']:.1f}%\n建议 {data['limit']:.1f}%")
        if lower and data['used']==0:
            self.amount.setText('—');self.caption.setText('今日消耗待恢复')
            self.detail.setText(f"缺少 02:00 基准\n暂估建议 {data['limit']:.1f}%")
        self.foot.setText('离线 · 保留读数' if offline else ('02:00 起 · 有缺口' if data.get('coverage')=='lower_bound' else '02:00 起统计'))
        began=datetime.fromtimestamp(data['began_at'],BEIJING).strftime('%m-%d %H:%M')
        reset=datetime.fromtimestamp(data['reset'],BEIJING).strftime('%m-%d %H:%M')
        start=datetime.fromtimestamp(data['day'],BEIJING).strftime('%m-%d %H:%M')
        end=datetime.fromtimestamp(data['day']+DAY,BEIJING).strftime('%m-%d %H:%M')
        text=(f'<b>每日建议 · 北京时间 02:00 换日</b><br>统计周期：{start} 至 {end}<br>恢复的基准记录：{began}<br>'
              f"本轮起点 {data['baseline']:g}% ÷ 剩余 {data['days']} 天 = 本轮建议 {data.get('segment_limit',data['limit']):.2f}%<br>"
              f"已观测消耗 {data['used']:.2f} 个周额度百分点；还可用 {data['left']:.2f}%<br>"
              f'本周重置：{reset}<br>当天建议固定，次日按剩余周额度重新分配。<br>'
              '这是使用建议，达到后仍可继续使用；80% 和 100% 各提醒一次。<br>'
              '统计以服务端百分比变化估算，每 3 分钟同步，不能换算为固定 token 数。')
        if data.get('coverage')=='lower_bound':text+='<br>≥ 表示已确认的最低消耗，缺失区间没有当作 0。'
        elif data.get('coverage')=='estimated':text+='<br>以 02:00 之前最近一次有效额度为基准，读数之间的消耗时间存在采样误差。'
        if data.get('gap_before_reset'):text+='<br>本日凌晨发生周重置；02:00 至周重置前缺少旧周期记录，当前建议按新周期计算。'
        if data.get('cycle_count',1)>1:text+='<br>本日跨周重置，已将已记录的各段消耗及建议合计。'
        if data['save_failed']:text+='<br>本次记录未能保存，重启后可能丢失。'
        if offline:text+='<br>额度同步暂不可用，当前数据尚未更新。'
        self.setToolTip(text)

class TaskPopup(QFrame):
    entered=Signal();left=Signal()
    def __init__(self,parent=None):
        super().__init__(parent,Qt.WindowType.ToolTip|Qt.WindowType.FramelessWindowHint)
        self.setObjectName('taskPopup');self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(360);self.anchor=QPoint();self.payload=None
        self.setStyleSheet('QFrame#taskPopup{background:#202e35;border:1px solid #978252;border-radius:12px;}'
            'QLabel{color:#ece6d0;background:transparent;border:0;font:12px "Microsoft YaHei";}'
            'QScrollArea,QScrollArea>QWidget>QWidget{background:transparent;border:0;}'
            'QScrollBar:vertical{width:6px;background:#293b41;}QScrollBar::handle:vertical{background:#7e775f;min-height:20px;border-radius:3px;}')
        layout=QVBoxLayout(self);layout.setContentsMargins(14,12,14,12);layout.setSpacing(8)
        self.title=QLabel();layout.addWidget(self.title)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content=QLabel();self.content.setTextFormat(Qt.TextFormat.RichText);self.content.setWordWrap(True)
        self.content.setAlignment(Qt.AlignmentFlag.AlignTop);self.content.setMargin(2)
        self.scroll.setWidget(self.content);layout.addWidget(self.scroll)
        foot=QLabel('本轮 / 会话累计 · token 含缓存输入\n调用结束后更新；不等于订阅额度扣费。');foot.setStyleSheet('color:#a6b6b7;font-size:10px;')
        layout.addWidget(foot)

    def set_tasks(self,tasks,state='working'):
        payload=(tasks,state)
        if payload==self.payload:return
        self.payload=payload
        self.title.setText(f'正在运行 · {len(tasks)} 个任务' if tasks else ('当前没有运行任务' if state=='idle' else '任务详情暂不可用'))
        chunks=[]
        for task in tasks:
            title=escape(task['title']);identifier=escape(task['id'][:8])
            line=(f'<b>{title}</b><br><span style="color:#aebfc0">本轮 </span>{tokens(task.get("turn_tokens"))}'
                  f'<span style="color:#aebfc0">　累计 </span>{tokens(task.get("total_tokens"))}')
            if task.get('input_tokens') is not None:
                line+=(f'<br><span style="color:#aebfc0;font-size:11px">会话输入 {tokens(task["input_tokens"])}'
                       f'（缓存 {tokens(task.get("cached_input_tokens"))}）<br>会话输出 {tokens(task.get("output_tokens"))} · {identifier}</span>')
            else:line+=f'<br><span style="color:#aebfc0">{identifier} · {"明细暂不可用" if task.get("total_tokens") is not None else "等待计数"}</span>'
            chunks.append(line)
        self.content.setText('<br><br>'.join(chunks) or '没有可显示的活动任务。')
        self.content.setFixedWidth(310)
        height=self.content.sizeHint().height()+8;self.content.setMinimumHeight(height)
        self.scroll.setFixedHeight(min(300,max(60,height)))
        self.adjustSize()
        if self.isVisible():self.place()

    def place(self):
        screen=QGuiApplication.screenAt(self.anchor) or QGuiApplication.primaryScreen()
        area=screen.availableGeometry()
        x=min(max(area.left()+6,self.anchor.x()+8),max(area.left()+6,area.right()-self.width()-6))
        y=min(max(area.top()+6,self.anchor.y()+8),max(area.top()+6,area.bottom()-self.height()-6))
        self.move(x,y)

    def show_at(self,point):
        self.anchor=point;self.place();self.show()

    def enterEvent(self,event):self.entered.emit();super().enterEvent(event)
    def leaveEvent(self,event):self.left.emit();super().leaveEvent(event)
