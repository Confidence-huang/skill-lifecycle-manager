<#
Stable-operation commands for the installed Skill capability system.
`stabilize` records one immutable local baseline after the manager, Registry, activity junction,
generated reports, managed repositories, and latest complete backup are observed. `health` compares
the live machine against that baseline without fetching, rewriting the Registry, or changing Skills.
Call example: Save-SkillStabilityBaseline -RegistryDirectory "D:\registry" -BackupRoot "D:\backups" -ManagerRoot "D:\manager" -ActivityPath "D:\active\manager" -Apply
#>


# --- Hash deterministic text without creating a temporary file ---
function Get-TextSHA256 {
    param([Parameter(Mandatory)][string]$Text)                       # Caller supplies already normalized evidence text.

    $bytes = [Text.Encoding]::UTF8.GetBytes($Text)                  # UTF-8 gives the same fingerprint on every PowerShell 7 host.
    $algorithm = [Security.Cryptography.SHA256]::Create()           # SHA256 is used throughout backup and Registry evidence.
    try {
        return [Convert]::ToHexString($algorithm.ComputeHash($bytes)) # Uppercase hex matches Get-FileHash output.
    }
    finally {
        $algorithm.Dispose()                                        # Release the native hashing resource after one calculation.
    }
}


# --- Reduce one Registry to a stable live-inventory fingerprint ---
function Get-SkillInventoryFingerprint {
    param([Parameter(Mandatory)][object]$Registry)                   # Generated timestamps are deliberately excluded from identity.

    $facts = @($Registry.skills | Sort-Object physicalPath, name | ForEach-Object {
        [ordered]@{
            name = $_.name                                         # Exact frontmatter name detects additions and renames.
            physicalPath = $_.physicalPath                         # Physical identity detects moved or replaced entries.
            status = $_.status                                     # Structural evidence drift belongs in routine health.
            scope = $_.scope                                       # Ownership changes can alter update authority.
            lifecycleMode = $_.lifecycleMode                       # PACKAGE/SOURCE/HYBRID changes affect maintenance.
            commit = $_.commit                                     # Full Git SHA is the immutable source version.
            governanceState = $_.governanceState                   # Observed lifecycle state is retained without quality grading.
        }
    })
    return Get-TextSHA256 -Text ($facts | ConvertTo-Json -Depth 5 -Compress) # One digest makes canonical/live comparison cheap.
}


# --- Describe one activity entry and its exact target ---
function Get-SkillActivityFacts {
    param([Parameter(Mandatory)][string]$ActivityPath)               # The manager should be exposed through one junction.

    if (-not (Test-Path -LiteralPath $ActivityPath)) {
        return [pscustomobject]@{ exists = $false; path = [IO.Path]::GetFullPath($ActivityPath); linkType = $null; target = $null }
    }

    $item = Get-Item -Force -LiteralPath $ActivityPath              # `-Force` retains reparse-point metadata.
    $target = if ($item.LinkType) { [string]::Join(";", @($item.Target)) } else { $null }
    return [pscustomobject]@{
        exists = $true                                              # Entry exists independently from whether it targets the right source.
        path = [IO.Path]::GetFullPath($item.FullName)               # Normalized path is stable in the baseline.
        linkType = if ($item.LinkType) { [string]$item.LinkType } else { $null }
        target = $target                                            # Health resolves and checks this target against the manager root.
    }
}


