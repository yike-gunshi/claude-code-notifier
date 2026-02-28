# Claude Code Notifier

macOS 和 Windows 桌面通知工具，适配 [Claude Code](https://docs.anthropic.com/en/docs/claude-code)。无需盯着终端，Claude 完成或需要你操作时自动弹窗提醒。

<p align="center">
  <img src="assets/notify-complete.png" width="360" alt="任务完成通知" />
  &nbsp;&nbsp;
  <img src="assets/notify-waiting.png" width="360" alt="等待操作通知" />
</p>

## 背景

Claude Code 是一个基于终端的 AI 编程助手。当你给它分配任务后，它会自主运行——有时几秒，有时几分钟。

**问题：** Claude Code 没有内置的完成提示音。你要么一直盯着终端等，要么切换到其他工作后错过 Claude 完成的时机。两种方式都浪费时间。

**解决方案：** 利用 Claude Code 的 [Hooks](https://docs.anthropic.com/en/docs/claude-code/hooks) 机制，在任务完成或需要操作时发送原生桌面通知 + 提示音。macOS 使用 `osascript`，Windows 使用注册 App ID 的 PowerShell toast 通知，支持操作中心（Action Center）完整显示。通知副标题会显示 AI 生成的会话摘要，一眼就能看出是哪个任务——多会话并行时尤其有用。

**效果：** Claude 完成的瞬间你就会收到通知。切换到其他 App、喝杯咖啡、做别的事情——通知会找到你。

## 功能

- **✅ 已完成** — Claude 回复完毕时弹出通知 + 提示音
- **⏳ 等待操作** — Claude 需要权限确认或等待输入时弹出通知 + 提示音
- **AI 会话摘要** — 自动调用 claude-3-haiku 将首条消息总结为短标题，一眼看出是哪个任务
- **本地 fallback** — 没有 API 时自动切换到本地关键词提取，不依赖网络
- **缓存机制** — 每个 session 只调一次 AI，后续通知瞬间触发
- **点击跳转** — Windows 下点击通知自动跳转到对应项目的 Cursor/终端窗口

## 通知事件

本工具监听 2 个 Hook 事件。Claude Code 还支持更多，你可以自行扩展：

| Hook 事件 | 标题 | macOS 声音 | Windows 声音 | 触发时机 |
|---|---|---|---|---|
| `Stop` | ✅ 已完成 | Hero | Windows Notify System Generic | Claude 完成回复 |
| `Notification` | ⏳ 等待操作 | Sosumi | Windows Notify Calendar | Claude 需要权限或等待输入 |

### 所有可用的 Claude Code Hook 事件

编辑 `notify.py` 和 `~/.claude/settings.json` 即可添加更多事件：

| Hook 事件 | 说明 | 建议声音 |
|---|---|---|
| `Stop` | Claude 完成回复 | Hero（胜利感） |
| `Notification` | 需要权限 / 等待输入 | Sosumi（经典警告） |
| `SubagentStop` | 子 agent 完成任务 | Ping（轻柔） |
| `PreToolUse` | 工具调用前（如 Bash, Write） | Tink（轻叩） |
| `PostToolUse` | 工具调用后 | Pop（短促） |
| `SessionStart` | 新会话开始 | Blow（启动感） |
| `PreCompact` | 上下文压缩前 | Submarine（低沉） |
| `UserPromptSubmit` | 用户提交输入 | —（通常静音） |

### macOS 系统声音参考

`/System/Library/Sounds/` 下所有可用声音：

| 声音 | 风格 | 适合场景 |
|---|---|---|
| `Hero` | 胜利感、振奋 | 任务完成 |
| `Sosumi` | 经典 Mac 警告、辨识度高 | 需要注意 |
| `Funk` | 短促、有力 | 错误或警告 |
| `Basso` | 低沉、严肃 | 严重错误 |
| `Glass` | 轻柔、清脆 | 轻量通知 |
| `Ping` | 快速、干净 | 次要更新 |
| `Pop` | 柔和、活泼 | 工具完成 |
| `Tink` | 轻叩 | 后台事件 |
| `Blow` | 轻风感 | 会话开始 |
| `Bottle` | 空洞、水感 | 中性事件 |
| `Frog` | 蛙鸣、趣味 | 自定义用途 |
| `Morse` | 节奏感 | 重复事件 |
| `Purr` | 轻微振动 | 温和提醒 |
| `Submarine` | 低频声纳 | 系统事件 |

### Windows 系统声音参考

`C:\Windows\Media\` 下可用声音，可在 `notify.py` 的 `WINDOWS_SOUNDS` 字典中修改映射：

| 声音 | 风格 | 适合场景 |
|---|---|---|
| `Windows Notify System Generic` | 干净、现代 | 任务完成（Stop 默认） |
| `Windows Notify Calendar` | 柔和铃声 | 需要注意（Notification 默认） |
| `Windows Notify Email` | 简短、清晰 | 次要更新 |
| `Windows Notify Messaging` | 快速提示 | 消息通知 |
| `Windows Critical Stop` | 紧急感 | 严重错误 |
| `Windows Exclamation` | 警告音 | 警告 |
| `Windows Hardware Insert` | 上升音调 | 会话开始 |
| `chimes` | 经典铃声 | 通用通知 |
| `notify` | 标准通知音 | 中性事件 |

## 系统要求

- **macOS** 或 **Windows 10/11**
- **Python 3.6+**
- **Claude Code** 已安装并配置

## 安装

### macOS

```bash
git clone https://github.com/yike-gunshi/claude-code-notifier.git
cd claude-code-notifier
bash install.sh
```

### Windows

```powershell
git clone https://github.com/yike-gunshi/claude-code-notifier.git
cd claude-code-notifier
powershell -ExecutionPolicy Bypass -File install.ps1
```

安装后重启 Claude Code 即可生效。

### 可选：启用 AI 会话摘要

安装 Anthropic Python SDK 以启用 AI 会话名称总结：

```bash
pip install anthropic
```

会自动使用你现有的 Claude Code API 凭证（`ANTHROPIC_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN`）。如不可用，自动回退到本地关键词提取。

## 工作原理

```
Claude Code Hook (stdin JSON)
        │
        ▼
   notify.sh (入口)
        │
        ▼
   notify.py
        │
        ├── 读取会话 transcript
        │       │
        │       ▼
        ├── AI 摘要 (claude-3-haiku)
        │   或 本地关键词提取
        │       │
        │       ▼
        ├── 缓存摘要
        │   macOS: ~/.cache/claude-code-notifier/
        │   Windows: %LOCALAPPDATA%\claude-code-notifier\
        │
        ▼
   桌面通知 + 提示音
   macOS: osascript  │  Windows: PowerShell toast (注册 App ID)
```

1. Claude Code 通过 stdin 传入 JSON（包含 `session_id`、`transcript_path`、`last_assistant_message` 等）
2. 脚本读取会话 transcript 中的首条用户消息
3. 生成短摘要（AI 或本地 fallback）并按 session 缓存
4. 发送原生桌面通知，摘要作为副标题显示

## 配置

### 修改通知声音

编辑 `notify.py`，修改 `main()` 函数中的 `sound` 值。

### 手动配置 Hook

如果你想手动配置，在 `~/.claude/settings.json` 中添加：

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "command": "/path/to/claude-code-notifier/notify.sh", "type": "command" }
        ],
        "matcher": ".*"
      }
    ],
    "Notification": [
      {
        "hooks": [
          { "command": "/path/to/claude-code-notifier/notify.sh", "type": "command" }
        ],
        "matcher": ".*"
      }
    ]
  }
}
```

## 卸载

### macOS

```bash
cd claude-code-notifier
bash uninstall.sh
```

### Windows

```powershell
cd claude-code-notifier
powershell -ExecutionPolicy Bypass -File uninstall.ps1
```

## 相关项目

如果你需要更丰富的音频 Hook 或跨平台支持，可以参考这些项目：

- [ctoth/claudio](https://github.com/ctoth/claudio) — Go 编写的音频插件，支持音色包和按工具事件播放不同声音
- [wyattjoh/claude-code-notification](https://github.com/wyattjoh/claude-code-notification) — 轻量 macOS 通知 Hook，支持自定义系统声音
- [shanraisshan/claude-code-voice-hooks](https://github.com/shanraisshan/claude-code-voice-hooks) — 工具使用时播放 ding/dong 声音
- [farouqaldori/claude-island](https://github.com/farouqaldori/claude-island) — macOS 菜单栏会话管理器，带通知功能
- [soulee-dev/claude-code-notify-powershell](https://github.com/soulee-dev/claude-code-notify-powershell) — Windows PowerShell toast 通知

## License

MIT
