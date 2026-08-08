# Install the reviewed user-level `skill` command on Windows without elevation.
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('install')]
    [string]$Mode
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSCommandPath

if (-not $Mode) {
    throw 'Usage: .\bootstrap.ps1 install'
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is missing from PATH. Install uv before running this bootstrap.'
}

$Dirty = & git -C $RepoRoot status --porcelain=v1
if ($LASTEXITCODE -ne 0) {
    throw "Cannot inspect Git identity for $RepoRoot"
}
if ($Dirty) {
    throw "Manager source is dirty: $RepoRoot"
}

& uv tool install --editable $RepoRoot
if ($LASTEXITCODE -ne 0) {
    throw 'uv tool installation failed.'
}
Write-Output "PASS: skill command installed from $RepoRoot"
