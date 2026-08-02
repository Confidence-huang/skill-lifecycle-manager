<#
Portable file backup for explicitly selected AI capability roots.
Physical files are copied once and hashed; reparse points are recorded as link metadata instead of
being traversed into duplicate or machine-specific content.
Call example: Backup-AICapabilities -Paths @("D:\skills", "D:\registry") -BackupRoot "D:\backups" -Apply
#>


# --- Copy one physical tree while recording links ---
function Copy-CapabilityTree {
    param(
        [Parameter(Mandatory)][string]$SourceRoot,                   # Existing file or directory selected by the user.
        [Parameter(Mandatory)][string]$DestinationRoot,              # Transaction-owned backup subtree.
        [Parameter(Mandatory)][string]$BackupRoot,                   # Overall backup root makes stored file references portable.
        [Parameter(Mandatory)][AllowEmptyCollection()][Collections.Generic.List[object]]$Files,
        [Parameter(Mandatory)][AllowEmptyCollection()][Collections.Generic.List[object]]$Links
    )

    $source = Get-CanonicalPath -Path $SourceRoot                   # Canonical source identity is retained in the manifest.
    New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
    $items = [Collections.Generic.List[object]]::new()              # Explicit additions prevent a recursive result from becoming a nested array.
    $items.Add((Get-Item -Force -LiteralPath $source))
    foreach ($child in Get-ChildItem -Force -LiteralPath $source -Recurse) { $items.Add($child) }
    foreach ($item in $items) {
        $relative = if ($item.FullName -eq $source) { "." } else { [IO.Path]::GetRelativePath($source, $item.FullName) }
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $Links.Add([pscustomobject]@{ sourceRoot = $source; relativePath = $relative; linkType = [string]$item.LinkType; target = [string]::Join(";", @($item.Target)) })
            continue                                                # Never follow a junction into duplicated or external content.
        }
        if ($item.PSIsContainer) {
            $directory = if ($relative -eq ".") { $DestinationRoot } else { Join-Path $DestinationRoot $relative }
            New-Item -ItemType Directory -Path $directory -Force | Out-Null # Preserve empty physical directories.
            continue
        }

        $destination = Join-Path $DestinationRoot $relative         # Relative layout remains stable inside this source snapshot.
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $item.FullName -Destination $destination -Force
        $Files.Add([pscustomobject]@{ sourceRoot = $source; relativePath = $relative; backupRelativePath = [IO.Path]::GetRelativePath($BackupRoot, $destination); length = $item.Length; sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash })
    }
}


# --- Create one verified capability backup ---
function Backup-AICapabilities {
    param(
        [Parameter(Mandatory)][string[]]$Paths,                     # Explicit roots prevent a broad accidental home-directory backup.
        [Parameter(Mandatory)][string]$BackupRoot,                  # Timestamped backup directory is created below this owner root.
        [switch]$Apply                                               # Preview reports roots and destination without copying data.
    )

    $existingPaths = @($Paths | Where-Object { Test-Path -LiteralPath $_ })
    if ($existingPaths.Count -eq 0) { throw "BLOCKED: None of the requested backup roots exist." }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = Join-Path $BackupRoot "ai-capabilities-$stamp"    # One timestamp groups data and its final manifest.
    $plan = [pscustomobject]@{
        status = "PASS"                                            # Requested roots exist and the timestamped target is unambiguous.
        action = if ($Apply) { "BACKUP" } else { "PREVIEW" }
        sources = @($existingPaths | ForEach-Object { Get-CanonicalPath $_ })
        destination = $backupPath
        fileCount = $null                                           # Declared up front because strict mode forbids ad-hoc properties.
        linkCount = $null
        manifest = $null
    }
    if (-not $Apply) { return $plan }

    if (Test-Path -LiteralPath $backupPath) { throw "BLOCKED: Backup destination already exists: $backupPath" }
    New-Item -ItemType Directory -Path $backupPath -Force | Out-Null
    $files = [Collections.Generic.List[object]]::new()
    $links = [Collections.Generic.List[object]]::new()
    try {
        $index = 0
        foreach ($path in $existingPaths) {
            $index += 1                                             # Index prevents equal leaf names from colliding in the backup.
            $leaf = Split-Path -Leaf (Get-CanonicalPath $path)
            $destination = Join-Path $backupPath ("data\{0:D2}-{1}" -f $index, $leaf)
            Copy-CapabilityTree -SourceRoot $path -DestinationRoot $destination -BackupRoot $backupPath -Files $files -Links $links
        }
        $manifest = [pscustomobject]@{
            schemaVersion = 1                                      # Restore refuses unknown future manifest contracts.
            createdAt = (Get-Date).ToString("o")
            sources = @($plan.sources)
            files = @($files)
            links = @($links)
        }
        $manifestPath = Join-Path $backupPath "backup-manifest.json"
        Write-AtomicText -Path $manifestPath -Content (($manifest | ConvertTo-Json -Depth 10) + "`n") -OwnerRoot $backupPath # Manifest is written only after all copies and hashes succeed.
        $plan.action = "BACKED_UP"
        $plan.fileCount = $files.Count
        $plan.linkCount = $links.Count
        $plan.manifest = $manifestPath
        return $plan
    }
    catch {
        Assert-PathWithinRoot -Path $backupPath -Root $BackupRoot
        Remove-Item -LiteralPath $backupPath -Recurse -Force        # An incomplete backup never survives without a valid manifest.
        throw
    }
}
