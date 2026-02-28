"""
Claude Code Notifier - Window Activator
Invoked by Windows when user clicks a toast notification.
Usage: pythonw.exe activate_window.py "claude-code-notifier://activate?pid=12345"
"""
import sys
import os
import ctypes
import ctypes.wintypes
from urllib.parse import urlparse, parse_qs, unquote


def find_window_by_pid(target_pid, keyword=None):
    """Find the main visible window belonging to a given PID.
    If keyword is provided, prefer windows whose title contains it."""
    user32 = ctypes.windll.user32
    result = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )

    def enum_callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        length = user32.GetWindowTextLengthW(hwnd)
        if pid.value == target_pid and length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            result.append((hwnd, buf.value))
        return True

    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

    if not result:
        return None

    # Prefer window whose title contains the keyword (project dir name)
    if keyword:
        keyword_lower = keyword.lower()
        for hwnd, title in result:
            if keyword_lower in title.lower():
                return hwnd

    return result[0][0]


def activate_window(hwnd):
    """Bring a window to the foreground.

    Windows restricts SetForegroundWindow for background processes.
    Use multiple strategies to reliably bring the window to front.
    """
    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    # Attach to the foreground window's thread to bypass SetForegroundWindow restriction
    fore_hwnd = user32.GetForegroundWindow()
    fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None)
    cur_thread = ctypes.windll.kernel32.GetCurrentThreadId()

    if fore_thread != cur_thread:
        user32.AttachThreadInput(cur_thread, fore_thread, True)

    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)

    if fore_thread != cur_thread:
        user32.AttachThreadInput(cur_thread, fore_thread, False)

    # Fallback: flash + topmost toggle if SetForegroundWindow was silently rejected
    if user32.GetForegroundWindow() != hwnd:
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
        user32.SetForegroundWindow(hwnd)


def main():
    if len(sys.argv) < 2:
        return

    parsed = urlparse(sys.argv[1])
    params = parse_qs(parsed.query)
    pid_str = params.get("pid", [None])[0]
    if not pid_str:
        return

    try:
        pid = int(pid_str)
    except ValueError:
        return

    # Check if process is still alive
    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return
    kernel32.CloseHandle(handle)

    # Extract project dir name from cwd for window title matching
    cwd_raw = params.get("cwd", [None])[0]
    keyword = os.path.basename(unquote(cwd_raw)) if cwd_raw else None

    hwnd = find_window_by_pid(pid, keyword=keyword)
    if hwnd:
        activate_window(hwnd)


if __name__ == "__main__":
    main()
