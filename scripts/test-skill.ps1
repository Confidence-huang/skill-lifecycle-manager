<#
End-to-end fixture tests for scan, Registry, package install, source update, backup, and restore.
Every artifact lives under one uniquely named temporary root and is removed in a final cleanup block.
Call example: pwsh -NoProfile -File .\test-skill.ps1
#>

[CmdletBinding()]
param([string]$TestParent = ([IO.Path]::GetTempPath()))              # Callers may redirect fixtures into a project work directory.

$ErrorActionPreference = "Stop"                                    # One failed assertion stops the suite with a non-zero exit.
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptRoot "skill-state.ps1")                         # Test the same shared functions loaded by the CLI.
. (Join-Path $scriptRoot "commands\governance.ps1")
. (Join-Path $scriptRoot "commands\scan.ps1")
. (Join-Path $scriptRoot "commands\report.ps1")
. (Join-Path $scriptRoot "commands\install.ps1")
. (Join-Path $scriptRoot "commands\update.ps1")
. (Join-Path $scriptRoot "commands\backup.ps1")
. (Join-Path $scriptRoot "commands\restore.ps1")


# --- Assert one test condition ---
function Assert-Test {
    param([Parameter(Mandatory)][bool]$Condition, [Parameter(Mandatory)][string]$Message)
    if (-not $Condition) { throw "TEST FAILED: $Message" }          # Preserve the first concrete broken contract.
}


# --- Write one minimal valid Skill entry ---
function New-TestSkill {
    param(
        [Parameter(Mandatory)][string]$Root,                        # Fixture Skill directory owned by this isolated test run.
        [Parameter(Mandatory)][string]$Name,                        # Frontmatter name supplies deterministic identity.
        [string]$Description = "Test Skill named $Name for lifecycle fixtures." # Optional domain text exercises governance classification.
    )
    New-Item -ItemType Directory -Path $Root -Force | Out-Null      # Fixture roots are transaction-owned and may be nested.
    $content = "---`nname: $Name`ndescription: $Description`n---`n`n# $Name`n"
    [IO.File]::WriteAllText((Join-Path $Root "SKILL.md"), $content, [Text.UTF8Encoding]::new($false)) # Emit strict UTF-8 frontmatter.
}


# --- Commit all current fixture files ---
function Save-TestRepository {
    param([Parameter(Mandatory)][string]$Repository, [string]$Message = "test fixture")
    $fixturePaths = [Collections.Generic.List[string]]::new()       # Stage only fixture paths that this test created.
    if (Test-Path -LiteralPath (Join-Path $Repository "SKILL.md")) { $fixturePaths.Add("SKILL.md") }
    if (Test-Path -LiteralPath (Join-Path $Repository "skills")) { $fixturePaths.Add("skills") }
    if ($fixturePaths.Count -eq 0) { throw "Fixture repository has no expected Skill paths." }
    & git -C $Repository add -- @($fixturePaths)                    # Avoid broad staging even inside an isolated test repository.
    & git -C $Repository commit -m $Message | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Fixture Git commit failed." }
}


