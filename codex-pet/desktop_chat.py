"""Open a fresh desktop conversation using the registered codex URI handler.

The installed desktop parser accepts mode=chat and mode=codex on /threads/new.
No keyboard events, foreground-window timing or previous conversation IDs.
The mode parameter is verified against desktop 26.1013.4894.0 source and may
need revalidation if the desktop changes its deep-link contract.
"""
import os
from PySide6.QtCore import QObject, Signal

NEW_CHAT_URLS = {
    'chatgpt': 'codex://threads/new?mode=chat',
    'codex': 'codex://threads/new?mode=codex',
}


class WindowsDesktop:
    def open_url(self, url):
        if url not in NEW_CHAT_URLS.values():
            raise ValueError('Unsupported desktop link')
        if os.name != 'nt':
            raise OSError('此入口目前只支持 Windows 桌面端。')
        # ShellExecute hands the complete URI to the registered desktop app.
        # Its own startup queue handles a closed/minimized/existing window.
        os.startfile(url)


class NativeChatBridge(QObject):
    status = Signal(str)
    finished = Signal(bool)
    failed = Signal(str)

    def __init__(self, parent=None, backend=None):
        super().__init__(parent)
        self.backend = backend or WindowsDesktop()

    def open(self, mode='chatgpt'):
        if mode not in NEW_CHAT_URLS:
            raise ValueError('Unknown desktop mode')
        try:
            self.backend.open_url(NEW_CHAT_URLS[mode])
        except OSError:
            text = '无法打开桌面端新对话，请检查 ChatGPT 桌面端安装及 codex 链接关联。'
            self.status.emit(text); self.failed.emit(text); self.finished.emit(False)
            return
        label = 'ChatGPT' if mode == 'chatgpt' else 'Codex'
        self.status.emit(f'已请求打开 {label} 新对话。')
        self.finished.emit(True)

    def cancel(self):
        # No delayed keyboard actions remain to cancel.
        pass
