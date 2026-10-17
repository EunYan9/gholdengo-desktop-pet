"""Render selected original tracks using the official Sketchfab screenshot API."""
import base64
import json
from pathlib import Path
import re
import sys

from PySide6.QtCore import QObject, QTimer, QUrl, Slot
from PySide6.QtWidgets import QApplication
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

ROOT=Path(__file__).resolve().parent
model=sys.argv[1] if len(sys.argv)>1 else 'chest'
if model not in ('chest','roaming','gholdengo'):raise SystemExit(2)
app=QApplication(sys.argv)
view=QWebEngineView()
view.resize(512,512)
settings=view.settings()
for option in ['LocalContentCanAccessRemoteUrls','LocalContentCanAccessFileUrls','JavascriptEnabled']:
    settings.setAttribute(getattr(QWebEngineSettings.WebAttribute,option),True)


class Exporter(QObject):
    @Slot(str,str,int,str,result=bool)
    def frame(self,stage,clip,index,data):
        if stage!=model or not re.fullmatch(r'[a-z0-9_]+',clip) or not 0<=index<600:return False
        if not data.startswith('data:image/png;base64,'):return False
        folder=ROOT/'rendered'/stage/clip
        folder.mkdir(parents=True,exist_ok=True)
        (folder/f'{index:04}.png').write_bytes(base64.b64decode(data.split(',',1)[1],validate=True))
        return True

    @Slot(str)
    def progress(self,message):print(message,flush=True)

    @Slot(str,str)
    def catalog(self,stage,data):
        if stage!=model:return
        tracks=json.loads(data)
        (ROOT/(stage+'-animations.json')).write_text(json.dumps(tracks,indent=2),encoding='utf-8')
        print('CATALOG',stage,len(tracks),'original tracks',flush=True)

    @Slot(str,str)
    def inspection(self,stage,data):
        if stage!=model:return
        (ROOT/(stage+'-inspection.json')).write_text(data,encoding='utf-8')
        print('INSPECTED',stage,flush=True)

    @Slot(str,str,float,int)
    def clipDone(self,stage,clip,duration,count):
        folder=ROOT/'rendered'/stage/clip
        (folder/'metadata.json').write_text(json.dumps({'duration':duration,'frames':count,'fps':30}),encoding='utf-8')
        print('SAVED',stage,clip,flush=True)

    @Slot(str)
    def done(self,stage):print('EXPORT COMPLETE',stage,flush=True);app.quit()

    @Slot(str)
    def failure(self,message):print('EXPORT FAILED',message,flush=True);app.exit(1)

channel=QWebChannel()
exporter=Exporter()
channel.registerObject('exporter',exporter)
view.page().setWebChannel(channel)
url=QUrl.fromLocalFile(str(ROOT/'export.html'))
url.setQuery('model='+model+('&clips='+sys.argv[2] if len(sys.argv)>2 else ''))
view.setUrl(url)
view.show()
QTimer.singleShot(600000,lambda:app.exit(3))
sys.exit(app.exec())
