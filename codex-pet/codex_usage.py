"""Read account quota through the installed Codex app-server; never starts a turn."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass


class QuotaError(Exception):
    pass


def find_codex() -> str:
    found = shutil.which('codex.exe' if os.name == 'nt' else 'codex')
    if found:
        return found
    base = Path(os.environ.get('LOCALAPPDATA', '')) / 'OpenAI' / 'Codex' / 'bin'
    candidates = list(base.glob('*/codex.exe'))
    if candidates:
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
    raise QuotaError('未找到 Codex，请先安装并登录 Codex 桌面应用。')


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


@dataclass(frozen=True)
class Window:
    label: str
    remaining: float
    minutes: float | None
    resets_at: float | None


def parse_limits(payload: dict) -> dict:
    buckets = payload.get('rateLimitsByLimitId')
    bucket = buckets.get('codex') if isinstance(buckets, dict) else None
    # Do not silently select a different model's quota bucket.
    if not isinstance(bucket, dict):
        bucket = payload.get('rateLimits')
    if not isinstance(bucket, dict):
        raise QuotaError('Codex 尚未返回可用额度。')
    windows = []
    for key in ('primary', 'secondary'):
        raw = bucket.get(key)
        if not isinstance(raw, dict):
            continue
        used = number(raw.get('usedPercent'))
        if used is None:
            continue
        minutes = number(raw.get('windowDurationMins'))
        if minutes == 10080:
            label = '周额度'
        elif minutes and minutes % 60 == 0:
            label = f'{minutes / 60:g}小时额度'
        elif minutes:
            label = f'{minutes:g}分钟额度'
        else:
            label = '额度窗口'
        windows.append(Window(label, max(0, min(100, 100 - used)), minutes,
                              number(raw.get('resetsAt'))).__dict__)
    if not windows:
        raise QuotaError('额度数据暂缺；保留上次读数。')
    blocked = payload.get('ordinaryUsageAllowed') is False
    return {'provider': 'Codex', 'windows': windows,
            'remaining': min(w['remaining'] for w in windows),
            'ordinary_usage_allowed': payload.get('ordinaryUsageAllowed'),
            'blocked': blocked, 'retrieved_at': time.time(),
            'credits': bucket.get('credits') if isinstance(bucket.get('credits'), dict) else None}


def fetch_limits(stop: threading.Event | None = None, timeout: float = 25) -> dict:
    """Own a short-lived stdio server. Its auth stays managed by Codex itself."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    process = subprocess.Popen(
        [find_codex(), 'app-server', '--stdio'], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        encoding='utf-8', creationflags=flags,
    )
    messages = queue.Queue()

    def reader():
        try:
            for line in process.stdout:
                try:
                    messages.put(json.loads(line))
                except (ValueError, TypeError):
                    continue
        finally:
            messages.put(None)

    thread = threading.Thread(target=reader, daemon=True, name='quota-stdio')
    thread.start()
    deadline = time.monotonic() + timeout

    def send(value):
        process.stdin.write(json.dumps(value) + '\n')
        process.stdin.flush()

    def receive(request_id):
        while time.monotonic() < deadline:
            if stop is not None and stop.is_set():
                raise QuotaError('已停止同步。')
            try:
                message = messages.get(timeout=0.15)
            except queue.Empty:
                continue
            if message is None:
                raise QuotaError('Codex 额度服务已退出。')
            if message.get('id') == request_id:
                if 'error' in message:
                    # Do not display raw backend errors or credential-bearing output.
                    raise QuotaError('Codex 额度读取失败；请确认桌面应用已登录。')
                return message.get('result', {})
        raise QuotaError('Codex 同步超时；保留上次读数。')

    try:
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {
            'name': 'local_quota_pet', 'title': 'Local Quota Pet', 'version': '0.1.0'}}})
        receive(1)
        send({'method': 'initialized', 'params': {}})
        send({'id': 2, 'method': 'account/rateLimits/read'})
        return parse_limits(receive(2))
    except (OSError, BrokenPipeError, ValueError):
        raise QuotaError('无法连接本机 Codex 额度服务。') from None
    finally:
        try:
            process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # Kill only the process tree we just started, including runtime children.
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=flags, timeout=5)
            else:
                process.kill()
            process.wait(timeout=5)
        thread.join(timeout=1)
        process.stdout.close()


if __name__ == '__main__':
    try:
        print(json.dumps(fetch_limits(), ensure_ascii=False))
    except QuotaError as exc:
        print(str(exc))
        raise SystemExit(1)
