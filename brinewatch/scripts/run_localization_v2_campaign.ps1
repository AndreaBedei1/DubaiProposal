# Localization v2 campaign: background session + N independent orbit
# acquisitions (fresh engine per session), then offline analysis.
#
#   $env:HOLOOCEAN_CUSTOM_ENGINE_PATH = "<fork root>"
#   $env:UNREAL_EDITOR_EXE = "<UnrealEditor.exe>"
#   powershell -File scripts\run_localization_v2_campaign.ps1 -OutDir outputs\localization_v2_run1

param([Parameter(Mandatory = $true)][string]$OutDir)

$ErrorActionPreference = "Stop"
# Resolve Python: BRINEWATCH_PYTHON > active conda env > python on PATH
$py = $env:BRINEWATCH_PYTHON
if (-not $py) { if ($env:CONDA_PREFIX -and (Test-Path (Join-Path $env:CONDA_PREFIX 'python.exe'))) { $py = Join-Path $env:CONDA_PREFIX 'python.exe' } }
if (-not $py) { $c = Get-Command python -ErrorAction SilentlyContinue; if ($c) { $py = $c.Source } }
if (-not $py) { throw 'No Python found: set BRINEWATCH_PYTHON or activate an environment.' }
$repo = Split-Path -Parent $PSScriptRoot
$log = Join-Path $env:HOLOOCEAN_CUSTOM_ENGINE_PATH "engine\Saved\Logs\HolodeckCustom.log"

function Start-Engine {
    Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue |
        Stop-Process -Force -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 4
    if (Test-Path $log) { Remove-Item $log -Force -ErrorAction SilentlyContinue }
    Start-Process -FilePath $py -ArgumentList @(
        (Join-Path $repo "scripts\launch_custom_engine.py")) -WindowStyle Minimized | Out-Null
    $deadline = (Get-Date).AddMinutes(6)
    while ($true) {
        if ((Get-Date) -gt $deadline) { throw "engine boot timeout" }
        if ((Test-Path $log) -and
            (Select-String -Path $log -Pattern "Creating file mapping" -Quiet)) { break }
        Start-Sleep -Seconds 5
    }
}

# session 1: background library (all radii/phases, no structure)
Write-Output "=== background ==="
Start-Engine
& $py -u (Join-Path $repo "scripts\localize_custom_v2.py") --mode background --out (Join-Path $repo $OutDir)

# sessions 2..5: independent acquisitions (radius x phase x noise seed);
# the first acquisition is the TUNING dataset, the rest are validation
$acqs = @(
    @{r = 18; p = 0.0;   s = 101 },
    @{r = 18; p = 11.25; s = 202 },
    @{r = 22; p = 0.0;   s = 303 },
    @{r = 22; p = 11.25; s = 404 }
)
foreach ($a in $acqs) {
    Write-Output "=== orbit r$($a.r) phase$($a.p) seed$($a.s) ==="
    Start-Engine
    & $py -u (Join-Path $repo "scripts\localize_custom_v2.py") --mode orbit `
        --radius $a.r --phase $a.p --seed $a.s --out (Join-Path $repo $OutDir)
}

Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue |
    Stop-Process -Force -Confirm:$false -ErrorAction SilentlyContinue

Write-Output "=== analysis ==="
& $py -u (Join-Path $repo "scripts\localize_custom_v2.py") --analyze --out (Join-Path $repo $OutDir)
Write-Output "LOCALIZATION V2 CAMPAIGN DONE"
