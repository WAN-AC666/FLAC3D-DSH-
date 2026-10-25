param(
    [string]$ProfileDir = "$env:USERPROFILE\.dsh\profiles\desktop",
    [string]$InstallDir = "$env:LOCALAPPDATA\dsh-flac3d",
    [string]$Python = "python",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot

function Say($msg) { Write-Host "  $msg" }
function Act($msg) { if ($DryRun) { Write-Host "  [dry-run] $msg" } else { Write-Host "  $msg" } }

Write-Host "FLAC3D DSH plugin installer"
Write-Host "  repo:    $repo"
Write-Host "  install: $InstallDir"
Write-Host "  profile: $ProfileDir"

if (-not (Test-Path (Join-Path $ProfileDir "package.json"))) {
    throw "profile not found: $ProfileDir (pass -ProfileDir)"
}

# 1. copy the plugin to a stable, ASCII install directory
Act "copy plugin + runner to $InstallDir"
if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Copy-Item (Join-Path $repo "plugin\*") $InstallDir -Recurse -Force
    New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "flac3d") | Out-Null
    Copy-Item (Join-Path $repo "flac3d\*") (Join-Path $InstallDir "flac3d") -Recurse -Force
}

# 2. resolve an absolute Python for the MCP process
$pythonExe = (Get-Command $Python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe) {
    $pythonExe = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}
if (-not $pythonExe) { throw "Python 3 not found; pass -Python <path-to-python.exe>" }
Say "python: $pythonExe"

# 3. render the bundle patch with absolute paths
$patchPath = Join-Path $InstallDir "cordis.patch.yml"
$serverPath = Join-Path $InstallDir "mcp_flac3d.py"
Act "render $patchPath"
if (-not $DryRun) {
    $text = Get-Content (Join-Path $repo "plugin\cordis.patch.yml") -Raw
    $text = $text.Replace("__PYTHON__", $pythonExe.Replace("\", "\\"))
    $text = $text.Replace("__MCP_SERVER__", $serverPath.Replace("\", "\\"))
    [IO.File]::WriteAllText($patchPath, $text, (New-Object System.Text.UTF8Encoding($false)))
}

# 4. link the bundle into the profile
$scope = Join-Path $ProfileDir "node_modules\@local"
$link = Join-Path $scope "flac3d"
Act "link $link -> $InstallDir"
if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $scope | Out-Null
    if (Test-Path $link) { (Get-Item $link).Delete() }
    New-Item -ItemType Junction -Path $link -Target $InstallDir | Out-Null
}

# 5. register the bundle in the profile manifest
$manifestPath = Join-Path $ProfileDir "package.json"
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$bundles = @($manifest.dsh.profile.bundles)
if ($bundles -notcontains "@local/flac3d") {
    Act "add @local/flac3d to profile bundles"
    if (-not $DryRun) {
        Copy-Item $manifestPath "$manifestPath.bak-flac3d" -Force
        $manifest.dsh.profile.bundles = @($bundles + "@local/flac3d")
        if (-not $manifest.dependencies) {
            $manifest | Add-Member -NotePropertyName dependencies -NotePropertyValue ([pscustomobject]@{}) -Force
        }
        $manifest.dependencies | Add-Member -NotePropertyName "@local/flac3d" -NotePropertyValue "1.0.0" -Force
        $json = $manifest | ConvertTo-Json -Depth 10
        [IO.File]::WriteAllText($manifestPath, $json, (New-Object System.Text.UTF8Encoding($false)))
    }
} else {
    Say "@local/flac3d already registered"
}

Write-Host ""
Write-Host "Done. Restart DeepSeek Harness if the mcp__flac3d__* tools do not appear."
Write-Host "Set FLAC3D_HOME if auto-detection fails."
