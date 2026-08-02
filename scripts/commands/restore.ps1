<#
Verified restore into an empty destination.
Every backup file is hash-checked before copying; recorded junctions are reported for manual review
instead of silently recreating absolute links that may target the wrong machine.
Call example: Restore-AICapabilities -BackupPath "D:\backups\ai-capabilities-..." -DestinationRoot "D:\restored" -Apply
#>


# --- Restore a verified backup into an empty destination ---
function Restore-AICapabilities {
    param(
        [Parameter(Mandatory)][string]$BackupPath,                   # Timestamped backup directory containing the final manifest.
        [Parameter(Mandatory)][string]$DestinationRoot,              # Must be absent or empty to prevent mixed old/new state.
        [switch]$Apply                                               # Preview performs complete manifest and hash validation.
    )

    $backup = Get-CanonicalPath -Path $BackupPath
    $manifestPath = Join-Path $backup "backup-manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "BLOCKED: Backup manifest is missing." }
    $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    if ($manifest.schemaVersion -ne 1) { throw "BLOCKED: Unsupported backup manifest schema '$($manifest.schemaVersion)'." }

    foreach ($file in $manifest.files) {
        $storedPath = Join-Path $backup ([string]$file.backupRelativePath) # Relative storage paths survive moving the complete backup directory.
        Assert-PathWithinRoot -Path $storedPath -Root $backup
        if (-not (Test-Path -LiteralPath $storedPath -PathType Leaf)) { throw "BLOCKED: Backup file is missing: $storedPath" }
        $actualHash = (Get-FileHash -LiteralPath $storedPath -Algorithm SHA256).Hash
        if ($actualHash -ne $file.sha256) { throw "BLOCKED: Backup hash mismatch: $storedPath" }
    }

    $destination = [IO.Path]::GetFullPath($DestinationRoot)
    if (Test-Path -LiteralPath $destination) {
        $existing = @(Get-ChildItem -Force -LiteralPath $destination)
        if ($existing.Count) { throw "BLOCKED: Restore destination must be empty: $destination" }
    }
    $plan = [pscustomobject]@{
        status = "PASS"                                            # Manifest, containment, hashes, and destination checks all passed.
        action = if ($Apply) { "RESTORE" } else { "PREVIEW" }
        backup = $backup
        destination = $destination
        fileCount = @($manifest.files).Count
        linksNeedingReview = @($manifest.links).Count
        links = @($manifest.links)
    }
    if (-not $Apply) { return $plan }

    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    try {
        $sourceIndex = @{}                                          # Map each original root to the same numbered backup subtree.
        $manifestSources = @($manifest.sources)                     # Preserve array semantics for a backup containing one source root.
        for ($index = 0; $index -lt $manifestSources.Count; $index += 1) {
            $sourceIndex[[string]$manifestSources[$index]] = $index + 1
        }
        foreach ($file in $manifest.files) {
            $number = $sourceIndex[[string]$file.sourceRoot]
            $leaf = Split-Path -Leaf ([string]$file.sourceRoot)
            $restoreBase = Join-Path $destination ("{0:D2}-{1}" -f $number, $leaf)
            $restoreFile = if ($file.relativePath -eq ".") { $restoreBase } else { Join-Path $restoreBase ([string]$file.relativePath) }
            Assert-PathWithinRoot -Path $restoreFile -Root $destination
            New-Item -ItemType Directory -Path (Split-Path -Parent $restoreFile) -Force | Out-Null
            $storedPath = Join-Path $backup ([string]$file.backupRelativePath)
            Copy-Item -LiteralPath $storedPath -Destination $restoreFile -Force
        }
        $plan.action = "RESTORED"
        return $plan                                                # Link records stay in output for an explicit later activation decision.
    }
    catch {
        if (Test-Path -LiteralPath $destination) {
            $parent = Split-Path -Parent $destination
            Assert-PathWithinRoot -Path $destination -Root $parent
            Remove-Item -LiteralPath $destination -Recurse -Force  # Roll back only the new empty-destination restore tree.
        }
        throw
    }
}
