"""URI handoff and real menu wiring, without launching or typing into the app."""
import os
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from desktop_chat import NativeChatBridge, WindowsDesktop

app=QApplication.instance() or QApplication([])
class Desktop:
    def __init__(self):self.urls=[];self.error=False
    def open_url(self,url):
        if self.error:raise OSError('Missing URI association')
        self.urls.append(url)
backend=Desktop();bridge=NativeChatBridge(backend=backend)
results=[];errors=[];bridge.finished.connect(results.append);bridge.failed.connect(errors.append)
bridge.open('chatgpt');bridge.open('codex');bridge.open('chatgpt')
assert results==[True,True,True]
assert backend.urls==['codex://threads/new?mode=chat','codex://threads/new?mode=codex','codex://threads/new?mode=chat']
for url in backend.urls:
    parsed=urlsplit(url)
    assert parsed.scheme=='codex' and parsed.netloc=='threads' and parsed.path=='/new'
    assert set(parse_qs(parsed.query))=={'mode'}  # No old project/thread or prompt.
with patch('desktop_chat.os.startfile',create=True) as launch:
    native=NativeChatBridge()
    native.open('chatgpt');native.open('codex')
    assert [call.args[0] for call in launch.call_args_list]==backend.urls[:2]
try:bridge.open('invalid')
except ValueError:pass
else:raise AssertionError('Unknown mode accepted')
assert len(backend.urls)==3
backend.error=True;bridge.open('codex')
assert results[-1] is False and errors and len(backend.urls)==3

import main,desktop_chat
original=desktop_chat.NativeChatBridge
backend=Desktop()
desktop_chat.NativeChatBridge=lambda parent:original(parent,backend=backend)
try:
    pet=main.Pet(demo=True)
    actions={action.text():action for action in pet.menu.actions()}
    assert not any('预览' in text or '试听' in text for text,action in actions.items() if action.isEnabled())
    actions['与 ChatGPT 对话'].trigger();first=pet.desktop_bridge
    actions['与 Codex 对话'].trigger()
    assert pet.desktop_bridge is first
    assert backend.urls==['codex://threads/new?mode=chat','codex://threads/new?mode=codex']
    assert not hasattr(pet,'chatgpt')
    pet.shutdown()
finally:desktop_chat.NativeChatBridge=original
print('PASS: fresh Chat/Codex URI dispatch, no old project/thread/prompt, OS protocol handoff, missing-handler feedback, and direct menu routes; no real app launch or keyboard input')
