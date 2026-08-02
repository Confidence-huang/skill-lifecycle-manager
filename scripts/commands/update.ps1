<#
Validated fast-forward updates for SOURCE and HYBRID Registry assets.
The command fetches first, validates the candidate in a detached temporary worktree, and changes the
managed repository only through a final fast-forward merge.
Call example: Update-SkillAsset -Name "hop" -RegistryDirectory "D:\CodexProjects\_skills\registry" -Apply
#>


# --- Resolve the configured upstream ref for one repository ---
function Get-UpdateRef {
    param(
        [Parameter(Mandatory)][string]$Repository,                  # Clean source repository selected from the Registry.
        [string]$RequestedRef                                       # Optional explicit branch, tag, or full commit.
    )

    if ($RequestedRef) { return $RequestedRef }                     # User-supplied candidate takes precedence over branch configuration.
    $branch = ((& git -C $Repository branch --show-current 2>$null) -join "").Trim()
    if (-not $branch) { throw "BLOCKED: Detached repository requires -Ref." }
    $upstream = ((& git -C $Repository for-each-ref --format="%(upstream:short)" "refs/heads/$branch" 2>$null) -join "").Trim()
    if (-not $upstream) { throw "BLOCKED: Branch '$branch' has no configured upstream; specify -Ref." }
    return $upstream                                                # Usually `origin/main`, retained as the update channel.
}


# --- Validate one fetched candidate without changing the active worktree ---
function Test-UpdateCandidate {
    param(
        [Parameter(Mandatory)][string]$Repository,                  # Physical source repository that owns the active Skill.
        [Parameter(Mandatory)][string]$CandidateCommit,             # Full fetched SHA selected for possible fast-forward.
        [Parameter(Mandatory)][string]$StagingHome                  # Detached worktree lives under this cleanup boundary.
    )

    New-Item -ItemType Directory -Path $StagingHome -Force | Out-Null
    $worktree = Join-Path $StagingHome ("update-" + [guid]::NewGuid().ToString("N")) # Unique candidate prevents cross-update leakage.
    Assert-PathWithinRoot -Path $worktree -Root $StagingHome
    try {
        & git -C $Repository worktree add --detach $worktree $CandidateCommit | Out-Null # Internal Git progress must not pollute the result object.
        if ($LASTEXITCODE -ne 0) { throw "BLOCKED: Could not create detached candidate worktree." }
        $entries = @(Get-SkillEntryFiles -Root $worktree)           # Validate every eligible Skill supplied by this repository.
        if ($entries.Count -eq 0) { throw "BLOCKED: Candidate contains no eligible SKILL.md entry." }
        foreach ($entry in $entries) {
            $metadata = Read-SkillMetadata -SkillFile $entry.FullName
            if ($metadata.Status -ne "PASS") { throw "BLOCKED: Candidate entry '$($entry.FullName)' failed validation: $($metadata.Issues -join '; ')" }
        }
        return [pscustomobject]@{ Status = "PASS"; EntryCount = $entries.Count; Worktree = $worktree }
    }
    finally {
        if (Test-Path -LiteralPath $worktree) {
            & git -C $Repository worktree remove --force $worktree 2>$null | Out-Null # Remove Git bookkeeping before filesystem fallback cleanup.
            if (Test-Path -LiteralPath $worktree) { Remove-Item -LiteralPath $worktree -Recurse -Force }
        }
    }
}


