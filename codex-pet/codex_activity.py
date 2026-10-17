"""Read local desktop turn metadata only; no conversation bodies or credentials.

This is a version-dependent local integration, not a public API. Missing schema
or unreadable locks yield unknown rather than pretending the pet is thinking.
"""
import ctypes
from ctypes import wintypes
from pathlib import Path
import os
import sqlite3


def writer_is_live(path):
    if os.name != 'nt': return None
    import msvcrt
    class Overlapped(ctypes.Structure):
        _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                    ('Offset', wintypes.DWORD), ('OffsetHigh', wintypes.DWORD), ('hEvent', wintypes.HANDLE)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
    kernel.UnlockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, ctypes.POINTER(Overlapped)]
    try:
        with path.open('rb') as stream:
            handle = msvcrt.get_osfhandle(stream.fileno()); overlap = Overlapped()
            # Shared, nonblocking byte-range lock; does not change the file.
            if kernel.LockFileEx(handle, 1, 0, 1, 0, ctypes.byref(overlap)):
                kernel.UnlockFileEx(handle, 0, 1, 0, ctypes.byref(overlap))
                return False
            return True if ctypes.get_last_error() == 33 else None
    except FileNotFoundError:
        return False
    except OSError:
        return None


def read_activity(home=None, lock_probe=writer_is_live, watching=()):
    home = Path(home) if home else Path(os.environ.get('CODEX_HOME', Path.home()/'.codex'))
    try:
        con = sqlite3.connect((home/'thread_history_1.sqlite').as_uri()+'?mode=ro', uri=True, timeout=.3)
        outcomes = {}
        try:
            con.execute('PRAGMA query_only=ON')
            rows = con.execute('''SELECT thread_id FROM thread_turns AS t
                WHERE status='inProgress' AND completed_at IS NULL
                AND NOT EXISTS (SELECT 1 FROM thread_turns AS newer
                    WHERE newer.thread_id=t.thread_id AND newer.rollout_ordinal>t.rollout_ordinal)''').fetchall()
            # Only lifecycle metadata for previously observed active threads.
            # A stop or a lost connection must not become a success celebration.
            for thread_id in watching:
                result = con.execute('''SELECT status FROM thread_turns
                    WHERE thread_id=? ORDER BY rollout_ordinal DESC LIMIT 1''', (thread_id,)).fetchone()
                if result and result[0] != 'inProgress': outcomes[thread_id] = result[0]
        finally:
            con.close()
        active_ids = []; unknown = False
        for (thread_id,) in rows:
            # Do not accept a database value as a filesystem path.
            if not thread_id or any(c not in '0123456789abcdef-' for c in thread_id):
                unknown = True; continue
            live = lock_probe(home/'thread-writer-locks'/(thread_id+'.lock'))
            if live is True: active_ids.append(thread_id)
            unknown |= live is None
        return {'state': 'working' if active_ids else ('unknown' if unknown else 'idle'),
                'count': len(active_ids), 'active_ids': active_ids, 'outcomes': outcomes}
    except (OSError, sqlite3.Error, ValueError):
        return {'state': 'unknown', 'count': 0, 'active_ids': [], 'outcomes': {}}
