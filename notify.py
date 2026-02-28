#!/usr/bin/env python3
"""
Claude Code Notifier - desktop notification hook with AI session summary.
Supports macOS (osascript) and Windows (PowerShell toast).

Triggers on:
  - Stop: Claude finished responding
  - Notification: Claude needs user input or permission
"""

import json
import sys
import os
import subprocess
import re


def get_first_user_message(transcript_path):
    """Extract the first user message from a Claude Code transcript JSONL file."""
    try:
        with open(transcript_path, "r") as f:
            for line in f:
                obj = json.loads(line.strip())
                if obj.get("type") == "user" and obj.get("message", {}).get("role") == "user":
                    content = obj["message"].get("content", "")
                    if isinstance(content, list):
                        content = " ".join(
                            b.get("text", "") for b in content if b.get("type") == "text"
                        )
                    return content.strip().replace("\n", " ")[:200]
    except Exception:
        pass
    return ""


def summarize_with_ai(text, base_url, auth_token):
    """Use Anthropic API (claude-3-haiku) to generate a short session summary."""
    try:
        import anthropic

        client = anthropic.Anthropic(base_url=base_url, auth_token=auth_token)
        resp = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=20,
            messages=[{
                "role": "user",
                "content": f"Summarize the task in 6 words or less. Output only the summary, no punctuation or quotes:\n{text}"
            }]
        )
        return resp.content[0].text.strip().strip("\"'、。！.,!\"'")
    except Exception:
        return ""


def summarize_locally(text):
    """Extract a short key phrase from the text without any API call."""
    # Strip common Chinese prefixes
    text = re.sub(
        r'^(请你?|帮我|帮忙|麻烦你?|我想要?|我要|我需要|我希望|能不能|可以|能否|你能|我的)+',
        '', text
    )
    # Split into clauses
    parts = re.split(r'[，。！？,.?;；：:\n]', text)
    parts = [p.strip() for p in parts if len(p.strip()) >= 2]
    if not parts:
        return text[:12]

    # Score clauses: prefer short, early ones
    scored = []
    for i, p in enumerate(parts):
        score = (1.0 / (i + 1)) * (1.0 / max(len(p), 1))
        if 4 <= len(p) <= 12:
            score *= 3
        scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    best = scored[0][1]

    # Truncate: word-boundary for English, char-boundary for CJK
    if re.search(r'[a-zA-Z]', best):
        words = best.split()
        result = ''
        for w in words:
            if len(result + ' ' + w) > 16:
                break
            result = (result + ' ' + w).strip()
        return result or best[:12]
    return best[:12]


def get_session_name(transcript, session_id, cwd):
    """Get a short session name: cache -> AI summary -> local extraction -> dir name."""
    if sys.platform == "win32":
        cache_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "claude-code-notifier")
    else:
        cache_dir = os.path.expanduser("~/.cache/claude-code-notifier")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, session_id) if session_id else ""

    # 1. Check cache
    if cache_file and os.path.exists(cache_file):
        with open(cache_file) as f:
            name = f.read().strip()
            if name:
                return name

    # 2. Generate from transcript
    first_msg = get_first_user_message(transcript) if transcript else ""
    session_name = ""

    if first_msg:
        # Try AI summary
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
        auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

        if base_url and (auth_token or api_key):
            session_name = summarize_with_ai(
                first_msg, base_url, auth_token or api_key
            )
        elif api_key:
            session_name = summarize_with_ai(
                first_msg, "https://api.anthropic.com", api_key
            )

        # Fallback: local extraction
        if not session_name:
            session_name = summarize_locally(first_msg)

    # Write cache
    if session_name and cache_file:
        with open(cache_file, "w") as f:
            f.write(session_name)

    return session_name or os.path.basename(cwd)


def get_terminal_pid():
    """Walk up the process tree to find the terminal window PID (Windows only)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes

        ntdll = ctypes.windll.ntdll
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        class PROCESS_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("Reserved1", ctypes.c_void_p),
                ("PebBaseAddress", ctypes.c_void_p),
                ("Reserved2", ctypes.c_void_p * 2),
                ("UniqueProcessId", ctypes.POINTER(ctypes.c_ulong)),
                ("InheritedFromUniqueProcessId", ctypes.POINTER(ctypes.c_ulong)),
            ]

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
        )

        def pid_has_visible_window(pid):
            found = [False]
            def callback(hwnd, _lparam):
                if user32.IsWindowVisible(hwnd):
                    wpid = ctypes.wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
                    if wpid.value == pid and user32.GetWindowTextLengthW(hwnd) > 0:
                        found[0] = True
                        return False
                return True
            user32.EnumWindows(WNDENUMPROC(callback), 0)
            return found[0]

        def get_parent_pid(pid):
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return None
            try:
                pbi = PROCESS_BASIC_INFORMATION()
                status = ntdll.NtQueryInformationProcess(
                    handle, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None
                )
                if status == 0:
                    return ctypes.cast(
                        pbi.InheritedFromUniqueProcessId, ctypes.c_void_p
                    ).value
                return None
            finally:
                kernel32.CloseHandle(handle)

        pid = os.getpid()
        visited = set()
        ancestors = []

        while pid and pid > 4 and pid not in visited:
            visited.add(pid)
            ancestors.append(pid)
            parent = get_parent_pid(pid)
            if parent is None or parent <= 4:
                break
            pid = parent

        # Return closest ancestor (from current process upward) that owns a visible window
        for p in ancestors[1:]:
            if pid_has_visible_window(p):
                return p

        return ancestors[-1] if ancestors else None
    except Exception:
        return None


def ensure_protocol_handler():
    """Register claude-code-notifier:// protocol handler in the Windows registry if missing."""
    if sys.platform != "win32":
        return
    try:
        import winreg
        key_path = r"Software\Classes\claude-code-notifier"
        try:
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path + r"\shell\open\command")
            return  # already registered
        except FileNotFoundError:
            pass

        # Find pythonw.exe
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable

        activate_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "activate_window.py")
        if not os.path.exists(activate_script):
            return

        command = f'"{pythonw}" "{activate_script}" "%1"'

        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:claude-code-notifier Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        winreg.CloseKey(key)

        cmd_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\shell\open\command")
        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command)
        winreg.CloseKey(cmd_key)
    except Exception:
        pass


