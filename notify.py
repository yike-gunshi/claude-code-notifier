#!/usr/bin/env python3
"""
Claude Code Notifier — cross-platform desktop notification hook with AI session summary.

Triggers on:
  - Stop: Claude finished responding
  - Notification: Claude needs user input or permission

Platforms:
  - Windows 10/11: winotify (native toast API)
  - macOS: osascript (via notify.sh fallback)
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


def send_notification(title, subtitle, body, sound):
    """Send a Windows desktop notification via winotify (native Win10/11 toast API).

    Uses winotify instead of System.Windows.Forms.NotifyIcon balloon tips,
    which are suppressed on modern Windows 11.
    """
    try:
        from winotify import Notification
        import winotify.audio as audio

        full_title = f"{title} - {subtitle}"
        # winotify has a title length limit (~200 chars). Truncate if needed.
        if len(full_title) > 180:
            full_title = full_title[:177] + "..."

        n = Notification(
            app_id="Claude Code",
            title=full_title,
            msg=body[:200] if body else "Claude 需要你的关注",
        )
        n.set_audio(audio.Default, loop=False)
        n.show()
    except Exception:
        # Last-resort fallback: use msg.exe for a basic popup
        try:
            subprocess.run(
                ["msg", "*", f"{title} - {subtitle}: {body}"],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass


def main():
    data = json.loads(os.environ.get("HOOK_INPUT", "{}"))
    event = data.get("hook_event_name", "")

    if event not in ("Stop", "Notification"):
        sys.exit(0)

    cwd = data.get("cwd", "")
    session_id = data.get("session_id", "")
    transcript = data.get("transcript_path", "")
    last_msg = data.get("last_assistant_message", "")[:80].replace('"', "").replace("\n", " ")
    notif_msg = data.get("message", "").replace('"', "").replace("\n", " ")

    session_name = get_session_name(transcript, session_id, cwd)

    if event == "Stop":
        send_notification(
            title="✅ 已完成",
            subtitle=session_name,
            body=last_msg or "回复已完成",
            sound=""
        )
    else:
        send_notification(
            title="⏳ 等待操作",
            subtitle=session_name,
            body=notif_msg or "需要你的输入",
            sound=""
        )


if __name__ == "__main__":
    main()