# --- Update selected source-managed Registry assets ---
function Update-SkillAsset {
    param(
        [Parameter(Mandatory)][string]$Name,                         # One Registry name or `all` for every eligible source repository.
        [string]$Ref,                                                # Optional candidate ref; all selected repositories must resolve it.
        [Parameter(Mandatory)][string]$RegistryDirectory,           # Canonical JSON Registry selects exact source paths.
        [Parameter(Mandatory)][string]$StagingHome,                 # Candidate worktrees stay outside live repositories.
        [switch]$Apply                                               # Preview fetches and validates; apply adds the final fast-forward.
    )

    $registryPath = Join-Path $RegistryDirectory "skills-registry.json"
    if (-not (Test-Path -LiteralPath $registryPath -PathType Leaf)) { throw "BLOCKED: Canonical Registry is missing; run registry -Apply first." }
    $registry = Get-Content -Raw -LiteralPath $registryPath | ConvertFrom-Json # JSON is canonical; generated YAML is never read as state.
    $eligible = @($registry.skills | Where-Object { $_.lifecycleMode -in @("SOURCE", "HYBRID") -and $_.sourceRepository })
    $selected = @(if ($Name -eq "all") { $eligible } else { $eligible | Where-Object name -eq $Name }) # Preserve Count for zero, one, or many matches.
    if ($selected.Count -eq 0) { throw "BLOCKED: No eligible source-managed Registry entry matched '$Name'." }
    if ($Name -ne "all" -and $selected.Count -gt 1) { throw "BLOCKED: Registry name '$Name' maps to multiple physical entries." }

    $repositories = @($selected | Group-Object sourceRepository | ForEach-Object { $_.Group[0] }) # Update each physical repository once.
    $results = [Collections.Generic.List[object]]::new()
    foreach ($asset in $repositories) {
        $repository = [string]$asset.sourceRepository              # Preserve the Registry path if canonicalization itself fails.
        try {
            $repository = Get-CanonicalPath -Path $repository
            $git = Get-GitFacts -Path $repository
            if (-not $git.IsRepository) { throw "BLOCKED: Registry source is no longer a Git repository: $repository" }
            if (-not $git.IsClean) { throw "BLOCKED: Source worktree is dirty: $repository" }
            if (-not $git.Remote) { throw "BLOCKED: Source repository has no origin remote: $repository" }

            & git -C $repository fetch --prune origin | Out-Null   # Fetch changes refs but leaves the active worktree and branch untouched.
            if ($LASTEXITCODE -ne 0) { throw "BLOCKED: Fetch failed for '$repository'." }
            $candidateRef = Get-UpdateRef -Repository $repository -RequestedRef $Ref
            $candidateCommit = ((& git -C $repository rev-parse $candidateRef 2>$null) -join "").Trim()
            if (-not $candidateCommit) { throw "BLOCKED: Candidate ref '$candidateRef' is unreadable in '$repository'." }
            & git -C $repository merge-base --is-ancestor $git.Commit $candidateCommit
            if ($LASTEXITCODE -ne 0) { throw "BLOCKED: Candidate '$candidateRef' is not a fast-forward from $($git.Commit)." }

            $validation = Test-UpdateCandidate -Repository $repository -CandidateCommit $candidateCommit -StagingHome $StagingHome
            $behind = [int](((& git -C $repository rev-list --count "$($git.Commit)..$candidateCommit") -join "").Trim())
            $result = [pscustomobject]@{
                status = "PASS"                                    # Fetch, ancestry, and detached candidate validation all passed.
                action = if ($Apply -and $behind -gt 0) { "UPDATED" } elseif ($behind -eq 0) { "CURRENT" } else { "PREVIEW" }
                name = $asset.name
                repository = $repository
                previousCommit = $git.Commit
                candidateCommit = $candidateCommit
                commitsBehind = $behind
                validatedEntries = $validation.EntryCount
                error = $null                                      # A common result shape simplifies batch consumers.
            }
            if ($Apply -and $behind -gt 0) {
                & git -C $repository merge --ff-only $candidateCommit | Out-Null # The only worktree mutation happens after candidate validation.
                if ($LASTEXITCODE -ne 0) { throw "BLOCKED: Final fast-forward failed for '$repository'." }
            }
            $results.Add($result)
        }
        catch {
            if ($Name -ne "all") { throw }                         # A named target preserves strict fail-fast command semantics.
            $results.Add([pscustomobject]@{
                status = "BLOCKED"                                 # One repository lacks a mutation gate; other repositories remain eligible.
                action = "SKIPPED"
                name = $asset.name
                repository = $repository
                previousCommit = $asset.commit
                candidateCommit = $null
                commitsBehind = $null
                validatedEntries = 0
                error = $_.Exception.Message
            })
        }
    }

    if ($Apply) {
        $null = Invoke-SkillScan -RegistryDirectory $RegistryDirectory -WriteRegistry # Refresh commit and branch evidence after all updates.
    }
    return @($results)
}
