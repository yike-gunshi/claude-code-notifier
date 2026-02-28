# Claude Code Notifier - Windows Uninstaller
# Removes notification hooks from Claude Code settings

$ErrorActionPreference = "Stop"

$SettingsFile = Join-Path $env:USERPROFILE ".claude\settings.json"

Write-Host "Claude Code Notifier - Windows Uninstaller" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $SettingsFile)) {
    Write-Host "Settings file not found. Nothing to uninstall."
    exit 0
}

# Backup
Copy-Item $SettingsFile "$SettingsFile.backup" -Force
Write-Host "Backed up settings to $SettingsFile.backup" -ForegroundColor Green

# Remove hooks using Python
$pyScript = @"
import json, os

settings_path = os.path.join(os.environ['USERPROFILE'], '.claude', 'settings.json')

with open(settings_path, 'r', encoding='utf-8') as f:
    settings = json.load(f)

hooks = settings.get('hooks', {})
removed = []

for key in ['Stop', 'Notification']:
    if key in hooks:
        entries = hooks[key]
        remaining = [e for e in entries if not any('notify.sh' in h.get('command', '') for h in e.get('hooks', []))]
        if len(remaining) < len(entries):
            removed.append(key)
        if remaining:
            hooks[key] = remaining
        else:
            del hooks[key]

settings['hooks'] = hooks

with open(settings_path, 'w', encoding='utf-8') as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)

if removed:
    print('Removed hooks: ' + ', '.join(removed))
else:
    print('No Claude Code Notifier hooks found.')
"@

python -c $pyScript
if ($LASTEXITCODE -ne 0) {
    py -3 -c $pyScript
}

# Clean cache
$cacheDir = Join-Path $env:LOCALAPPDATA "claude-code-notifier"
if (Test-Path $cacheDir) {
    Remove-Item $cacheDir -Recurse -Force
    Write-Host "Cleared session summary cache" -ForegroundColor Green
}

# Remove protocol handler
$protocolKey = "HKCU:\Software\Classes\claude-code-notifier"
if (Test-Path $protocolKey) {
    Remove-Item $protocolKey -Recurse -Force
    Write-Host "Removed protocol handler: claude-code-notifier://" -ForegroundColor Green
}

Write-Host ""
Write-Host "Uninstall complete. Restart Claude Code to apply." -ForegroundColor Green
