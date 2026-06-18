# -*- coding: utf-8 -*-
"""OS clipboard reader — the piece Textual omits (it can write via OSC 52 but not read).

`read_clipboard()` returns the current system clipboard text so that ctrl+v in the
wizard pastes content copied from *anywhere* in the OS, not just text copied inside
the app. Windows uses the Win32 API via ctypes (no dependency); POSIX shells out to
the platform clipboard tool. Every failure path returns "" — paste then falls back
to Textual's internal buffer.
"""

from __future__ import annotations

import platform
import subprocess

_CF_UNICODETEXT = 13
_POSIX_READERS = (
    ["pbpaste"],
    ["wl-paste", "--no-newline"],
    ["xclip", "-selection", "clipboard", "-o"],
    ["xsel", "--clipboard", "--output"],
)


def read_clipboard() -> str:
    """Return the OS clipboard's text, or "" if it is empty or cannot be read."""
    try:
        if platform.system() == "Windows":
            return _read_windows()
        return _read_posix()
    except Exception:
        return ""


def _read_windows() -> str:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    if not user32.OpenClipboard(0):
        return ""
    try:
        if not user32.IsClipboardFormatAvailable(_CF_UNICODETEXT):
            return ""
        handle = user32.GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return ""
        kernel32.GlobalLock.restype = ctypes.c_void_p
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer) or ""
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _read_posix() -> str:
    for cmd in _POSIX_READERS:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return result.stdout
    return ""
