# Boot the custom fork engine (octree cache cleared) and run a custom-engine
# BrineWatch script that attaches to it, then stop the engine.
#
#   $env:UNREAL_EDITOR_EXE = "<UnrealEditor.exe>"
#   powershell -File scripts\run_custom_demo.ps1                        # scientific mission
#   powershell -File scripts\run_custom_demo.ps1 -Script scripts\capture_cinematic_inspection.py

param(
    [string]$Script = "scripts\run_custom_pfh2026_demo.py",
    [string]$ScriptArgs = ""
)

$ErrorActionPreference = "Stop"
$py = "C:\Users\andrea.bedei3\.conda\envs\ocean\python.exe"
if ($env:BRINEWATCH_PYTHON) { $py = $env:BRINEWATCH_PYTHON }
$repo = Split-Path -Parent $PSScriptRoot
$engineDir = Join-Path (Split-Path -Parent $repo) "engine"
if ($env:HOLOOCEAN_CUSTOM_ENGINE_PATH) {
    $c = $env:HOLOOCEAN_CUSTOM_ENGINE_PATH
    if (Test-Path (Join-Path $c "Holodeck.uproject")) { $engineDir = $c }
    elseif (Test-Path (Join-Path $c "engine\Holodeck.uproject")) { $engineDir = Join-Path $c "engine" }
}
$engineLog = Join-Path $engineDir "Saved\Logs\HolodeckCustom.log"

Write-Output "=== boot custom engine ==="
Get-Process -Name UnrealEditor,Holodeck -ErrorAction SilentlyContinue |
    Stop-Process -Force -Confirm:$false -ErrorAction SilentlyContinue
Start-Sleep -Seconds 6
if (Test-Path $engineLog) { Remove-Item $engineLog -Force -ErrorAction SilentlyContinue }
Start-Process -FilePath $py -ArgumentList @(
    (Join-Path $repo "scripts\launch_custom_engine.py"), "--clear-cache") -WindowStyle Minimized | Out-Null

$deadline = (Get-Date).AddMinutes(6)
while ($true) {
    if ((Get-Date) -gt $deadline) { throw "engine boot timeout" }
    if ((Test-Path $engineLog) -and
        (Select-String -Path $engineLog -Pattern "Creating file mapping" -Quiet)) { break }
    Start-Sleep -Seconds 5
}
Write-Output "engine ready"

Write-Output "=== run $Script ==="
$scriptPath = Join-Path $repo $Script
if ($ScriptArgs) {
    & $py -u $scriptPath $ScriptArgs.Split(" ")
} else {
    & $py -u $scriptPath
}
$code = $LASTEXITCODE

Write-Output "=== stop engine ==="
Get-Process -Name UnrealEditor,Holodeck -ErrorAction SilentlyContinue |
    Stop-Process -Force -Confirm:$false -ErrorAction SilentlyContinue
Write-Output "CUSTOM DEMO DRIVER DONE (script exit $code)"
