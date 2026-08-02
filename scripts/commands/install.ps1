<#
Transactional Skill installation from a local directory or complete Git source.
PACKAGE copies one self-contained Skill; SOURCE keeps a complete one-entry repository; HYBRID keeps
the complete repository and activates one selected entry through a junction.
Call example: Install-SkillAsset -Source "https://github.com/owner/repo.git" -Mode Source -Apply
#>


# --- Select one Skill entry from an inspected source ---
function Select-InstallEntry {
    param(
        [Parameter(Mandatory)][string]$InspectedRoot,                # Local directory or temporary full clone used for classification.
        [string]$SkillPath                                          # Required when multiple eligible entries are present.
    )

    $entries = @(Get-SkillEntryFiles -Root $InspectedRoot)          # Ignore embedded examples and test fixtures consistently with scan.
    if ($entries.Count -eq 0) { throw "BLOCKED: Source contains no eligible SKILL.md entry." }
    if ($SkillPath) {
        $selectedRoot = Join-Path $InspectedRoot $SkillPath          # User-selected path is resolved inside the inspected source.
        Assert-PathWithinRoot -Path $selectedRoot -Root $InspectedRoot
        $selectedFile = Join-Path $selectedRoot "SKILL.md"          # `-SkillPath` names the Skill directory, not the file itself.
        if (-not (Test-Path -LiteralPath $selectedFile -PathType Leaf)) { throw "BLOCKED: -SkillPath does not contain SKILL.md." }
        return Get-Item -LiteralPath $selectedFile
    }
    if ($entries.Count -gt 1) { throw "BLOCKED: Source contains $($entries.Count) eligible Skill entries; specify -SkillPath." }
    return $entries[0]                                              # A single eligible entry is unambiguous.
}


# --- Inspect the source in a transaction-owned staging directory ---
function Get-InstallInspection {
    param(
        [Parameter(Mandatory)][string]$Source,                       # Existing local directory or Git remote URL.
        [Parameter(Mandatory)][string]$StagingHome,                  # All temporary clones stay under this narrow cleanup root.
        [string]$Ref                                                 # Optional branch, tag, or commit to inspect and install.
    )

    New-Item -ItemType Directory -Path $StagingHome -Force | Out-Null # First use creates the dedicated transaction root.
    if (Test-Path -LiteralPath $Source -PathType Container) {
        return [pscustomobject]@{ Root = Get-CanonicalPath $Source; Temporary = $false; SourceKind = "LOCAL" }
    }

    $stage = Join-Path $StagingHome ("inspect-" + [guid]::NewGuid().ToString("N")) # Unique destination prevents cross-install contamination.
    Assert-PathWithinRoot -Path $stage -Root $StagingHome            # Cleanup is authorized only for this staging subtree.
    try {
        & git clone --no-checkout -- $Source $stage | Out-Null       # Keep the complete Git repository instead of a ZIP snapshot.
        if ($LASTEXITCODE -ne 0) { throw "BLOCKED: Git clone failed for '$Source'." }
        & git -C $stage checkout $(if ($Ref) { $Ref } else { "HEAD" }) | Out-Null # Materialize the requested ref before entry discovery.
        if ($LASTEXITCODE -ne 0) { throw "BLOCKED: Git ref '$Ref' could not be checked out." }
        return [pscustomobject]@{ Root = $stage; Temporary = $true; SourceKind = "GIT" }
    }
    catch {
        if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force } # Failed inspection never leaves hidden staging state.
        throw
    }
}