WINDOWS_SOUNDS = {
    "Hero": r"C:\Windows\Media\Windows Notify System Generic.wav",
    "Sosumi": r"C:\Windows\Media\Windows Notify Calendar.wav",
}


def send_notification(title, subtitle, body, sound, terminal_pid=None, cwd=""):
    """Send a desktop notification with sound (macOS or Windows)."""
    if sys.platform == "win32":
        _send_windows_notification(title, subtitle, body, sound, terminal_pid, cwd)
    else:
        _send_macos_notification(title, subtitle, body, sound)


def _send_macos_notification(title, subtitle, body, sound):
    """Send a macOS desktop notification with sound."""
    body = body.replace('"', '\\"')
    subtitle = subtitle.replace('"', '\\"')
    script = (
        f'display notification "{body}" '
        f'with title "{title}" '
        f'subtitle "{subtitle}" '
        f'sound name "{sound}"'
    )
    subprocess.run(["osascript", "-e", script], capture_output=True)


def _send_windows_notification(title, subtitle, body, sound, terminal_pid=None, cwd=""):
    """Send a Windows toast notification with sound."""
    sound_path = WINDOWS_SOUNDS.get(sound, "")
    # Play sound in background
    if sound_path and os.path.exists(sound_path):
        ps_sound = (
            f"(New-Object System.Media.SoundPlayer '{sound_path}').PlaySync()"
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps_sound],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    # Send toast notification via PowerShell with registered App ID
    display_body = f"{subtitle}\n{body}" if subtitle else body
    title = title.replace("'", "''")
    display_body = display_body.replace("'", "''")
    # Build launch attribute for click-to-activate
    if terminal_pid:
        from urllib.parse import quote
        cwd_encoded = quote(cwd, safe="") if cwd else ""
        launch_attr = f' activationType="protocol" launch="claude-code-notifier://activate?pid={terminal_pid}&amp;cwd={cwd_encoded}"'
    else:
        launch_attr = ''
    ps_toast = f"""
$appId = 'Claude.Code.Notifier'
$regPath = 'HKCU:\\Software\\Classes\\AppUserModelId\\' + $appId
if (-not (Test-Path $regPath)) {{
    New-Item -Path $regPath -Force | Out-Null
    New-ItemProperty -Path $regPath -Name 'DisplayName' -Value 'Claude Code' -PropertyType String -Force | Out-Null
}}
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$xml = @'
<toast duration="long"{launch_attr}>
  <visual>
    <binding template="ToastGeneric">
      <text>{title}</text>
      <text>{display_body}</text>
    </binding>
  </visual>
</toast>
'@
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_toast],
        capture_output=True,
    )


def main():
    data = json.loads(os.environ.get("HOOK_INPUT", "{}"))
    event = data.get("hook_event_name", "")

    if event not in ("Stop", "Notification"):
        sys.exit(0)

    if sys.platform == "win32":
        ensure_protocol_handler()

    cwd = data.get("cwd", "")
    session_id = data.get("session_id", "")
    transcript = data.get("transcript_path", "")
    last_msg = data.get("last_assistant_message", "")[:80].replace('"', "").replace("\n", " ")
    notif_msg = data.get("message", "").replace('"', "").replace("\n", " ")

    session_name = get_session_name(transcript, session_id, cwd)
    terminal_pid = get_terminal_pid()

    if event == "Stop":
        send_notification(
            title="✅ 已完成",
            subtitle=session_name,
            body=last_msg or "回复已完成",
            sound="Hero",
            terminal_pid=terminal_pid,
            cwd=cwd,
        )
    else:
        send_notification(
            title="⏳ 等待操作",
            subtitle=session_name,
            body=notif_msg or "需要你的输入",
            sound="Sosumi",
            terminal_pid=terminal_pid,
            cwd=cwd,
        )


if __name__ == "__main__":
    main()
