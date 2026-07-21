# Multi-session sonar visibility campaign (custom fork engine).
# One fresh engine per condition (see docs/application/pfh2026/CUSTOM_ENGINE.md:
# one engine session serves one client session), then offline analysis.
#
# Usage:
#   $env:HOLOOCEAN_CUSTOM_ENGINE_PATH = "<fork root>"
#   $env:UNREAL_EDITOR_EXE = "<UnrealEditor.exe>"
#   powershell -File scripts\run_sonar_conditions_campaign.ps1 -OutDir outputs\sonar_conditions_run1

param(
    [Parameter(Mandatory = $true)][string]$OutDir,
    [string[]]$Conditions = @("A", "FULL", "PIPE", "RISERS", "REMOVED")
)

$ErrorActionPreference = "Stop"
# -File invocations deliver arrays as one comma-joined string: split them
$Conditions = @($Conditions | ForEach-Object { $_ -split "," } |
        Where-Object { $_ })
# Resolve Python: BRINEWATCH_PYTHON > active conda env > python on PATH
$py = $env:BRINEWATCH_PYTHON
if (-not $py) { if ($env:CONDA_PREFIX -and (Test-Path (Join-Path $env:CONDA_PREFIX 'python.exe'))) { $py = Join-Path $env:CONDA_PREFIX 'python.exe' } }
if (-not $py) { $c = Get-Command python -ErrorAction SilentlyContinue; if ($c) { $py = $c.Source } }
if (-not $py) { throw 'No Python found: set BRINEWATCH_PYTHON or activate an environment.' }
$repo = Split-Path -Parent $PSScriptRoot
$log = Join-Path $env:HOLOOCEAN_CUSTOM_ENGINE_PATH "engine\Saved\Logs\HolodeckCustom.log"

foreach ($cond in $Conditions) {
    Write-Output "=== condition $cond ==="
    Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue |
        Stop-Process -Force -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 4
    if (Test-Path $log) { Remove-Item $log -Force -ErrorAction SilentlyContinue }

    $engine = Start-Process -FilePath $py -ArgumentList @(
        (Join-Path $repo "scripts\launch_custom_engine.py")) -PassThru -WindowStyle Minimized

    # wait for the engine to create the shared memory (fresh log)
    $deadline = (Get-Date).AddMinutes(6)
    while ($true) {
        if ((Get-Date) -gt $deadline) { throw "engine boot timeout for $cond" }
        if ((Test-Path $log) -and
            (Select-String -Path $log -Pattern "Creating file mapping" -Quiet)) { break }
        Start-Sleep -Seconds 5
    }
    Write-Output "engine ready for $cond"

    & $py -u (Join-Path $repo "scripts\custom_sonar_conditions.py") `
        --condition $cond --out (Join-Path $repo $OutDir)
    if ($LASTEXITCODE -ne 0) { Write-Output "WARNING: condition $cond exited $LASTEXITCODE" }

    Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue |
        Stop-Process -Force -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 4
}

Write-Output "=== offline analysis ==="
& $py -u (Join-Path $repo "scripts\custom_sonar_conditions.py") --analyze --out (Join-Path $repo $OutDir)
Write-Output "CAMPAIGN DONE"