# --- Capture local Git state for every source-managed repository ---
function Get-ManagedRepositorySnapshots {
    param([Parameter(Mandatory)][object]$Registry)                   # Registry supplies exact repository ownership and Skill names.

    $snapshots = [Collections.Generic.List[object]]::new()          # One repository may own several HYBRID Skill records.
    $groups = @($Registry.skills | Where-Object sourceRepository | Group-Object sourceRepository | Sort-Object Name)
    foreach ($group in $groups) {
        $root = [IO.Path]::GetFullPath($group.Name)                 # Physical repository path is the local update identity.
        if (-not (Test-Path -LiteralPath $root -PathType Container)) {
            $snapshots.Add([pscustomobject]@{ root = $root; exists = $false; branch = $null; commit = $null; remote = $null; isClean = $null; localStateFingerprint = $null; skills = @($group.Group.name | Sort-Object -Unique) })
            continue
        }

        $git = Get-GitFacts -Path $root                             # Shared Git probe provides branch, SHA, remote, and cleanliness.
        $status = @(& git -C $root status --porcelain=v1 --untracked-files=all 2>$null) # Color-free lines expose local dirty-state changes.
        $diff = @(& git -C $root diff --no-ext-diff --stat HEAD 2>$null) # A compact diff shape distinguishes more than clean/dirty alone.
        $localStateText = @($git.Commit, $git.Branch, $git.Remote, @($status), @($diff)) | ConvertTo-Json -Depth 4 -Compress
        $snapshots.Add([pscustomobject]@{
            root = $root                                            # Later health checks address the same physical repository.
            exists = $git.IsRepository                              # A missing `.git` is visible instead of becoming PACKAGE silently.
            branch = $git.Branch                                   # Branch is an update channel, not the frozen version.
            commit = $git.Commit                                   # Full commit SHA is the frozen local version.
            remote = $git.Remote                                   # Missing origin remains explicit.
            isClean = $git.IsClean                                 # Existing dirty repositories are recorded, not overwritten.
            localStateFingerprint = Get-TextSHA256 -Text $localStateText # Health detects local commit/status drift without fetch.
            skills = @($group.Group.name | Sort-Object -Unique)    # Human output shows which capabilities each repository owns.
        })
    }
    return @($snapshots)
}


# --- Find the newest backup that finished with a readable manifest ---
function Get-LatestCapabilityBackup {
    param([Parameter(Mandatory)][string]$BackupRoot)                 # Only timestamped AI capability backups below this root are eligible.

    if (-not (Test-Path -LiteralPath $BackupRoot -PathType Container)) { return $null }
    $candidates = [Collections.Generic.List[object]]::new()         # Invalid or incomplete directories never become recovery evidence.
    foreach ($directory in Get-ChildItem -LiteralPath $BackupRoot -Directory -Filter "ai-capabilities-*") {
        $manifestPath = Join-Path $directory.FullName "backup-manifest.json"
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { continue }
        try { $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json } catch { continue }
        if ($manifest.schemaVersion -ne 1) { continue }             # Restore supports only the known manifest contract.
        $candidates.Add([pscustomobject]@{
            path = [IO.Path]::GetFullPath($directory.FullName)      # Complete backup directory is the portable recovery unit.
            manifest = [IO.Path]::GetFullPath($manifestPath)        # Exact final manifest proves transaction completion.
            manifestSHA256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash
            createdAt = ([datetimeoffset]$manifest.createdAt).ToString("o") # Preserve an unambiguous offset instead of locale-formatted text.
            fileCount = @($manifest.files).Count                   # Counts make the health summary useful without rehashing 5.5 GB.
            linkCount = @($manifest.links).Count                    # Junction records remain separate from physical files.
        })
    }
    $latest = @($candidates | Sort-Object { [datetimeoffset]$_.createdAt } -Descending | Select-Object -First 1)
    if ($latest.Count -eq 0) { return $null }                       # Empty roots are a visible missing-backup gate for stabilize.
    return $latest[0]
}


