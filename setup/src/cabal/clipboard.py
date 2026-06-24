# -*- coding: utf-8 -*-
"""OS clipboard helpers for Cabal copy/paste.

`read_clipboard()` returns the current system clipboard text so that ctrl+v in the
wizard pastes content copied from *anywhere* in the OS, not just text copied inside
the app.

`write_clipboard()` pushes copied Textual selections to the OS clipboard. Textual's
default copy path only writes its internal buffer plus an OSC 52 terminal escape,
which is not reliable in every terminal.

Windows uses the Win32 API via ctypes (no dependency); POSIX shells out to the
platform clipboard tool. Every failure path returns a safe empty/False value.
"""

from __future__ import annotations

import platform
import subprocess

_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002
_POSIX_READERS = (
    ["pbpaste"],
    ["wl-paste", "--no-newline"],
    ["xclip", "-selection", "clipboard", "-o"],
    ["xsel", "--clipboard", "--output"],
)
_POSIX_WRITERS = (
    ["pbcopy"],
    ["wl-copy"],
    ["xclip", "-selection", "clipboard"],
    ["xsel", "--clipboard", "--input"],
)


def read_clipboard() -> str:
    """Return the OS clipboard's text, or "" if it is empty or cannot be read."""
    try:
        if platform.system() == "Windows":
            return _read_windows()
        return _read_posix()
    except Exception:
        return ""


def write_clipboard(text: str) -> bool:
    """Write text to the OS clipboard. Returns False if the platform copy fails."""
    try:
        if platform.system() == "Windows":
            return _write_windows(text)
        return _write_posix(text)
    except Exception:
        return False


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


def _write_windows(text: str) -> bool:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HANDLE]
    kernel32.GlobalFree.restype = wintypes.HANDLE

    if not user32.OpenClipboard(0):
        return False

    handle = None
    try:
        if not user32.EmptyClipboard():
            return False

        payload = ctypes.create_unicode_buffer(text + "\0")
        size = ctypes.sizeof(payload)
        handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE, size)
        if not handle:
            return False

        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            kernel32.GlobalFree(handle)
            handle = None
            return False

        try:
            ctypes.memmove(pointer, payload, size)
        finally:
            kernel32.GlobalUnlock(handle)

        if not user32.SetClipboardData(_CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            handle = None
            return False

        # Ownership transferred to the clipboard.
        handle = None
        return True
    finally:
        if handle:
            kernel32.GlobalFree(handle)
        user32.CloseClipboard()


def _write_posix(text: str) -> bool:
    for cmd in _POSIX_WRITERS:
        try:
            result = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return True
    return False
