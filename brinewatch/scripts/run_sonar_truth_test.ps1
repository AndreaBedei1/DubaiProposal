# Minimal sonar visibility truth test driver.
#
#   $env:UNREAL_EDITOR_EXE = "<UnrealEditor.exe>"      # required for custom
#   # optional: pin the fork client (proven 2.2.2); omit to try the official client
#   $env:HOLOOCEAN_CUSTOM_CLIENT_PATH = "<fork>/client/src"
#   powershell -File scripts\run_sonar_truth_test.ps1 -OutDir outputs\sonar_truth_run1
#
# Runs the OFFICIAL engine (one in-process session, all conditions) and the
# CUSTOM fork engine (one fresh session per condition, octree cache cleared
# before each boot), then the offline analysis. Pass -SkipOfficial or
# -SkipCustom to run only one engine.

param(
    [Parameter(Mandatory = $true)][string]$OutDir,
    [string[]]$Conditions = @("A", "BOX", "CYL", "OUTFALL"),
    [switch]$SkipOfficial,
    [switch]$SkipCustom
)

$ErrorActionPreference = "Stop"
$Conditions = @($Conditions | ForEach-Object { $_ -split "," } | Where-Object { $_ })
$py = "C:\Users\andrea.bedei3\.conda\envs\ocean\python.exe"
if ($env:BRINEWATCH_PYTHON) { $py = $env:BRINEWATCH_PYTHON }
$repo = Split-Path -Parent $PSScriptRoot
$out = Join-Path $repo $OutDir
# the fork engine lives at <repo-root>/engine (parent of brinewatch), or the
# env-var override; its UE log is Saved/Logs/HolodeckCustom.log
$engineDir = Join-Path (Split-Path -Parent $repo) "engine"
if ($env:HOLOOCEAN_CUSTOM_ENGINE_PATH) {
    $c = $env:HOLOOCEAN_CUSTOM_ENGINE_PATH
    if (Test-Path (Join-Path $c "Holodeck.uproject")) { $engineDir = $c }
    elseif (Test-Path (Join-Path $c "engine\Holodeck.uproject")) { $engineDir = Join-Path $c "engine" }
}
$engineLog = Join-Path $engineDir "Saved\Logs\HolodeckCustom.log"

function Stop-Engine {
    Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue |
        Stop-Process -Force -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 4
}

if (-not $SkipOfficial) {
    Write-Output "=== OFFICIAL engine (all conditions, one session) ==="
    Get-Process -Name Holodeck -ErrorAction SilentlyContinue |
        Stop-Process -Force -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    & $py -u (Join-Path $repo "scripts\sonar_truth_test.py") --engine official --out $out
    Get-Process -Name Holodeck -ErrorAction SilentlyContinue |
        Stop-Process -Force -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

if (-not $SkipCustom) {
    foreach ($cond in $Conditions) {
        Write-Output "=== CUSTOM engine, condition $cond (fresh session) ==="
        Stop-Engine
        # clear the on-disk octree cache so the sonar octree rebuilds from scratch
        & $py -u (Join-Path $repo "scripts\launch_custom_engine.py") --clear-cache --dry-run | Out-Null
        if (Test-Path $engineLog) { Remove-Item $engineLog -Force -ErrorAction SilentlyContinue }
        Start-Process -FilePath $py -ArgumentList @(
            (Join-Path $repo "scripts\launch_custom_engine.py"), "--clear-cache") -WindowStyle Minimized | Out-Null
        $deadline = (Get-Date).AddMinutes(6)
        while ($true) {
            if ((Get-Date) -gt $deadline) { throw "engine boot timeout for $cond" }
            if ((Test-Path $engineLog) -and
                (Select-String -Path $engineLog -Pattern "Creating file mapping" -Quiet)) { break }
            Start-Sleep -Seconds 5
        }
        Write-Output "engine ready for $cond"
        & $py -u (Join-Path $repo "scripts\sonar_truth_test.py") --engine custom --condition $cond --out $out
        if ($LASTEXITCODE -ne 0) { Write-Output "WARNING: custom $cond exited $LASTEXITCODE" }
        Stop-Engine
    }
}

Write-Output "=== analysis ==="
& $py -u (Join-Path $repo "scripts\sonar_truth_test.py") --analyze --out $out
Write-Output "TRUTH TEST DONE"