# --- Validate an optional project's declared Skill working set ---
function Get-ProjectSkillProfileFacts {
    param(
        [string]$ProjectRoot,                                       # Omit the project to run global health only.
        [Parameter(Mandatory)][object]$Registry,                    # Exact names are checked against canonical live assets.
        [Parameter(Mandatory)][string]$BaselinePath                 # Project must inherit the same frozen global baseline.
    )

    if (-not $ProjectRoot) { return [pscustomobject]@{ status = "NOT_REQUESTED"; projectRoot = $null; profilePath = $null; declaredSkills = 0; missingSkills = @(); issues = @() } }
    $project = Get-CanonicalPath -Path $ProjectRoot                 # Project identity follows the same D-drive canonical-path rule.
    $profilePath = Join-Path $project "project-skill-profile.json"
    $issues = [Collections.Generic.List[string]]::new()             # Every profile defect is reported together for one repair pass.
    if (-not (Test-Path -LiteralPath (Join-Path $project "PROJECT_LOG.md") -PathType Leaf)) { $issues.Add("PROJECT_LOG.md is missing.") }
    if (-not (Test-Path -LiteralPath $profilePath -PathType Leaf)) {
        $issues.Add("project-skill-profile.json is missing.")
        return [pscustomobject]@{ status = "BLOCKED"; projectRoot = $project; profilePath = $profilePath; declaredSkills = 0; missingSkills = @(); issues = @($issues) }
    }

    try { $profile = Get-Content -Raw -LiteralPath $profilePath | ConvertFrom-Json } catch { $issues.Add("Profile JSON is invalid: $($_.Exception.Message)"); return [pscustomobject]@{ status = "BLOCKED"; projectRoot = $project; profilePath = $profilePath; declaredSkills = 0; missingSkills = @(); issues = @($issues) } }
    if ($profile.schemaVersion -ne 1) { $issues.Add("Unsupported project profile schema '$($profile.schemaVersion)'.") }
    if ([IO.Path]::GetFullPath([string]$profile.inherits.globalBaseline) -ne [IO.Path]::GetFullPath($BaselinePath)) { $issues.Add("Project profile points to a different global baseline.") }

    $declared = [Collections.Generic.List[string]]::new()           # Tier names express roles, never quality or usage grades.
    foreach ($tier in $profile.workingSet.PSObject.Properties) {
        foreach ($skillName in @($tier.Value)) { $declared.Add([string]$skillName) }
    }
    $registeredNames = @($Registry.skills.name | Sort-Object -Unique)
    $missing = @($declared | Sort-Object -Unique | Where-Object { $_ -notin $registeredNames })
    foreach ($skillName in $missing) { $issues.Add("Declared Skill '$skillName' is not present in the canonical Registry.") }
    return [pscustomobject]@{
        status = if ($issues.Count) { "BLOCKED" } else { "PASS" }
        projectRoot = $project                                     # Result tells users exactly which project was checked.
        profilePath = $profilePath                                 # Profile is configuration, not another Skill or Registry.
        declaredSkills = @($declared | Sort-Object -Unique).Count
        missingSkills = $missing
        issues = @($issues)
    }
}


