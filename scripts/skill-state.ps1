<#
Shared Skill asset facts, host layout, and safe file operations.
The command files dot-source this script so scanning, installation, updating, backup, and restore
use one definition of Skill identity, frontmatter validity, Git provenance, path containment, and
SOURCE/HYBRID activity links on both Windows and Linux.
Call example: . "$PSScriptRoot/skill-state.ps1"; Get-SkillHostLayout
#>

Set-StrictMode -Version Latest                                      # Turn accidental nulls and misspelled properties into visible failures.
$ErrorActionPreference = "Stop"                                    # Stop transactions at the first failed filesystem or process operation.

$script:IgnoredSkillSegments = @(                                  # Exclude embedded examples and dependency trees from active discovery.
    ".git", ".venv", "node_modules", "references", "examples",
    "templates", "tests", "test", "fixtures", "assets", "__pycache__", ".trae",
    "site-packages", "dist-packages", ".tox", ".mypy_cache", ".pytest_cache"
)


# --- Select the current host's path comparison rule ---
function Get-SkillPathComparison {
    if ($IsWindows) { return [StringComparison]::OrdinalIgnoreCase } # NTFS activity paths keep their established case-insensitive identity.
    return [StringComparison]::Ordinal                              # Linux paths remain distinct when their letter case differs.
}


# --- Select the current host's path collection comparer ---
function Get-SkillPathStringComparer {
    if ($IsWindows) { return [StringComparer]::OrdinalIgnoreCase }  # Dictionaries and hash sets must agree with direct path checks.
    return [StringComparer]::Ordinal                               # POSIX identities must not be lowercased before deduplication.
}


