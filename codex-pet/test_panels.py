"""Qt integration: live task replacement, hover targeting and budget states."""
import os,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QEventLoop,QPoint,QTimer,Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
import main
from main import Pet,ActivityWorker

app=QApplication.instance() or QApplication([])
def run(ms):
    loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()

snapshots=[{'state':'working','count':1,'active_ids':['abc'],'outcomes':{}},
           {'state':'working','count':1,'active_ids':['def'],'outcomes':{'abc':'completed'}},
           {'state':'working','count':1,'active_ids':['def'],'outcomes':{'abc':'completed'}},
           {'state':'idle','count':0,'active_ids':[],'outcomes':{'abc':'completed','def':'completed'}}]
class Stop:
    index=0
    def is_set(self):return self.index>=len(snapshots)
    def wait(self,_):self.index+=1
worker=ActivityWorker();worker.stop=Stop()
class Details:
    def read(self,ids):return [{'id':id,'title':id,'total_tokens':100+worker.stop.index} for id in ids]
worker.details=Details();events=[];worker.updated.connect(events.append)
original=main.read_activity;main.read_activity=lambda **kw:snapshots[worker.stop.index]
try:worker.run()
finally:main.read_activity=original
assert len(events)==4 and events[1]['tasks'][0]['id']=='def'
assert events[2]['tasks'][0]['total_tokens']==102 and events[-1]['outcome']=='completed'

pet=Pet(demo=True,stage='chest');pet.show();run(40)
pet.tasks_popup.set_tasks([{'id':'rounding','title':'圆角检查'}])
pet.tasks_popup.show_at(QPoint(200,200));run(10)
image=pet.tasks_popup.grab().toImage()
for x,y in ((0,0),(image.width()-1,0),(0,image.height()-1),(image.width()-1,image.height()-1)):
    assert image.pixelColor(x,y).alpha()==0
for x,y in ((5,25),(image.width()-6,25),(image.width()//2,5),(image.width()//2,image.height()-5)):
    assert image.pixelColor(x,y).getRgb()==(32,46,53,255),image.pixelColor(x,y).getRgb()
pet.tasks_popup.hide()
now=time.time()
def quota(remaining,when):
    return {'retrieved_at':when,'remaining':50,'blocked':False,'windows':[
        {'label':'5小时额度','remaining':50,'minutes':300,'resets_at':now+1000},
        {'label':'周额度','remaining':remaining,'minutes':10080,'resets_at':now+6.5*86400}]}
pet.update_quota(quota(70,now));header=pet.header.text();limit=pet.budget.current['limit']
if pet.budget.view()['coverage']=='lower_bound':
    assert '待恢复' in pet.daily.caption.text() and '已用' not in pet.daily.detail.text()
notices=[];pet.tray.showMessage=lambda *args:notices.append(args)
pet.update_quota(quota(70-limit*.85,now+.01))
assert len(notices)==1 and pet.budget.current['limit']==limit
pet.update_quota(quota(70-limit*1.1,now+.02))
assert len(notices)==2 and any(text in pet.daily.caption.text() for text in ('已超','超出'))
pet.update_quota(quota(70-limit*1.2,now+.03));assert len(notices)==2
pet.error('测试离线');assert '离线' in pet.daily.foot.text()
missing=quota(70,now+.04);missing['windows']=missing['windows'][:1]
pet.update_quota(missing);assert '离线' in pet.daily.foot.text()
pet.update_activity({'state':'working','count':1,'tasks':[{'id':'abc','title':'<script>标题</script>','total_tokens':120,'turn_tokens':20}]})
assert pet.tasks_popup.title.text()=='Codex · 正在运行 1 个任务'
def move(point):
    event=QMouseEvent(QMouseEvent.Type.MouseMove,point.toPointF(),pet.view.mapToGlobal(point).toPointF(),Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier)
    app.sendEvent(pet.view,event)
move(QPoint(20,150));assert not pet.tasks_popup.isVisible()
move(pet.view.badge_rect().center().toPoint());assert pet.tasks_popup.isVisible()
assert '&lt;script&gt;' in pet.tasks_popup.content.text()
move(QPoint(20,150));run(300);assert not pet.tasks_popup.isVisible()
pet.update_activity({'state':'idle','count':0,'tasks':[]})
assert not pet.tasks_popup.isVisible()
old=pet.view.mapToGlobal(QPoint()).x()
pet.daily_toggle.setChecked(False);assert pet.view.mapToGlobal(QPoint()).x()==old and pet.width()==310
pet.daily_toggle.setChecked(True);assert pet.view.mapToGlobal(QPoint()).x()==old and pet.width()==428
pet.update_quota(quota(70-limit*1.2,now+.05))
assert '5小时' in pet.header.text() and '周' in pet.header.text()
pet.shutdown();pet.close()
print('PASS: task replacement and token updates with same count; fixed budget and reminders; offline state; badge-only hover; escaped titles; close on leave; unchanged header; stable pet position')