# --- Freeze one explicit stable-use baseline ---
function Save-SkillStabilityBaseline {
    param(
        [Parameter(Mandatory)][string]$RegistryDirectory,           # Baseline lives beside, but does not replace, the canonical Registry.
        [Parameter(Mandatory)][string]$BackupRoot,                  # A complete recovery point is mandatory before freezing.
        [Parameter(Mandatory)][string]$ManagerRoot,                 # Clean manager Git commit becomes the implementation identity.
        [Parameter(Mandatory)][string]$ActivityPath,                # Active junction must resolve to that exact manager repository.
        [switch]$Apply                                              # Preview reports evidence; Apply writes one immutable baseline file.
    )

    $registryRoot = Get-CanonicalPath -Path $RegistryDirectory
    $manager = Get-CanonicalPath -Path $ManagerRoot
    $registryPath = Join-Path $registryRoot "skills-registry.json"
    $yamlPath = Join-Path $registryRoot "skills-registry.yaml"
    $capabilityReport = Join-Path $registryRoot "skill-capability-report.md"
    $governanceReport = Join-Path $registryRoot "skill-governance-report.md"
    $baselinePath = Join-Path $registryRoot "skill-stability-baseline.json"
    foreach ($requiredPath in @($registryPath, $yamlPath, $capabilityReport, $governanceReport)) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) { throw "BLOCKED: Stable baseline requires '$requiredPath'." }
    }
    if (Test-Path -LiteralPath $baselinePath) { throw "BLOCKED: Stability baseline already exists; preserve or archive it before an explicit rebaseline." }

    $managerGit = Get-GitFacts -Path $manager
    if (-not $managerGit.IsRepository -or -not $managerGit.Commit -or -not $managerGit.IsClean) { throw "BLOCKED: Manager source must be a clean Git repository with a committed HEAD." }
    $activity = Get-SkillActivityFacts -ActivityPath $ActivityPath
    if (-not $activity.exists -or $activity.linkType -ne "Junction") { throw "BLOCKED: Manager activity entry must be a junction." }
    $activityTarget = Get-CanonicalPath -Path $activity.target
    if ($activityTarget -ne $manager) { throw "BLOCKED: Manager activity junction targets '$activityTarget', not '$manager'." }
    $backup = Get-LatestCapabilityBackup -BackupRoot $BackupRoot
    if (-not $backup) { throw "BLOCKED: No complete version-1 AI capability backup is available." }

    $registry = Get-Content -Raw -LiteralPath $registryPath | ConvertFrom-Json
    $baseline = [ordered]@{
        schemaVersion = 1                                          # Health rejects unknown future stability contracts.
        createdAt = (Get-Date).ToString("o")
        operatingMode = "FROZEN_STABLE_USE"                       # Observe real work before more AI-OS redesign.
        boundaries = [ordered]@{
            automaticInstall = $false                              # New Skills remain explicit user-scoped operations.
            automaticUpdate = $false                               # Update candidates still pass existing detached gates.
            automaticDeletion = $false                             # No telemetry means no automatic retirement authority.
            automaticGrading = $false                              # Evidence readiness remains separate from quality.
            phase3Routing = $false                                 # Automatic capability dispatch is deliberately deferred.
        }
        manager = [ordered]@{ root = $manager; branch = $managerGit.Branch; commit = $managerGit.Commit; activityPath = $activity.path; activityLinkType = $activity.linkType; activityTarget = $activityTarget }
        registry = [ordered]@{
            jsonPath = $registryPath
            jsonSHA256 = (Get-FileHash -LiteralPath $registryPath -Algorithm SHA256).Hash
            yamlPath = $yamlPath
            yamlSHA256 = (Get-FileHash -LiteralPath $yamlPath -Algorithm SHA256).Hash
            generatedAt = $registry.generatedAt
            generator = $registry.generator
            roots = @($registry.roots)
            inventoryFingerprint = Get-SkillInventoryFingerprint -Registry $registry
            physicalEntries = $registry.summary.inventory.physicalEntries
            topLevelEntries = $registry.summary.inventory.topLevelEntries
            reviewRequired = $registry.summary.governanceState.REVIEW_REQUIRED
            overallRated = $registry.summary.assessmentCoverage.overallRated
        }
        reports = [ordered]@{
            capability = [ordered]@{ path = $capabilityReport; sha256 = (Get-FileHash -LiteralPath $capabilityReport -Algorithm SHA256).Hash }
            governance = [ordered]@{ path = $governanceReport; sha256 = (Get-FileHash -LiteralPath $governanceReport -Algorithm SHA256).Hash }
        }
        latestBackup = $backup                                     # Existing 5.5 GB recovery point remains the rollback evidence.
        managedRepositories = @(Get-ManagedRepositorySnapshots -Registry $registry)
        upstreamFreshness = "UNKNOWN_NOT_FETCHED"                 # Local stability never implies the remote has no new commits.
    }
    $result = [pscustomobject]@{ status = "PASS"; action = if ($Apply) { "STABILIZE" } else { "PREVIEW" }; baselinePath = $baselinePath; managerCommit = $managerGit.Commit; physicalEntries = $registry.summary.inventory.physicalEntries; reviewRequired = $registry.summary.governanceState.REVIEW_REQUIRED; sourceRepositories = @($baseline.managedRepositories).Count; latestBackup = $backup.path; operatingMode = $baseline.operatingMode }
    if (-not $Apply) { return $result }

    Write-AtomicText -Path $baselinePath -Content (($baseline | ConvertTo-Json -Depth 12) + "`n") -OwnerRoot $registryRoot
    $result.action = "STABILIZED"
    return $result                                                  # Feedback reports exactly which frozen evidence was written.
}