# --- Install one Skill asset ---
function Install-SkillAsset {
    param(
        [Parameter(Mandatory)][string]$Source,                       # Local directory or Git URL named by the user.
        [ValidateSet("Auto", "Package", "Source", "Hybrid")][string]$Mode = "Auto",
        [string]$Name,                                               # Optional activity name override; frontmatter is preferred.
        [string]$SkillPath,                                          # Relative Skill directory for a multi-entry repository.
        [string]$Ref,                                                # Optional Git ref, resolved to a full commit after clone.
        [Parameter(Mandatory)][string]$SkillHome,                    # Physical packages and source/hybrid activity junctions live here.
        [Parameter(Mandatory)][string]$SourceHome,                   # Complete Git repositories live outside activity roots.
        [Parameter(Mandatory)][string]$StagingHome,                  # Temporary inspection and clone paths are transaction-owned.
        [Parameter(Mandatory)][string]$RegistryDirectory,           # Successful installation regenerates canonical state.
        [switch]$Apply                                               # Without -Apply return the exact plan and leave final state unchanged.
    )

    $inspection = $null                                             # Finally cleanup needs to know whether inspection created a clone.
    $createdPaths = [Collections.Generic.List[string]]::new()       # Roll back only paths this transaction actually created.
    try {
        $inspection = Get-InstallInspection -Source $Source -StagingHome $StagingHome -Ref $Ref
        $selectedFile = Select-InstallEntry -InspectedRoot $inspection.Root -SkillPath $SkillPath
        $selectedRoot = Split-Path -Parent $selectedFile.FullName   # Physical entry used for validation and activity target.
        $metadata = Read-SkillMetadata -SkillFile $selectedFile.FullName
        if ($metadata.Status -ne "PASS") { throw "BLOCKED: Selected SKILL.md failed validation: $($metadata.Issues -join '; ')" }

        $git = Get-GitFacts -Path $inspection.Root                  # Git presence separates package copies from source-managed assets.
        $entryCount = @(Get-SkillEntryFiles -Root $inspection.Root).Count
        $resolvedMode = $Mode.ToUpperInvariant()
        if ($resolvedMode -eq "AUTO") {
            $resolvedMode = if (-not $git.IsRepository) { "PACKAGE" } elseif ($entryCount -eq 1 -and $selectedRoot.TrimEnd("\") -eq $git.Root.TrimEnd("\")) { "SOURCE" } else { "HYBRID" }
        }
        if ($resolvedMode -in @("SOURCE", "HYBRID") -and -not $git.IsRepository) { throw "BLOCKED: $resolvedMode mode requires a complete Git repository." }
        if ($resolvedMode -eq "SOURCE" -and ($entryCount -ne 1 -or $selectedRoot.TrimEnd("\") -ne $git.Root.TrimEnd("\"))) { throw "BLOCKED: Source mode requires one repository-root Skill; use Hybrid." }

        $activityName = if ($Name) { $Name } else { $metadata.Name } # Frontmatter remains the default discovery identity.
        if ($activityName -notmatch "^[a-z0-9-]{1,64}$") { throw "BLOCKED: Activity name must use 1-64 lowercase letters, digits, or hyphens." }
        $activityPath = Join-Path $SkillHome $activityName           # Collision checks happen before final state mutation.
        Assert-PathWithinRoot -Path $activityPath -Root $SkillHome   # A validated name still receives an explicit containment proof.
        if (Test-Path -LiteralPath $activityPath) { throw "BLOCKED: Activity path already exists: $activityPath" }

        $repositoryName = ([IO.Path]::GetFileName(($Source.TrimEnd("/", "\")))).Replace(".git", "")
        if (-not $repositoryName) { $repositoryName = $activityName } # Local root paths may not expose a URL-like repository name.
        if ($repositoryName -notmatch "^[A-Za-z0-9._-]+$" -or $repositoryName -in @(".", "..")) { $repositoryName = $activityName }
        $sourcePath = if ($resolvedMode -eq "PACKAGE") { $null } else { Join-Path $SourceHome $repositoryName }
        if ($sourcePath) { Assert-PathWithinRoot -Path $sourcePath -Root $SourceHome } # Repository leaf cannot redirect outside source home.
        if ($sourcePath -and (Test-Path -LiteralPath $sourcePath)) { throw "BLOCKED: Source repository path already exists: $sourcePath" }

        $plan = [pscustomobject]@{
            status = "PASS"                                        # Inspection and validation established an executable plan.
            action = if ($Apply) { "INSTALL" } else { "PREVIEW" }
            name = $activityName
            lifecycleMode = $resolvedMode
            source = $Source
            selectedSkill = $selectedRoot
            sourceDestination = $sourcePath
            activityDestination = $activityPath
            commit = $git.Commit                                    # Full SHA pins the inspected Git candidate.
        }
        if (-not $Apply) { return $plan }                            # Preview leaves only a temporary clone that finally removes.

        New-Item -ItemType Directory -Path $SkillHome -Force | Out-Null
        if ($resolvedMode -eq "PACKAGE") {
            New-Item -ItemType Directory -Path $activityPath | Out-Null # Create the transaction-owned package root before copying contents.
            $createdPaths.Add($activityPath)
            Get-ChildItem -Force -LiteralPath $selectedRoot | Where-Object Name -ne ".git" | Copy-Item -Destination $activityPath -Recurse -Force # Package mode deliberately omits repository metadata.
            $originRecord = [pscustomobject]@{
                schemaVersion = 1                                  # Scanner validates this small installed-package provenance contract.
                lifecycleMode = "PACKAGE"
                origin = $Source                                    # Retain the user-supplied local path or Git URL without claiming trust.
                remote = $git.Remote                                # Git origin is recorded when the inspected source provides one.
                commit = $git.Commit                                # Full SHA pins the package source snapshot when Git is available.
                selectedSkillPath = [IO.Path]::GetRelativePath($inspection.Root, $selectedRoot)
                installedAt = (Get-Date).ToString("o")
            }
            $originPath = Join-Path $activityPath ".skill-lifecycle.json"
            Write-AtomicText -Path $originPath -Content (($originRecord | ConvertTo-Json -Depth 6) + "`n") -OwnerRoot $activityPath # Provenance travels with the copied package.
        }
        else {
            New-Item -ItemType Directory -Path $SourceHome -Force | Out-Null
            & git clone --no-hardlinks -- $inspection.Root $sourcePath | Out-Null # Preserve a complete independent source repository and history.
            if ($LASTEXITCODE -ne 0) { throw "Git clone into source home failed." }
            $createdPaths.Add($sourcePath)
            if ($Ref) { & git -C $sourcePath checkout $Ref | Out-Null; if ($LASTEXITCODE -ne 0) { throw "Installed repository could not checkout '$Ref'." } }
            $installedCommit = ((& git -C $sourcePath rev-parse HEAD) -join "").Trim() # Resolve the installed version to immutable evidence.
            if (-not $installedCommit) { throw "Installed repository has no readable commit SHA." }

            $relativeSkill = [IO.Path]::GetRelativePath($inspection.Root, $selectedRoot) # Map the inspected entry into the final clone.
            $installedSkill = if ($relativeSkill -eq ".") { $sourcePath } else { Join-Path $sourcePath $relativeSkill }
            $installedMetadata = Read-SkillMetadata -SkillFile (Join-Path $installedSkill "SKILL.md")
            if ($installedMetadata.Status -ne "PASS") { throw "Installed Skill failed post-clone validation." }
            New-Item -ItemType Junction -Path $activityPath -Target $installedSkill | Out-Null # Activate only after source validation passes.
            $createdPaths.Add($activityPath)
            $plan.commit = $installedCommit                         # Report the exact final clone rather than the inspection copy.
        }

        $null = Invoke-SkillScan -Paths @($SkillHome) -RegistryDirectory $RegistryDirectory -WriteRegistry # State reflects the installed activity entry.
        $plan.status = "PASS"
        $plan.action = "INSTALLED"
        return $plan
    }
    catch {
        for ($index = $createdPaths.Count - 1; $index -ge 0; $index -= 1) {
            $path = $createdPaths[$index]                            # Reverse creation order removes activity junction before source data.
            if (Test-Path -LiteralPath $path) {
                $root = if ($path.StartsWith([IO.Path]::GetFullPath($SkillHome), [StringComparison]::OrdinalIgnoreCase)) { $SkillHome } else { $SourceHome }
                Assert-PathWithinRoot -Path $path -Root $root        # Cleanup cannot escape the activity or source home.
                $item = Get-Item -Force -LiteralPath $path
                if ($item.LinkType) { Remove-Item -LiteralPath $path -Force } else { Remove-Item -LiteralPath $path -Recurse -Force } # Never recurse through a junction target.
            }
        }
        throw
    }
    finally {
        if ($inspection -and $inspection.Temporary -and (Test-Path -LiteralPath $inspection.Root)) {
            Assert-PathWithinRoot -Path $inspection.Root -Root $StagingHome
            Remove-Item -LiteralPath $inspection.Root -Recurse -Force # Temporary inspection clones never become hidden active state.
        }
    }
}
