#requires -Version 5.1
<#
.SYNOPSIS
    Install the FLAC3D 7.0 plugin into a DeepSeek Harness profile.

.DESCRIPTION
    Copies the plugin to a stable local directory, renders cordis.patch.yml with
    absolute paths, links the package into the profile's node_modules and adds
    the bundle to dsh.profile.bundles.

.PARAMETER ProfileDir
    DSH profile directory. Default: %USERPROFILE%\.dsh\profiles\desktop

.PARAMETER InstallDir
    Where the package is copied. Default: %LOCALAPPDATA%\dsh-flac3d

.PARAMETER Flac3DHome
    FLAC3D installation root. Default: FLAC3D_HOME, the registry, or a common path.

.PARAMETER Python
    Python interpreter for the MCP process. Default: the Python bundled with
    FLAC3D, then `python` / `py -3` on PATH.

.PARAMETER Uninstall
    Remove the junction, the bundle entry and (with -RemoveFiles) the install dir.

.EXAMPLE
    .\install.ps1 -DryRun
    .\install.ps1
    .\install.ps1 -Uninstall
#>
param(
    [string]$ProfileDir = "$env:USERPROFILE\.dsh\profiles\desktop",
    [string]$InstallDir = "$env:LOCALAPPDATA\dsh-flac3d",
    [string]$Flac3DHome,
    [string]$Python,
    [switch]$Uninstall,
    [switch]$RemoveFiles,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot

function Say($msg) { Write-Host "  $msg" }
function Step($msg) { Write-Host "  -> $msg" }
function Act($msg) {
    if ($DryRun) { Write-Host "  [dry-run] $msg" } else { Write-Host "  -> $msg" }
}

function Find-Flac3dHome {
    param([string]$Explicit)
    if ($Explicit -and (Test-Path $Explicit)) { return (Resolve-Path $Explicit).Path.TrimEnd('\') }
    if ($env:FLAC3D_HOME -and (Test-Path $env:FLAC3D_HOME)) {
        return (Resolve-Path $env:FLAC3D_HOME).Path.TrimEnd('\')
    }
    foreach ($key in @('HKLM:\SOFTWARE\Itasca\Flac3d700', 'HKLM:\SOFTWARE\WOW6432Node\Itasca\Flac3d700')) {
        $value = (Get-ItemProperty -Path $key -Name installdir64 -ErrorAction SilentlyContinue).installdir64
        if ($value -and (Test-Path $value)) { return $value.TrimEnd('\') }
    }
    foreach ($guess in @(
            'C:\Program Files\Itasca\FLAC3D700',
            'C:\Program Files\Itasca\FLAC3D 7.0',
            'C:\Program Files (x86)\Itasca\FLAC3D700',
            'D:\Itasca\FLAC3D700')) {
        if (Test-Path $guess) { return $guess }
    }
    return $null
}

function Find-Python {
    param([string]$Explicit, [string]$Flac3dRoot)
    if ($Explicit) {
        $cmd = Get-Command $Explicit -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
        if (Test-Path $Explicit) { return (Resolve-Path $Explicit).Path }
        throw "python not found: $Explicit"
    }
    if ($Flac3dRoot) {
        $bundled = Join-Path $Flac3dRoot 'exe64\python36\python.exe'
        if (Test-Path $bundled) { return $bundled }
    }
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            $exe = & $launcher.Source -3 -c "import sys; print(sys.executable)" 2>$null
            if ($exe -and (Test-Path $exe)) { return $exe.Trim() }
        } catch { }
    }
    $runtime = Join-Path $env:USERPROFILE '.dsh\dsh-runtimes'
    if (Test-Path $runtime) {
        $candidate = Get-ChildItem $runtime -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($candidate) { return $candidate.FullName }
    }
    throw "Python 3 not found. Pass -Python <path to python.exe>."
}

Write-Host "FLAC3D plugin for DeepSeek Harness"
Write-Host "  repo:    $repo"

$link = Join-Path $ProfileDir "node_modules\@local\flac3d"
$manifestPath = Join-Path $ProfileDir "package.json"

if ($Uninstall) {
    if (Test-Path $link) { Act "remove link $link"; if (-not $DryRun) { (Get-Item $link).Delete() } }
    if (Test-Path $manifestPath) {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        $bundles = @($manifest.dsh.profile.bundles) | Where-Object { $_ -ne "@local/flac3d" }
        Act "remove @local/flac3d from dsh.profile.bundles"
        if (-not $DryRun) {
            $manifest.dsh.profile.bundles = @($bundles)
            if ($manifest.dependencies -and $manifest.dependencies.PSObject.Properties.Name -contains "@local/flac3d") {
                $manifest.dependencies.PSObject.Properties.Remove("@local/flac3d")
            }
            [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 10),
                (New-Object System.Text.UTF8Encoding($false)))
        }
    }
    if ($RemoveFiles -and (Test-Path $InstallDir)) {
        Act "delete $InstallDir"
        if (-not $DryRun) { Remove-Item $InstallDir -Recurse -Force }
    }
    Write-Host "Uninstalled. Restart the harness."
    return
}

if (-not (Test-Path $manifestPath)) {
    throw "DSH profile not found: $manifestPath (pass -ProfileDir)"
}

$home_ = Find-Flac3dHome -Explicit $Flac3DHome
if (-not $home_) {
    Write-Warning "FLAC3D not found. Set FLAC3D_HOME before running models."
} else {
    Say "FLAC3D:  $home_"
    $console = Join-Path $home_ 'exe64\flac3d700_console.exe'
    if (-not (Test-Path $console)) { Write-Warning "console executable missing: $console" }
}

$pythonExe = Find-Python -Explicit $Python -Flac3dRoot $home_
Say "python:  $pythonExe"
Say "install: $InstallDir"
Say "profile: $ProfileDir"

Act "copy plugin + runner"
if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Copy-Item (Join-Path $repo "plugin\*") $InstallDir -Recurse -Force
    New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "flac3d") | Out-Null
    Copy-Item (Join-Path $repo "flac3d\runner.py") (Join-Path $InstallDir "flac3d\runner.py") -Force
}

$patchPath = Join-Path $InstallDir "cordis.patch.yml"
$serverPath = Join-Path $InstallDir "mcp_flac3d.py"
Act "render cordis.patch.yml"
if (-not $DryRun) {
    $text = Get-Content (Join-Path $repo "plugin\cordis.patch.yml") -Raw
    $text = $text.Replace("__PYTHON__", $pythonExe.Replace("\", "\\"))
    $text = $text.Replace("__MCP_SERVER__", $serverPath.Replace("\", "\\"))
    [IO.File]::WriteAllText($patchPath, $text, (New-Object System.Text.UTF8Encoding($false)))
}

Act "link into profile node_modules"
if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path (Split-Path $link) | Out-Null
    if (Test-Path $link) { (Get-Item $link).Delete() }
    New-Item -ItemType Junction -Path $link -Target $InstallDir | Out-Null
}

$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$bundles = @($manifest.dsh.profile.bundles)
if ($bundles -contains "@local/flac3d") {
    Say "bundle already registered"
} else {
    Act "register @local/flac3d in dsh.profile.bundles"
    if (-not $DryRun) {
        Copy-Item $manifestPath "$manifestPath.bak-flac3d" -Force
        $manifest.dsh.profile.bundles = @($bundles + "@local/flac3d")
        if (-not $manifest.dependencies) {
            $manifest | Add-Member -NotePropertyName dependencies -NotePropertyValue ([pscustomobject]@{}) -Force
        }
        $manifest.dependencies | Add-Member -NotePropertyName "@local/flac3d" -NotePropertyValue "1.0.0" -Force
        [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 10),
            (New-Object System.Text.UTF8Encoding($false)))
    }
}

Write-Host ""
Write-Host "Installed. Next steps:"
Write-Host "  1. restart DeepSeek Harness (or wait for the bundle to hot-load)"
Write-Host "  2. ask the agent to call flac3d_info, then flac3d_run on examples/cube_gravity.py"
Write-Host "  3. diagnose with .\verify.ps1"