# --- Compare live state with the frozen baseline without mutation or fetch ---
function Get-SkillHealth {
    param(
        [Parameter(Mandatory)][string]$RegistryDirectory,           # Contains canonical Registry and immutable stability baseline.
        [Parameter(Mandatory)][string]$BackupRoot,                  # Used only to confirm the frozen backup still exists.
        [Parameter(Mandatory)][string]$ManagerRoot,                 # Current manager source is checked against its frozen commit.
        [Parameter(Mandatory)][string]$ActivityPath,                # Current active link must retain its frozen identity.
        [string]$ProjectRoot                                        # Optional project profile adds a real-work suitability smoke check.
    )

    $registryRoot = Get-CanonicalPath -Path $RegistryDirectory
    $baselinePath = Join-Path $registryRoot "skill-stability-baseline.json"
    if (-not (Test-Path -LiteralPath $baselinePath -PathType Leaf)) { throw "BLOCKED: Stability baseline is missing; run stabilize -Apply first." }
    $baseline = Get-Content -Raw -LiteralPath $baselinePath | ConvertFrom-Json
    if ($baseline.schemaVersion -ne 1) { throw "BLOCKED: Unsupported stability baseline schema '$($baseline.schemaVersion)'." }

    $checks = [Collections.Generic.List[object]]::new()             # Each PASS/BLOCKED fact remains independently inspectable.
    $isPowerShell7 = $PSVersionTable.PSEdition -eq "Core" -and $PSVersionTable.PSVersion.Major -ge 7
    $checks.Add([pscustomobject]@{ name = "powershell-runtime"; status = if ($isPowerShell7) { "PASS" } else { "BLOCKED" }; detail = "$($PSVersionTable.PSEdition) $($PSVersionTable.PSVersion)" })

    $registryPath = Join-Path $registryRoot "skills-registry.json"
    $yamlPath = Join-Path $registryRoot "skills-registry.yaml"
    $registryExists = (Test-Path -LiteralPath $registryPath -PathType Leaf) -and (Test-Path -LiteralPath $yamlPath -PathType Leaf)
    $registryHashMatches = $registryExists -and (Get-FileHash -LiteralPath $registryPath -Algorithm SHA256).Hash -eq $baseline.registry.jsonSHA256 -and (Get-FileHash -LiteralPath $yamlPath -Algorithm SHA256).Hash -eq $baseline.registry.yamlSHA256
    $checks.Add([pscustomobject]@{ name = "registry-files"; status = if ($registryHashMatches) { "PASS" } else { "BLOCKED" }; detail = if ($registryHashMatches) { "Canonical JSON and YAML match the frozen hashes." } else { "Registry files are missing or differ from the frozen hashes." } })
    if (-not $registryExists) { throw "BLOCKED: Canonical Registry files are missing." }
    $registry = Get-Content -Raw -LiteralPath $registryPath | ConvertFrom-Json

    $liveRegistry = Invoke-SkillScan -Paths @($baseline.registry.roots) -RegistryDirectory $registryRoot # Read-only scan compares physical capability identity.
    $canonicalFingerprint = Get-SkillInventoryFingerprint -Registry $registry
    $liveFingerprint = Get-SkillInventoryFingerprint -Registry $liveRegistry
    $inventoryMatches = $canonicalFingerprint -eq $baseline.registry.inventoryFingerprint -and $liveFingerprint -eq $canonicalFingerprint
    $checks.Add([pscustomobject]@{ name = "live-inventory"; status = if ($inventoryMatches) { "PASS" } else { "BLOCKED" }; detail = if ($inventoryMatches) { "$($liveRegistry.summary.inventory.physicalEntries) physical / $($liveRegistry.summary.inventory.topLevelEntries) top-level entries match." } else { "Live inventory differs from the canonical or frozen fingerprint." } })

    $manager = Get-GitFacts -Path (Get-CanonicalPath -Path $ManagerRoot)
    $managerMatches = $manager.IsRepository -and $manager.IsClean -and $manager.Commit -eq $baseline.manager.commit
    $checks.Add([pscustomobject]@{ name = "manager-git"; status = if ($managerMatches) { "PASS" } else { "BLOCKED" }; detail = "HEAD=$($manager.Commit); clean=$($manager.IsClean)" })
    $activity = Get-SkillActivityFacts -ActivityPath $ActivityPath
    $activityTarget = if ($activity.target) { Get-CanonicalPath -Path $activity.target } else { $null }
    $activityMatches = $activity.exists -and $activity.linkType -eq $baseline.manager.activityLinkType -and $activityTarget -eq $baseline.manager.activityTarget
    $checks.Add([pscustomobject]@{ name = "manager-activity"; status = if ($activityMatches) { "PASS" } else { "BLOCKED" }; detail = "$($activity.linkType) -> $activityTarget" })

    foreach ($report in @($baseline.reports.capability, $baseline.reports.governance)) {
        $reportMatches = (Test-Path -LiteralPath $report.path -PathType Leaf) -and (Get-FileHash -LiteralPath $report.path -Algorithm SHA256).Hash -eq $report.sha256
        $checks.Add([pscustomobject]@{ name = "generated-report"; status = if ($reportMatches) { "PASS" } else { "BLOCKED" }; detail = [string]$report.path })
    }

    $baselineRepositories = @($baseline.managedRepositories)
    $liveRepositories = @(Get-ManagedRepositorySnapshots -Registry $registry)
    $repositoryDrift = [Collections.Generic.List[string]]::new()
    foreach ($frozen in $baselineRepositories) {
        $live = @($liveRepositories | Where-Object root -eq $frozen.root)
        if ($live.Count -ne 1 -or $live[0].commit -ne $frozen.commit -or $live[0].localStateFingerprint -ne $frozen.localStateFingerprint) { $repositoryDrift.Add([string]$frozen.root) }
    }
    $sourceMatches = $repositoryDrift.Count -eq 0 -and $liveRepositories.Count -eq $baselineRepositories.Count
    $checks.Add([pscustomobject]@{ name = "local-source-state"; status = if ($sourceMatches) { "PASS" } else { "BLOCKED" }; detail = if ($sourceMatches) { "$($liveRepositories.Count) repositories match local frozen commits and status fingerprints." } else { "Local drift: $([string]::Join('; ', @($repositoryDrift)))" } })

    $latestBackup = Get-LatestCapabilityBackup -BackupRoot $BackupRoot # Newer complete backups are reported without changing the baseline.
    $backupManifest = [string]$baseline.latestBackup.manifest
    $backupMatches = (Test-Path -LiteralPath $backupManifest -PathType Leaf) -and (Get-FileHash -LiteralPath $backupManifest -Algorithm SHA256).Hash -eq $baseline.latestBackup.manifestSHA256
    $checks.Add([pscustomobject]@{ name = "recovery-manifest"; status = if ($backupMatches -and $latestBackup) { "PASS" } else { "BLOCKED" }; detail = if ($latestBackup) { "frozen=$($baseline.latestBackup.path); latest=$($latestBackup.path)" } else { "No complete backup remains under '$BackupRoot'." } })

    $project = Get-ProjectSkillProfileFacts -ProjectRoot $ProjectRoot -Registry $registry -BaselinePath $baselinePath
    if ($project.status -ne "NOT_REQUESTED") { $checks.Add([pscustomobject]@{ name = "project-skill-profile"; status = $project.status; detail = if ($project.status -eq "PASS") { "$($project.declaredSkills) declared Skills are present." } else { [string]::Join("; ", @($project.issues)) } }) }
    $blockedChecks = @($checks | Where-Object status -eq "BLOCKED")
    return [pscustomobject]@{
        status = if ($blockedChecks.Count) { "BLOCKED" } else { "PASS" }
        action = "HEALTH_CHECKED"                                 # Command is read-only even though it inspects live Git and files.
        operatingMode = $baseline.operatingMode
        baselineCreatedAt = $baseline.createdAt
        physicalEntries = $liveRegistry.summary.inventory.physicalEntries
        topLevelEntries = $liveRegistry.summary.inventory.topLevelEntries
        reviewRequired = $liveRegistry.summary.governanceState.REVIEW_REQUIRED
        localSourceDrift = $repositoryDrift.Count
        latestBackup = if ($latestBackup) { $latestBackup } else { $baseline.latestBackup }
        upstreamFreshness = "UNKNOWN_NOT_FETCHED"                 # No network mutation or fetch occurs in routine health.
        automaticActions = $baseline.boundaries
        project = $project
        checks = @($checks)
        mutations = 0                                              # Explicit proof that health did not write or update assets.
    }
}