# --- Normalize a path without removing its filesystem root ---
function Get-NormalizedSkillPath {
    param([Parameter(Mandatory)][string]$Path)                       # Existing and planned paths both need stable textual comparison.

    $fullPath = [IO.Path]::GetFullPath($Path)                      # Collapse relative segments with the current host's path rules.
    $pathRoot = [IO.Path]::GetPathRoot($fullPath)                  # `/`, drive roots, and UNC roots must never trim into an empty string.
    if ($fullPath.Length -gt $pathRoot.Length) {
        $separators = [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
        $fullPath = $fullPath.TrimEnd($separators)                 # One canonical suffix keeps equality and prefix checks consistent.
    }
    return $fullPath                                               # Output retains the original case on every host.
}


# --- Compare two paths using the current filesystem identity rule ---
function Test-SameSkillPath {
    param(
        [Parameter(Mandatory)][string]$Left,                         # First existing or planned filesystem identity.
        [Parameter(Mandatory)][string]$Right                         # Second identity compared without resolving links.
    )

    $leftPath = Get-NormalizedSkillPath -Path $Left                # Normalize separators and dot segments before equality.
    $rightPath = Get-NormalizedSkillPath -Path $Right
    return $leftPath.Equals($rightPath, (Get-SkillPathComparison)) # Windows folds case; Linux deliberately does not.
}


# --- Check whether one path is at or below a declared root ---
function Test-SkillPathAtOrWithinRoot {
    param(
        [Parameter(Mandatory)][string]$Path,                         # Candidate filesystem identity.
        [Parameter(Mandatory)][string]$Root                          # Root whose own identity is also accepted.
    )

    $fullPath = Get-NormalizedSkillPath -Path $Path                # Planned transaction paths may not exist yet.
    $fullRoot = Get-NormalizedSkillPath -Path $Root
    if ($fullPath.Equals($fullRoot, (Get-SkillPathComparison))) { return $true } # Project-root classification accepts the root itself.
    $prefix = $fullRoot + [IO.Path]::DirectorySeparatorChar        # A separator rejects lookalike siblings such as `skills-other`.
    return $fullPath.StartsWith($prefix, (Get-SkillPathComparison))
}


# --- Check whether one path is a strict child of a declared root ---
function Test-SkillPathWithinRoot {
    param(
        [Parameter(Mandatory)][string]$Path,                         # Candidate file or directory below the owner root.
        [Parameter(Mandatory)][string]$Root                          # Owner root itself is not a removable transaction child.
    )

    if (Test-SameSkillPath -Left $Path -Right $Root) { return $false } # Destructive operations must never target the owner root itself.
    return Test-SkillPathAtOrWithinRoot -Path $Path -Root $Root
}


# --- Resolve one optional absolute XDG root ---
function Get-SkillEnvironmentRoot {
    param(
        [Parameter(Mandatory)][string]$Name,                         # XDG variable name read without changing the process environment.
        [Parameter(Mandatory)][string]$Fallback                      # Absolute user-profile fallback used when the variable is absent.
    )

    $configured = [Environment]::GetEnvironmentVariable($Name)     # Empty variables follow the documented XDG fallback behavior.
    if (-not $configured) { return Get-NormalizedSkillPath -Path $Fallback }
    if (-not [IO.Path]::IsPathRooted($configured)) { throw "BLOCKED: $Name must contain an absolute path." }
    return Get-NormalizedSkillPath -Path $configured               # Host-local defaults remain explicit in help and command output.
}


# --- Return the current host's default lifecycle layout ---
function Get-SkillHostLayout {
    if ($IsWindows) {
        return [pscustomobject]@{
            platform = "windows"                                  # Existing D-drive locations remain byte-for-byte compatible.
            skillHome = "D:\CodexProjects\_skills\agents\skills"
            sourceHome = "D:\CodexProjects\_skills\sources"
            stagingHome = "D:\CodexProjects\_skills\staging"
            registryDirectory = "D:\CodexProjects\_skills\registry"
            backupRoot = "D:\CodexProjects\_skills\backups"
            activityLinkType = "Junction"
        }
    }

    if (-not $IsLinux) { throw "BLOCKED: This release supports Windows and Linux hosts only." } # macOS needs its own accepted link and layout evidence.

    $userProfile = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    if (-not $userProfile) { throw "BLOCKED: The current user profile path is unavailable." }
    $dataHome = Get-SkillEnvironmentRoot -Name "XDG_DATA_HOME" -Fallback (Join-Path $userProfile ".local/share")
    $stateHome = Get-SkillEnvironmentRoot -Name "XDG_STATE_HOME" -Fallback (Join-Path $userProfile ".local/state")
    $cacheHome = Get-SkillEnvironmentRoot -Name "XDG_CACHE_HOME" -Fallback (Join-Path $userProfile ".cache")
    $dataRoot = Join-Path $dataHome "skill-lifecycle-manager"      # Sources and backups are durable user-owned lifecycle data.
    return [pscustomobject]@{
        platform = "linux"                                        # The current release accepts Linux as the non-Windows target.
        skillHome = Join-Path $userProfile ".agents/skills"        # Codex and cross-Agent user Skills use the established shared root.
        sourceHome = Join-Path $dataRoot "sources"
        stagingHome = Join-Path (Join-Path $cacheHome "skill-lifecycle-manager") "staging"
        registryDirectory = Join-Path $stateHome "skill-lifecycle-manager"
        backupRoot = Join-Path $dataRoot "backups"
        activityLinkType = "SymbolicLink"
    }
}


# --- Create one SOURCE/HYBRID activity link for the current host ---
function New-SkillActivityLink {
    param(
        [Parameter(Mandatory)][string]$Path,                         # New activity entry below the approved Skill home.
        [Parameter(Mandatory)][string]$Target                        # Validated physical Skill directory in the source repository.
    )

    $linkType = (Get-SkillHostLayout).activityLinkType             # Windows uses Junction; Linux uses SymbolicLink.
    return New-Item -ItemType $linkType -Path $Path -Target $Target # Caller owns collision checks and transaction rollback.
}


# --- Resolve one filesystem link target into an absolute path ---
function Get-SkillLinkTargetPath {
    param([Parameter(Mandatory)][object]$Item)                       # FileSystemInfo must expose one target for a managed activity entry.

    $targets = @($Item.Target)
    if ($targets.Count -ne 1 -or -not $targets[0]) { throw "BLOCKED: Activity link '$($Item.FullName)' must expose exactly one target." }
    $target = [string]$targets[0]
    if (-not [IO.Path]::IsPathRooted($target)) { $target = Join-Path $Item.Parent.FullName $target } # Linux links may store a relative target.
    return Get-NormalizedSkillPath -Path $target                   # The target need not be dereferenced until its caller requests evidence.
}


# --- Normalize an existing path ---
function Get-CanonicalPath {
    param([Parameter(Mandatory)][string]$Path)                       # Path must exist so identity is based on live filesystem evidence.

    $resolved = Resolve-Path -LiteralPath $Path                      # Let PowerShell normalize relative components and provider syntax.
    return [IO.Path]::GetFullPath($resolved.ProviderPath)            # Return a stable absolute Windows path for comparisons and output.
}


# --- Resolve every filesystem-link component in a Skill path ---
function Resolve-SkillPhysicalPath {
    param([Parameter(Mandatory)][string]$Path)                       # A nested entry may sit below an activity link rather than be one itself.

    $canonicalPath = Get-CanonicalPath -Path $Path                  # Normalize dot segments before walking each path component.
    $pathRoot = [IO.Path]::GetPathRoot($canonicalPath)               # Preserve the drive or UNC root while resolving descendants.
    $relative = $canonicalPath.Substring($pathRoot.Length)          # Each component can independently redirect through a filesystem link.
    $components = @($relative -split "[\\/]" | Where-Object { $_ })
    $current = $pathRoot                                             # Build the physical path from left to right.
    foreach ($component in $components) {
        $candidate = Join-Path $current $component                  # Candidate exists because the original full path resolved.
        $item = Get-Item -Force -LiteralPath $candidate
        if ($item.LinkType) {
            $target = Get-SkillLinkTargetPath -Item $item           # Windows Junctions and Linux SymbolicLinks share one target contract.
            $current = Get-CanonicalPath -Path $target              # Resolve the first redirection before checking chained links.
            for ($linkDepth = 0; $linkDepth -lt 16; $linkDepth += 1) {
                $targetItem = Get-Item -Force -LiteralPath $current
                if (-not $targetItem.LinkType) { break }            # Physical directory ends the compatibility-link chain.
                $nextTarget = Get-SkillLinkTargetPath -Item $targetItem
                $current = Get-CanonicalPath -Path $nextTarget      # Follow compatibility chains such as Codex -> agents -> sources.
            }
            if ((Get-Item -Force -LiteralPath $current).LinkType) { throw "BLOCKED: Activity-link chain exceeded 16 links at '$Path'." }
        }
        else {
            $current = $candidate                                   # Ordinary component preserves the current physical chain.
        }
    }
    return [IO.Path]::GetFullPath($current)                          # Final path is stable for alias deduplication and Git checks.
}


# --- Prove that a destructive target stays inside its declared root ---
function Assert-PathWithinRoot {
    param(
        [Parameter(Mandatory)][string]$Path,                         # Exact file or directory that a transaction may remove or replace.
        [Parameter(Mandatory)][string]$Root                          # Narrow owner directory approved for that transaction.
    )

    $fullPath = Get-NormalizedSkillPath -Path $Path                # Normalization closes `..` and relative-path escape routes.
    $fullRoot = Get-NormalizedSkillPath -Path $Root                # Host comparison rules preserve Linux case-sensitive safety.
    if (-not (Test-SkillPathWithinRoot -Path $fullPath -Root $fullRoot)) {
        throw "BLOCKED: '$fullPath' is outside approved root '$fullRoot'."
    }
}


# --- Find eligible Skill entries below a root ---
function Get-SkillEntryFiles {
    param([Parameter(Mandatory)][string]$Root)                       # Root may be an activity directory or a complete source repository.

    $canonicalRoot = Get-CanonicalPath -Path $Root                  # Use one prefix when calculating relative segments.
    $skillFiles = Get-ChildItem -LiteralPath $canonicalRoot -Filter "SKILL.md" -File -Recurse -Force
    return @($skillFiles | Where-Object {
        $relative = [IO.Path]::GetRelativePath($canonicalRoot, $_.FullName) # Runtime separators keep the exclusion check cross-platform.
        $segments = @($relative -split "[\\/]")                  # Windows and imported POSIX paths use the same exclusion check.
        $directorySegments = if ($segments.Count -gt 1) { $segments[0..($segments.Count - 2)] } else { @() }
        -not (@($directorySegments | Where-Object { $_ -in $script:IgnoredSkillSegments -or $_ -like ".venv*" }).Count)
    } | Sort-Object FullName)
}


# --- Read and validate Skill frontmatter ---
function Get-FrontmatterField {
    param(
        [Parameter(Mandatory)][string]$YAML,                         # Frontmatter body without delimiter lines.
        [Parameter(Mandatory)][string]$Field                         # Top-level field name allowed by the Skill contract.
    )

    $lines = @($YAML -split "\r?\n")                              # Preserve block-scalar indentation for multiline descriptions.
    for ($index = 0; $index -lt $lines.Count; $index += 1) {
        $fieldMatch = [regex]::Match($lines[$index], "^$([regex]::Escape($Field)):\s*(?<value>.*?)\s*$")
        if (-not $fieldMatch.Success) { continue }
        $value = $fieldMatch.Groups["value"].Value.Trim()           # Ordinary scalar values finish on the matching line.
        if ($value -notin @(">", ">-", ">+", "|", "|-", "|+")) { return $value.Trim(" `"'") }

        $blockLines = [Collections.Generic.List[string]]::new()     # YAML block scalars continue only through indented lines.
        for ($blockIndex = $index + 1; $blockIndex -lt $lines.Count; $blockIndex += 1) {
            $line = $lines[$blockIndex]
            if ($line -match "^\S") { break }                      # Next top-level key ends the requested field.
            $blockLines.Add($line.Trim())                           # Registry needs readable text, not original presentation indentation.
        }
        if ($value.StartsWith(">")) { return (@($blockLines) -join " ").Trim() } # Folded YAML joins prose with spaces.
        return (@($blockLines) -join "`n").Trim()                  # Literal YAML preserves intended line boundaries.
    }
    return $null                                                    # Caller decides whether a missing field is BLOCKED.
}


# --- Read and validate Skill frontmatter ---
function Read-SkillMetadata {
    param([Parameter(Mandatory)][string]$SkillFile)                  # The file is read with strict UTF-8 to expose corrupt metadata.

    $issues = [Collections.Generic.List[string]]::new()             # Keep every concrete validation issue for BLOCKED reporting.
    try {
        $utf8 = [Text.UTF8Encoding]::new($false, $true)              # Reject replacement-character decoding that would hide corruption.
        $content = [IO.File]::ReadAllText($SkillFile, $utf8)         # Read the complete entry because frontmatter is always at the top.
    }
    catch {
        return [pscustomobject]@{ Name = $null; Description = $null; Status = "BLOCKED"; Issues = @("SKILL.md is not valid UTF-8: $($_.Exception.Message)") }
    }

    $frontmatter = [regex]::Match($content, "\A---\r?\n(?<yaml>.*?)\r?\n---(?:\r?\n|\z)", "Singleline") # Require one leading YAML block.
    if (-not $frontmatter.Success) {                                # A missing block prevents reliable Codex discovery.
        $issues.Add("SKILL.md is missing a leading YAML frontmatter block.")
        return [pscustomobject]@{ Name = $null; Description = $null; Status = "BLOCKED"; Issues = @($issues) }
    }

    $yaml = $frontmatter.Groups["yaml"].Value                       # Parse only fields needed for identity and discovery reporting.
    $name = Get-FrontmatterField -YAML $yaml -Field "name"
    $description = Get-FrontmatterField -YAML $yaml -Field "description"

    if (-not $name) { $issues.Add("Frontmatter field 'name' is missing or empty.") } # Names are the stable discovery identity.
    if (-not $description) { $issues.Add("Frontmatter field 'description' is missing or empty.") } # Descriptions drive Skill triggering.
    if ($name -and $name -notmatch "^[a-z0-9-]{1,64}$") { $issues.Add("Frontmatter name must use 1-64 lowercase letters, digits, or hyphens.") }

    $status = if ($issues.Count) { "BLOCKED" } else { "PASS" }     # Structural failures are actionable, never collapsed into UNKNOWN.
    return [pscustomobject]@{ Name = $name; Description = $description; Status = $status; Issues = @($issues) }
}


# --- Read local Git provenance without changing repository state ---
function Get-GitFacts {
    param([Parameter(Mandatory)][string]$Path)                       # Any path inside a repository is accepted.

    $topLevel = (& git -C $Path rev-parse --show-toplevel 2>$null)  # Git itself resolves worktrees and link-backed repositories.
    if ($LASTEXITCODE -ne 0 -or -not $topLevel) {                   # A package directory legitimately has no Git owner.
        return [pscustomobject]@{ IsRepository = $false; Root = $null; Branch = $null; Commit = $null; Remote = $null; IsClean = $null }
    }

    $root = [IO.Path]::GetFullPath(($topLevel -join "").Trim())     # Normalize Git's slash style before comparing repository roots.
    $branchOutput = @(& git -C $root branch --show-current 2>$null)  # Capture the exit code before running the next Git query.
    $branch = if ($LASTEXITCODE -eq 0) { ($branchOutput -join "").Trim() } else { "" }
    $commitOutput = @(& git -C $root rev-parse --verify HEAD 2>$null) # Unborn repositories must not report the literal string `HEAD`.
    $commit = if ($LASTEXITCODE -eq 0) { ($commitOutput -join "").Trim() } else { "" }
    $remoteOutput = @(& git -C $root remote get-url origin 2>$null)  # Missing origin is recorded as UNKNOWN provenance.
    $remote = if ($LASTEXITCODE -eq 0) { ($remoteOutput -join "").Trim() } else { "" }
    $statusLines = @(& git -C $root status --porcelain=v1 2>$null)  # Porcelain output is stable and color-free for exact checks.

    return [pscustomobject]@{
        IsRepository = $true                                       # Git top-level lookup established repository ownership.
        Root = $root                                                # Physical repository root for source management and updates.
        Branch = if ($branch) { $branch } else { $null }            # Detached repositories intentionally report no branch.
        Commit = if ($commit) { $commit } else { $null }            # Full SHA is the immutable local version evidence.
        Remote = if ($remote) { $remote } else { $null }            # Missing origin is UNKNOWN provenance, not a fake local URL.
        IsClean = ($statusLines.Count -eq 0)                         # Dirty source repositories are blocked from managed updates.
    }
}


# --- Write UTF-8 text atomically inside a declared owner directory ---
function Write-AtomicText {
    param(
        [Parameter(Mandatory)][string]$Path,                         # Final state file path visible to later agents.
        [Parameter(Mandatory)][string]$Content,                      # Complete new content; partial append semantics are forbidden.
        [Parameter(Mandatory)][string]$OwnerRoot                     # Root used to prove the temporary and final targets are bounded.
    )

    Assert-PathWithinRoot -Path $Path -Root $OwnerRoot              # Stop before creating any file outside the declared state root.
    $parent = Split-Path -Parent $Path                              # Registry and manifest directories may not exist on first use.
    New-Item -ItemType Directory -Path $parent -Force | Out-Null    # Directory creation is idempotent inside the approved owner root.
    $temporary = "$Path.$([guid]::NewGuid().ToString('N')).tmp"    # A unique sibling keeps rename atomic on the same volume.
    Assert-PathWithinRoot -Path $temporary -Root $OwnerRoot         # Apply the same containment proof to cleanup-sensitive temp state.

    try {
        [IO.File]::WriteAllText($temporary, $Content, [Text.UTF8Encoding]::new($false)) # Emit portable UTF-8 without a BOM.
        Move-Item -LiteralPath $temporary -Destination $Path -Force # Readers see either the previous complete file or the new one.
    }
    finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary } # Remove only the exact transaction-owned temp file.
    }
}


# --- Convert one value into a safe YAML scalar ---
function ConvertTo-YAMLScalar {
    param([AllowNull()][object]$Value)                              # Registry YAML is a mirror, so every scalar is rendered explicitly.

    if ($null -eq $Value) { return "null" }                        # Preserve JSON null rather than inventing an empty string.
    if ($Value -is [bool]) { return $Value.ToString().ToLowerInvariant() } # YAML booleans stay machine-readable.
    if ($Value -is [byte] -or $Value -is [int16] -or $Value -is [int32] -or $Value -is [int64]) { return [string]$Value }
    $escaped = ([string]$Value).Replace("\", "\\").Replace('"', '\"').Replace("`r", "").Replace("`n", "\n") # Quote paths and descriptions uniformly.
    return '"' + $escaped + '"'
}


# --- Return the standard global activation roots ---
function Get-DefaultSkillRoots {
    param([string]$ProjectRoot)                                     # Optional project root adds project-local activation locations.

    $roots = [Collections.Generic.List[object]]::new()              # Each root carries scope evidence instead of guessing from a Skill name.
    $layout = Get-SkillHostLayout                                  # Central host facts prevent command files from embedding path policy.
    if ($IsWindows) {
        $candidates = @(
            [pscustomobject]@{ Path = $layout.skillHome; Scope = "USER" },
            [pscustomobject]@{ Path = "D:\CodexProjects\_skills\codex\skills"; Scope = "USER" },
            [pscustomobject]@{ Path = "D:\CodexProjects\_skills\codex\plugins-cache"; Scope = "SYSTEM" }
        )
    }
    else {
        $userProfile = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
        $candidates = @(
            [pscustomobject]@{ Path = $layout.skillHome; Scope = "USER" },
            [pscustomobject]@{ Path = Join-Path $userProfile ".codex/skills"; Scope = "USER" },
            [pscustomobject]@{ Path = Join-Path $userProfile ".claude/skills"; Scope = "USER" },
            [pscustomobject]@{ Path = Join-Path $userProfile ".config/opencode/skills"; Scope = "USER" },
            [pscustomobject]@{ Path = Join-Path $userProfile ".codex/plugins/cache"; Scope = "SYSTEM" }
        )
    }
    foreach ($candidate in $candidates) {                           # Missing optional roots are omitted rather than reported as false failures.
        if (Test-Path -LiteralPath $candidate.Path -PathType Container) { $roots.Add($candidate) }
    }

    if ($ProjectRoot) {                                             # Project Skills are discovered only when a concrete project is in scope.
        $project = Get-CanonicalPath -Path $ProjectRoot
        foreach ($relative in @(".agents/skills", ".codex/skills", ".skills")) {
            $candidatePath = Join-Path $project $relative           # Use known project-local conventions, not a recursive drive scan.
            if (Test-Path -LiteralPath $candidatePath -PathType Container) {
                $roots.Add([pscustomobject]@{ Path = $candidatePath; Scope = "PROJECT" })
            }
        }
    }
    return @($roots)
}


# --- Return existing roots used by a default capability backup ---
function Get-DefaultCapabilityBackupRoots {
    param([Parameter(Mandatory)][object]$Layout)                    # CLI passes the already-resolved host layout to keep one decision source.

    if ($IsWindows) {
        $candidates = @(
            $Layout.skillHome,
            "D:\CodexProjects\_skills\codex\skills",
            $Layout.sourceHome,
            $Layout.registryDirectory,
            "C:\Users\Lenovo\.codex\global_rules",
            "C:\Users\Lenovo\.codex\memories"
        )
    }
    else {
        $userProfile = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
        $candidates = @(
            $Layout.skillHome,
            (Join-Path $userProfile ".codex/skills"),
            $Layout.sourceHome,
            $Layout.registryDirectory,
            (Join-Path $userProfile ".codex/memories")
        )
    }
    return @($candidates | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Get-NormalizedSkillPath -Path $_ } | Sort-Object -Unique)
}
