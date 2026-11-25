$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$profile = Get-Content -LiteralPath (Join-Path $root 'profile.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($profile.ssh_host -notmatch '^[A-Za-z0-9_.@-]+$' -or $profile.remote_dir -notmatch '^/home/nvidia/luna-test-runs/[A-Za-z0-9_/-]+$') { throw 'Invalid console profile.' }
$python = (Get-Command python.exe -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) { throw 'pythonw.exe is required for the native desktop console.' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'vendor\PIL\__init__.py'))) {
    & $python -m pip install --target (Join-Path $root 'vendor') --only-binary=:all: -r (Join-Path $root 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Console-local image dependency installation failed.' }
}
& ssh.exe -T -o BatchMode=yes -o StrictHostKeyChecking=yes $profile.ssh_host "mkdir -p $($profile.remote_dir)"
if ($LASTEXITCODE -ne 0) { throw 'Robot SSH is unavailable; no settings were changed.' }
& scp.exe -q (Join-Path $root 'robot_agent.py') (Join-Path $root 'test_agent_guards.py') "$($profile.ssh_host):$($profile.remote_dir)/"
if ($LASTEXITCODE -ne 0) { throw 'Agent upload failed.' }
& ssh.exe -T -o BatchMode=yes $profile.ssh_host "/usr/bin/python3 -m py_compile $($profile.remote_dir)/robot_agent.py"
if ($LASTEXITCODE -ne 0) { throw 'Robot-side syntax check failed.' }
$desktop = [Environment]::GetFolderPath('Desktop')
$link = Join-Path $desktop 'Gento Luna 协作搬运控制台.lnk'
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($link)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '-B "' + (Join-Path $root 'app.py') + '"'
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = (Join-Path $root 'luna-console.ico') + ',0'
$shortcut.Description = 'Gento Luna 参数检查、视频预览与 PICO 快捷控制；打开不启动动作'
$shortcut.Save()
Write-Output "Shortcut created: $link"
Write-Output 'Only console files uploaded. No Robot, Teleop, Tool, mode or motion command was sent.'