# --- Run all lifecycle fixtures ---
$suiteError = $null                                                 # Preserve product-test failures even if Windows cleanup also fails.
$suiteResult = $null                                                # Emit PASS only after fixture cleanup succeeds.
$testRoot = Join-Path ([IO.Path]::GetFullPath($TestParent)) ("skill-lifecycle-manager-tests-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
try {
    $scanRoot = Join-Path $testRoot "scan-root"
    $packageRoot = Join-Path $scanRoot "package-one"
    New-TestSkill -Root $packageRoot -Name "package-one" -Description "Create presentation slides and PowerPoint documents for governance fixtures." # No Git owner should classify as PACKAGE.

    $sourceRoot = Join-Path $scanRoot "source-one"
    New-TestSkill -Root $sourceRoot -Name "source-one"
    & git -C $sourceRoot init -b main | Out-Null
    & git -C $sourceRoot config user.name "Skill Lifecycle Test"
    & git -C $sourceRoot config user.email "skill-lifecycle-test@example.invalid"
    Save-TestRepository -Repository $sourceRoot

    $hybridRoot = Join-Path $scanRoot "hybrid-repository"
    New-TestSkill -Root (Join-Path $hybridRoot "skills\hybrid-a") -Name "hybrid-a"
    New-TestSkill -Root (Join-Path $hybridRoot "skills\hybrid-b") -Name "hybrid-b"
    & git -C $hybridRoot init -b main | Out-Null
    & git -C $hybridRoot config user.name "Skill Lifecycle Test"
    & git -C $hybridRoot config user.email "skill-lifecycle-test@example.invalid"
    Save-TestRepository -Repository $hybridRoot

    $registryRoot = Join-Path $testRoot "registry"
    $registry = Invoke-SkillScan -Paths @($scanRoot) -RegistryDirectory $registryRoot -WriteRegistry
    Assert-Test ($registry.summary.total -eq 4) "Scan should discover four eligible physical Skills."
    Assert-Test ($registry.summary.inventory.physicalEntries -eq 4 -and $registry.summary.inventory.uniqueNames -eq 4) "Inventory views should distinguish physical entries from exact names."
    Assert-Test ($registry.summary.inventory.topLevelEntries -eq 2 -and $registry.summary.inventory.nestedEntries -eq 2) "Inventory should distinguish top-level entries from nested repository Skills."
    $governedPackage = @($registry.skills | Where-Object name -eq "package-one")[0]
    Assert-Test ($governedPackage.isTopLevel -and $governedPackage.governanceState -eq "AVAILABLE") "Top-level PASS package should remain available."
    Assert-Test ($governedPackage.capabilityDomains -contains "documents-presentations" -and $governedPackage.capabilityEvidence.Count -gt 0) "Lexical capability classification did not retain its evidence."
    Assert-Test ($governedPackage.evidenceReadinessScore -eq 75 -and $governedPackage.evidenceTier -eq "PARTIAL_EVIDENCE") "Historical package evidence readiness was scored incorrectly."
    Assert-Test ($governedPackage.overallGrade -eq "UNRATED" -and $governedPackage.usageEvidence -eq "UNKNOWN_NO_TELEMETRY") "Missing usage evidence was converted into an invented grade."
    Assert-Test (@($registry.skills | Where-Object { $_.name -like "hybrid-*" -and -not $_.isTopLevel -and $_.governanceState -eq "REVIEW_REQUIRED" }).Count -eq 2) "Nested provenance gaps should enter the review queue."
    Assert-Test ($registry.summary.assessmentCoverage.qualityKnown -eq 0 -and $registry.summary.assessmentCoverage.usageKnown -eq 0 -and $registry.summary.assessmentCoverage.securityKnown -eq 0) "Unknown assessment coverage must remain explicit."
    Assert-Test ($registry.summary.capabilityDomain."documents-presentations" -eq 1) "Capability-domain summary does not match the classified fixture."
    Assert-Test (@($registry.skills | Where-Object { $_.name -eq "package-one" -and $_.lifecycleMode -eq "PACKAGE" }).Count -eq 1) "Package classification failed."
    Assert-Test (@($registry.skills | Where-Object { $_.name -eq "source-one" -and $_.lifecycleMode -eq "SOURCE" }).Count -eq 1) "Source classification failed."
    Assert-Test (@($registry.skills | Where-Object { $_.name -like "hybrid-*" -and $_.lifecycleMode -eq "HYBRID" }).Count -eq 2) "Hybrid classification failed."
    Assert-Test (Test-Path -LiteralPath (Join-Path $registryRoot "skills-registry.json")) "Canonical JSON Registry was not written."
    Assert-Test (Test-Path -LiteralPath (Join-Path $registryRoot "skills-registry.yaml")) "YAML Registry mirror was not written."
    $reportPreview = Write-SkillCapabilityReport -RegistryDirectory $registryRoot
    Assert-Test ($reportPreview.action -eq "PREVIEW" -and -not (Test-Path -LiteralPath $reportPreview.reportPath)) "Report preview unexpectedly wrote a file."
    $reportResult = Write-SkillCapabilityReport -RegistryDirectory $registryRoot -Apply
    Assert-Test ($reportResult.action -eq "REPORTED" -and (Test-Path -LiteralPath $reportResult.reportPath)) "Capability report was not generated."
    $governancePreview = Write-SkillGovernanceReport -Registry $registry -RegistryDirectory $registryRoot
    Assert-Test ($governancePreview.action -eq "PREVIEW" -and -not (Test-Path -LiteralPath $governancePreview.reportPath)) "Governance preview unexpectedly wrote a file."
    $governanceResult = Write-SkillGovernanceReport -Registry $registry -RegistryDirectory $registryRoot -Apply
    Assert-Test ($governanceResult.action -eq "GOVERNED" -and (Test-Path -LiteralPath $governanceResult.reportPath)) "Governance report was not generated."
    $governanceText = Get-Content -Raw -LiteralPath $governanceResult.reportPath
    Assert-Test ($governanceText -match "All Skills remain ``UNRATED``" -and $governanceText -match "documents-presentations") "Governance report omitted the no-fabricated-grade boundary or capability graph."

    $installSource = Join-Path $testRoot "incoming\installed-package"
    New-TestSkill -Root $installSource -Name "installed-package"
    $skillHome = Join-Path $testRoot "active"
    $sourceHome = Join-Path $testRoot "sources"
    $stagingHome = Join-Path $testRoot "staging"
    $installPreview = Install-SkillAsset -Source $installSource -Mode Package -SkillHome $skillHome -SourceHome $sourceHome -StagingHome $stagingHome -RegistryDirectory $registryRoot
    Assert-Test ($installPreview.action -eq "PREVIEW") "Install preview did not report PREVIEW."
    Assert-Test (-not (Test-Path -LiteralPath (Join-Path $skillHome "installed-package"))) "Preview unexpectedly created an activity entry."
    $installResult = Install-SkillAsset -Source $installSource -Mode Package -SkillHome $skillHome -SourceHome $sourceHome -StagingHome $stagingHome -RegistryDirectory $registryRoot -Apply
    Assert-Test ($installResult.action -eq "INSTALLED") "Package apply did not complete."

    $gitPackageRoot = Join-Path $testRoot "incoming\git-package-one"
    New-TestSkill -Root $gitPackageRoot -Name "git-package-one"
    & git -C $gitPackageRoot init -b main | Out-Null
    & git -C $gitPackageRoot config user.name "Skill Lifecycle Test"
    & git -C $gitPackageRoot config user.email "skill-lifecycle-test@example.invalid"
    Save-TestRepository -Repository $gitPackageRoot
    $gitPackageCommit = ((& git -C $gitPackageRoot rev-parse HEAD) -join "").Trim()
    $gitPackageInstall = Install-SkillAsset -Source $gitPackageRoot -Mode Package -SkillHome $skillHome -SourceHome $sourceHome -StagingHome $stagingHome -RegistryDirectory $registryRoot -Apply
    $gitPackageOrigin = Get-Content -Raw -LiteralPath (Join-Path $skillHome "git-package-one\.skill-lifecycle.json") | ConvertFrom-Json
    Assert-Test ($gitPackageInstall.action -eq "INSTALLED" -and $gitPackageOrigin.commit -eq $gitPackageCommit) "Git-backed package did not preserve its full source commit."
    $packageRegistry = Get-Content -Raw -LiteralPath (Join-Path $registryRoot "skills-registry.json") | ConvertFrom-Json
    $gitPackageRegistryRecord = @($packageRegistry.skills | Where-Object name -eq "git-package-one")
    Assert-Test (@($gitPackageRegistryRecord | Where-Object { $_.lifecycleMode -eq "PACKAGE" -and $_.commit -eq $gitPackageCommit }).Count -eq 1) "Registry did not expose Git-backed PACKAGE provenance: $($gitPackageRegistryRecord | ConvertTo-Json -Compress -Depth 5)"

    $sourceInstall = Install-SkillAsset -Source $sourceRoot -Mode Source -SkillHome $skillHome -SourceHome $sourceHome -StagingHome $stagingHome -RegistryDirectory $registryRoot -Apply
    Assert-Test ($sourceInstall.action -eq "INSTALLED" -and (Get-Item -Force -LiteralPath (Join-Path $skillHome "source-one")).LinkType -eq "Junction") "Source install did not create one source clone and activity junction."
    $hybridInstall = Install-SkillAsset -Source $hybridRoot -Mode Hybrid -SkillPath "skills\hybrid-a" -SkillHome $skillHome -SourceHome $sourceHome -StagingHome $stagingHome -RegistryDirectory $registryRoot -Apply
    Assert-Test ($hybridInstall.action -eq "INSTALLED" -and (Get-Item -Force -LiteralPath (Join-Path $skillHome "hybrid-a")).LinkType -eq "Junction") "Hybrid install did not activate the selected repository entry."

    $origin = Join-Path $testRoot "update-origin.git"
    & git init --bare $origin | Out-Null                              # Local bare remote makes update tests deterministic and offline.
    $seed = Join-Path $testRoot "update-seed"
    & git clone $origin $seed | Out-Null
    & git -C $seed switch -c main | Out-Null
    & git -C $seed config user.name "Skill Lifecycle Test"
    & git -C $seed config user.email "skill-lifecycle-test@example.invalid"
    New-TestSkill -Root $seed -Name "update-one"
    Save-TestRepository -Repository $seed -Message "version one"
    & git -C $seed push -u origin main | Out-Null
    & git --git-dir=$origin symbolic-ref HEAD refs/heads/main         # Future clones receive main and its upstream automatically.

    $managed = Join-Path $sourceHome "update-one"
    & git clone $origin $managed | Out-Null
    $updateHome = Join-Path $testRoot "update-active"
    New-Item -ItemType Directory -Path $updateHome -Force | Out-Null
    New-Item -ItemType Junction -Path (Join-Path $updateHome "update-one") -Target $managed | Out-Null
    $null = Invoke-SkillScan -Paths @($updateHome) -RegistryDirectory $registryRoot -WriteRegistry

    Add-Content -LiteralPath (Join-Path $seed "SKILL.md") -Value "`nUpdate fixture content." -Encoding utf8
    Save-TestRepository -Repository $seed -Message "version two"
    & git -C $seed push | Out-Null
    $beforeUpdate = ((& git -C $managed rev-parse HEAD) -join "").Trim()
    $updateResult = @(Update-SkillAsset -Name "update-one" -RegistryDirectory $registryRoot -StagingHome $stagingHome -Apply)
    $afterUpdate = ((& git -C $managed rev-parse HEAD) -join "").Trim()
    Assert-Test ($updateResult[0].action -eq "UPDATED") "Source update did not report UPDATED."
    Assert-Test ($beforeUpdate -ne $afterUpdate) "Source repository did not fast-forward."

    $blockedManaged = Join-Path $sourceHome "update-blocked"
    New-TestSkill -Root $blockedManaged -Name "update-blocked"
    & git -C $blockedManaged init -b main | Out-Null
    & git -C $blockedManaged config user.name "Skill Lifecycle Test"
    & git -C $blockedManaged config user.email "skill-lifecycle-test@example.invalid"
    Save-TestRepository -Repository $blockedManaged
    Add-Content -LiteralPath (Join-Path $blockedManaged "SKILL.md") -Value "`nDirty fixture content." -Encoding utf8 # Dirty worktree must block only this repository in all mode.
    New-Item -ItemType Junction -Path (Join-Path $updateHome "update-blocked") -Target $blockedManaged | Out-Null
    $null = Invoke-SkillScan -Paths @($updateHome) -RegistryDirectory $registryRoot -WriteRegistry
    $allUpdateResults = @(Update-SkillAsset -Name "all" -RegistryDirectory $registryRoot -StagingHome $stagingHome -Apply)
    Assert-Test (@($allUpdateResults | Where-Object { $_.name -eq "update-one" -and $_.action -eq "CURRENT" }).Count -eq 1) "Batch update did not continue to the clean repository."
    Assert-Test (@($allUpdateResults | Where-Object { $_.name -eq "update-blocked" -and $_.status -eq "BLOCKED" -and $_.action -eq "SKIPPED" }).Count -eq 1) "Batch update did not isolate the dirty repository."

    $backupRoot = Join-Path $testRoot "backups"
    $backupResult = Backup-AICapabilities -Paths @($skillHome, $registryRoot, $updateHome) -BackupRoot $backupRoot -Apply
    Assert-Test ($backupResult.action -eq "BACKED_UP") "Backup did not complete."
    Assert-Test ($backupResult.linkCount -eq 4) "Backup did not record all four activity junctions exactly once."
    $backupManifest = Get-Content -Raw -LiteralPath $backupResult.manifest | ConvertFrom-Json
    $updateActivityRoot = Get-CanonicalPath -Path $updateHome       # This fixture root contains only a junction to the managed repository.
    $filesCopiedThroughJunction = @($backupManifest.files | Where-Object sourceRoot -eq $updateActivityRoot)
    Assert-Test ($filesCopiedThroughJunction.Count -eq 0) "Backup entered an activity junction instead of recording only the link."
    $restoreRoot = Join-Path $testRoot "restored"
    $restorePreview = Restore-AICapabilities -BackupPath $backupResult.destination -DestinationRoot $restoreRoot
    Assert-Test ($restorePreview.action -eq "PREVIEW") "Restore preview did not validate the backup."
    $restoreResult = Restore-AICapabilities -BackupPath $backupResult.destination -DestinationRoot $restoreRoot -Apply
    Assert-Test ($restoreResult.action -eq "RESTORED") "Restore apply did not complete."

    $suiteResult = [pscustomobject]@{
        status = "PASS"                                            # Every public v1.0 capability completed against isolated fixtures.
        tests = 37
        classifications = $registry.summary.lifecycleMode
        updatedFrom = $beforeUpdate
        updatedTo = $afterUpdate
        backupFiles = $backupResult.fileCount
    }
}
catch {
    $suiteError = $_                                                # Defer rethrow until transaction-owned fixtures are cleaned.
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        Assert-PathWithinRoot -Path $testRoot -Root ([IO.Path]::GetFullPath($TestParent))
        $cleanupError = $null
        for ($attempt = 1; $attempt -le 5; $attempt += 1) {
            try {
                Remove-Item -LiteralPath $testRoot -Recurse -Force  # Remove only the uniquely named transaction-owned fixture root.
                $cleanupError = $null
                break
            }
            catch {
                $cleanupError = $_                                  # Brief retries handle transient Windows Git file handles.
                Start-Sleep -Milliseconds 200
            }
        }
        if ($cleanupError -and -not $suiteError) { $suiteError = $cleanupError }
    }
}

if ($suiteError) { throw $suiteError }                              # Report the original functional failure whenever one occurred.
$suiteResult | ConvertTo-Json -Depth 6                              # PASS is visible only after clean fixture teardown.
