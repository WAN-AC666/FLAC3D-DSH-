#requires -Version 5.1
<#
.SYNOPSIS
    Check that the machine can run FLAC3D from this checkout.

.DESCRIPTION
    Verifies the FLAC3D installation, the Python interpreter and the runner, then
    (unless -SkipRun) solves the bundled example model end to end. Exit code 0
    means the plugin should work.

.EXAMPLE
    .\verify.ps1
    .\verify.ps1 -SkipRun
#>
param(
    [string]$Flac3DHome,
    [string]$Python,
    [double]$TimeoutSec = 300,
    [switch]$SkipRun
)

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$ok = $true

function Check($name, $condition, $detail) {
    if ($condition) {
        Write-Host ("  [ok]   {0} {1}" -f $name, $detail) -ForegroundColor Green
    } else {
        Write-Host ("  [fail] {0} {1}" -f $name, $detail) -ForegroundColor Red
        $script:ok = $false
    }
}

Write-Host "FLAC3D plugin self-check"
Write-Host "  checkout: $repo"

# FLAC3D
$home_ = $Flac3DHome
if (-not $home_ -and $env:FLAC3D_HOME) { $home_ = $env:FLAC3D_HOME }
if (-not $home_) {
    foreach ($key in @('HKLM:\SOFTWARE\Itasca\Flac3d700', 'HKLM:\SOFTWARE\WOW6432Node\Itasca\Flac3d700')) {
        $value = (Get-ItemProperty -Path $key -Name installdir64 -ErrorAction SilentlyContinue).installdir64
        if ($value) { $home_ = $value; break }
    }
}
if (-not $home_) {
    foreach ($guess in @('C:\Program Files\Itasca\FLAC3D700', 'C:\Program Files\Itasca\FLAC3D 7.0')) {
        if (Test-Path $guess) { $home_ = $guess; break }
    }
}
Check "FLAC3D home" ($home_ -and (Test-Path $home_)) $home_

$console = if ($home_) { Join-Path $home_ 'exe64\flac3d700_console.exe' } else { $null }
Check "console build" ($console -and (Test-Path $console)) $console
$gui = if ($home_) { Join-Path $home_ 'exe64\flac3d700_gui.exe' } else { $null }
Check "gui build" ($gui -and (Test-Path $gui)) $gui

# Python
if (-not $Python) {
    if ($home_ -and (Test-Path (Join-Path $home_ 'exe64\python36\python.exe'))) {
        $Python = Join-Path $home_ 'exe64\python36\python.exe'
    } else {
        $Python = (Get-Command python -ErrorAction SilentlyContinue).Source
    }
}
Check "python" ($Python -and (Test-Path $Python)) $Python

$runner = Join-Path $repo 'flac3d\runner.py'
Check "runner" (Test-Path $runner) $runner

if (-not $ok) {
    Write-Host ""
    Write-Host "Fix the items above. FLAC3D: set FLAC3D_HOME. Python: pass -Python <path>."
    exit 1
}

if ($SkipRun) {
    Write-Host ""
    Write-Host "Static checks passed (-SkipRun)."
    exit 0
}

Write-Host ""
Write-Host "Solving examples/cube_gravity.py ..."
$example = Join-Path $repo 'examples\cube_gravity.py'
$raw = & $Python $runner $example --timeout $TimeoutSec 2>&1 | Out-String
Write-Host $raw

try {
    $result = $raw | ConvertFrom-Json
} catch {
    Write-Host "  [fail] runner did not return JSON" -ForegroundColor Red
    exit 1
}

if ($result.status -eq "ok") {
    Write-Host ("  [ok]   example solved in {0}s, log: {1}" -f $result.seconds, $result.log) -ForegroundColor Green
    exit 0
}

Write-Host ("  [fail] status={0}" -f $result.status) -ForegroundColor Red
if ($result.error) { Write-Host $result.error }
exit 1
