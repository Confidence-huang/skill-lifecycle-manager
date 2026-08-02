<#
Skill discovery, classification, and Registry output.
The scan follows configured activity roots, deduplicates aliases by physical SKILL.md identity,
then reports asset scope and lifecycle mode as separate evidence-backed fields.
Call example: Invoke-SkillScan -RegistryDirectory "D:\CodexProjects\_skills\registry" -WriteRegistry
#>


# --- Classify one physical Skill entry ---
function New-SkillRecord {
    param(
        [Parameter(Mandatory)][string]$ActivePath,                   # Path through which an Agent discovers the Skill.
        [Parameter(Mandatory)][string]$Scope                         # Scope comes from the scanned activation root.
    )

    $physicalPath = Resolve-SkillPhysicalPath -Path $ActivePath     # Junction aliases collapse onto one physical Skill directory.
    $skillFile = Join-Path $physicalPath "SKILL.md"                 # Every record is anchored to the actual entry file.
    $metadata = Read-SkillMetadata -SkillFile $skillFile            # Strict frontmatter validation determines PASS or BLOCKED.
    $git = Get-GitFacts -Path $physicalPath                         # Git facts decide source ownership and immutable version evidence.
    $issues = [Collections.Generic.List[string]]::new()             # Extend structural issues with provenance uncertainty.
    foreach ($issue in $metadata.Issues) { $issues.Add($issue) }

    $entryCount = 1                                                 # Package Skills have one observed activation entry by definition.
    $mode = "PACKAGE"                                              # No Git owner means the activity directory is the managed package.
    if ($git.IsRepository) {
        $entryCount = @(Get-SkillEntryFiles -Root $git.Root).Count  # A multi-entry repository needs source plus selected activation paths.
        $sameRoot = $physicalPath.TrimEnd("\") -eq $git.Root.TrimEnd("\")
        $mode = if ($sameRoot -and $entryCount -eq 1) { "SOURCE" } else { "HYBRID" }
        if (-not $git.Remote) { $issues.Add("Git repository has no origin remote; publisher provenance is UNKNOWN.") }
        if (-not $git.Commit) { $issues.Add("Git repository has no readable commit SHA.") }
    }

    $status = $metadata.Status                                      # Invalid discovery metadata always remains BLOCKED.
    if ($status -eq "PASS" -and $issues.Count) { $status = "UNKNOWN" } # Missing provenance needs evidence but does not invalidate the entry.
    $name = if ($metadata.Name) { $metadata.Name } else { Split-Path -Leaf $physicalPath }

    $resolvedScope = if ($ActivePath -match "[\\/]codex[\\/]skills[\\/]\.system(?:[\\/]|$)") { "SYSTEM" } else { $Scope }
    return [pscustomobject]@{
        name = $name                                                # Frontmatter identity, with directory fallback only for reporting.
        description = $metadata.Description                         # Full trigger description supports later human review.
        status = $status                                            # Literal PASS/BLOCKED/UNKNOWN evidence state.
        scope = $resolvedScope.ToUpperInvariant()                    # `.system` remains SYSTEM even inside the wider Codex USER root.
        lifecycleMode = $mode                                       # PACKAGE/SOURCE/HYBRID maintenance strategy.
        activePaths = @($ActivePath)                                # Aliases are merged by Invoke-SkillScan.
        physicalPath = $physicalPath                                # Resolved entity used for file identity and Git checks.
        sourceRepository = if ($git.IsRepository) { $git.Root } else { $null }
        remote = $git.Remote                                        # Origin URL is evidence, not a trust verdict.
        branch = $git.Branch                                        # Branch is an update channel, not the version pin.
        commit = $git.Commit                                        # Full SHA is the local immutable version evidence.
        entryCount = $entryCount                                    # Multi-entry repositories classify as HYBRID.
        issues = @($issues)                                         # Concrete problems remain available to humans and automation.
    }
}


# --- Enumerate activity paths, including junction-backed entries ---
function Get-ActivationSkillPaths {
    param([Parameter(Mandatory)][string]$Root)                       # Root itself stays canonical while each top-level entry may redirect.

    $canonicalRoot = Get-CanonicalPath -Path $Root
    $paths = [Collections.Generic.List[string]]::new()
    $rootSkill = Join-Path $canonicalRoot "SKILL.md"                # Rare direct-root Skill layouts remain discoverable.
    if (Test-Path -LiteralPath $rootSkill -PathType Leaf) { $paths.Add($canonicalRoot) }

    $children = @(Get-ChildItem -Force -LiteralPath $canonicalRoot -Directory)
    foreach ($child in $children) {
        if ($child.Name -in $script:IgnoredSkillSegments) { continue } # Do not scan caches, examples, or repository internals as activities.
        $physicalChild = Resolve-SkillPhysicalPath -Path $child.FullName
        foreach ($entry in Get-SkillEntryFiles -Root $physicalChild) {
            $physicalEntry = Split-Path -Parent $entry.FullName      # Map source-relative entry location back through the activity alias.
            $relativeEntry = [IO.Path]::GetRelativePath($physicalChild, $physicalEntry)
            $activeEntry = if ($relativeEntry -eq ".") { $child.FullName } else { Join-Path $child.FullName $relativeEntry }
            $paths.Add([IO.Path]::GetFullPath($activeEntry))
        }
    }
    return @($paths | Sort-Object -Unique)                           # Overlapping enumeration never creates duplicate active paths.
}


# --- Render the Registry as a readable YAML mirror ---
function Convert-RegistryToYAML {
    param([Parameter(Mandatory)][object]$Registry)                   # Canonical object is already stable and sorted before rendering.

    $lines = [Collections.Generic.List[string]]::new()              # A line builder avoids dependency on a machine-wide YAML module.
    $lines.Add("schemaVersion: $($Registry.schemaVersion)")
    $lines.Add("generatedAt: $(ConvertTo-YAMLScalar $Registry.generatedAt)")
    $lines.Add("generator: $(ConvertTo-YAMLScalar $Registry.generator)")
    $lines.Add("roots:")
    foreach ($root in $Registry.roots) { $lines.Add("  - $(ConvertTo-YAMLScalar $root)") }
    $lines.Add("summary:")
    $lines.Add("  total: $($Registry.summary.total)")
    foreach ($groupName in @("status", "scope", "lifecycleMode")) {
        $lines.Add("  ${groupName}:")
        $group = $Registry.summary.$groupName                       # Summary keys are controlled enum values from the scanner.
        foreach ($property in $group.PSObject.Properties) { $lines.Add("    $($property.Name): $($property.Value)") }
    }
    $lines.Add("skills:")
    foreach ($skill in $Registry.skills) {
        $lines.Add("  - name: $(ConvertTo-YAMLScalar $skill.name)")
        foreach ($field in @("description", "status", "scope", "lifecycleMode", "physicalPath", "sourceRepository", "remote", "branch", "commit", "entryCount")) {
            $lines.Add("    ${field}: $(ConvertTo-YAMLScalar $skill.$field)") # Quote every free-text or path field consistently.
        }
        $lines.Add("    activePaths:")
        foreach ($path in $skill.activePaths) { $lines.Add("      - $(ConvertTo-YAMLScalar $path)") }
        $lines.Add("    issues:")
        if ($skill.issues.Count -eq 0) { $lines.Add("      []") } else { foreach ($issue in $skill.issues) { $lines.Add("      - $(ConvertTo-YAMLScalar $issue)") } }
    }
    return ($lines -join "`n") + "`n"                              # End with one newline for clean diffs and shell display.
}


# --- Scan activity roots and optionally persist the Registry ---
function Invoke-SkillScan {
    param(
        [string[]]$Paths,                                           # Explicit roots override the standard global root set.
        [string]$ProjectRoot,                                       # Adds conventional project-local Skill roots when supplied.
        [Parameter(Mandatory)][string]$RegistryDirectory,           # Owner directory for canonical JSON and generated YAML files.
        [switch]$WriteRegistry                                      # Mutation occurs only for the explicit registry command or -Apply.
    )

    $rootRecords = if ($Paths -and $Paths.Count) {                  # Explicit test or project scans get UNKNOWN scope unless recognizable.
        @($Paths | Where-Object { Test-Path -LiteralPath $_ -PathType Container } | ForEach-Object {
            $scope = if ($ProjectRoot -and (Get-CanonicalPath $_).StartsWith((Get-CanonicalPath $ProjectRoot), [StringComparison]::OrdinalIgnoreCase)) { "PROJECT" } else { "UNKNOWN" }
            [pscustomobject]@{ Path = Get-CanonicalPath $_; Scope = $scope }
        })
    }
    else {
        @(Get-DefaultSkillRoots -ProjectRoot $ProjectRoot)           # Standard roots carry USER/SYSTEM/PROJECT evidence.
    }

    $recordsByIdentity = [ordered]@{}                               # Physical SKILL.md path is the deduplication key.
    foreach ($root in $rootRecords) {
        foreach ($activePath in Get-ActivationSkillPaths -Root $root.Path) {
            $record = New-SkillRecord -ActivePath $activePath -Scope $root.Scope
            $identity = (Join-Path $record.physicalPath "SKILL.md").ToLowerInvariant()
            if ($recordsByIdentity.Contains($identity)) {           # Preserve every alias without duplicating the physical asset.
                $existing = $recordsByIdentity[$identity]
                $existing.activePaths = @($existing.activePaths + $activePath | Sort-Object -Unique)
                $scopePriority = @{ UNKNOWN = 0; PROJECT = 1; USER = 2; SYSTEM = 3 } # Physical ownership outranks narrower compatibility aliases.
                if ($scopePriority[$record.scope] -gt $scopePriority[$existing.scope]) { $existing.scope = $record.scope }
            }
            else {
                $recordsByIdentity[$identity] = $record             # First observation owns immutable file and Git facts.
            }
        }
    }

    $records = @($recordsByIdentity.Values | Sort-Object name, physicalPath) # Stable ordering keeps Registry diffs reviewable.
    $nameGroups = @($records | Group-Object name | Where-Object Count -gt 1)
    foreach ($group in $nameGroups) {                               # Same name plus different physical identity is a collision.
        foreach ($record in $group.Group) {
            $record.status = if ($record.status -eq "BLOCKED") { "BLOCKED" } else { "UNKNOWN" }
            $record.issues = @($record.issues + "Name collision: $($group.Count) physical Skill entries use '$($group.Name)'.")
        }
    }

    $summary = [pscustomobject]@{
        total = $records.Count                                      # Total is deduplicated by physical entry identity.
        status = [pscustomobject]@{ PASS = @($records | Where-Object status -eq "PASS").Count; BLOCKED = @($records | Where-Object status -eq "BLOCKED").Count; UNKNOWN = @($records | Where-Object status -eq "UNKNOWN").Count }
        scope = [pscustomobject]@{ SYSTEM = @($records | Where-Object scope -eq "SYSTEM").Count; USER = @($records | Where-Object scope -eq "USER").Count; PROJECT = @($records | Where-Object scope -eq "PROJECT").Count; UNKNOWN = @($records | Where-Object scope -eq "UNKNOWN").Count }
        lifecycleMode = [pscustomobject]@{ PACKAGE = @($records | Where-Object lifecycleMode -eq "PACKAGE").Count; SOURCE = @($records | Where-Object lifecycleMode -eq "SOURCE").Count; HYBRID = @($records | Where-Object lifecycleMode -eq "HYBRID").Count; UNKNOWN = @($records | Where-Object lifecycleMode -eq "UNKNOWN").Count }
    }
    $registry = [pscustomobject]@{
        schemaVersion = 1                                          # Increment only when field semantics become incompatible.
        generatedAt = (Get-Date).ToString("o")                      # Local offset is retained for cross-session evidence.
        generator = "skill-lifecycle-manager/1.0.0"                # Generator version lets future migrations identify behavior.
        roots = @($rootRecords.Path | Sort-Object -Unique)          # Record exactly which live surfaces were inspected.
        summary = $summary                                          # Compact health and classification counts.
        skills = $records                                           # Full evidence records remain the Registry source of truth.
    }

    if ($WriteRegistry) {
        $registryRoot = [IO.Path]::GetFullPath($RegistryDirectory)   # Registry owns both canonical and mirror files.
        if (-not (Test-Path -LiteralPath $registryRoot)) { New-Item -ItemType Directory -Path $registryRoot -Force | Out-Null }
        $jsonPath = Join-Path $registryRoot "skills-registry.json"  # JSON remains the only editable machine state.
        $yamlPath = Join-Path $registryRoot "skills-registry.yaml"  # YAML is regenerated from the same in-memory object.
        Write-AtomicText -Path $jsonPath -Content (($registry | ConvertTo-Json -Depth 12) + "`n") -OwnerRoot $registryRoot
        Write-AtomicText -Path $yamlPath -Content (Convert-RegistryToYAML -Registry $registry) -OwnerRoot $registryRoot
    }
    return $registry                                                # Callers can inspect or test the same object that was persisted.
}
