<#
PowerShell 7 entrypoint for complete Skill lifecycle operations on Windows and Linux.
This file only receives the trigger, loads command functions, and dispatches one explicit action;
business decisions and filesystem mutations stay in the matching command file.
Call example: pwsh -NoProfile -File ./skill.ps1 -Command registry -Apply
#>

[CmdletBinding()]
param(
    [ValidateSet("help", "scan", "registry", "report", "governance", "stabilize", "health", "verify", "install", "update", "backup", "restore")]
    [string]$Command = "help",                                     # One explicit lifecycle action per invocation.
    [string[]]$Path,                                                # Scan or backup roots; defaults depend on the command.
    [string]$ProjectRoot,                                           # Optional project-local Skill discovery root.
    [string]$Source,                                                # Install source: local directory or Git URL.
    [string]$Name,                                                  # Install name override or update Registry name.
    [ValidateSet("Auto", "Package", "Source", "Hybrid")]
    [string]$Mode = "Auto",                                       # Acquisition mode; Auto derives it from source evidence.
    [string]$SkillPath,                                             # Relative selected Skill directory for HYBRID repositories.
    [string]$TargetSkill,                                           # Exact existing Skill root for targeted v2 verification.
    [string]$Ref,                                                   # Optional Git update/install branch, tag, or commit.
    [string]$SkillHome,                                             # Omit to use the current host's user activity root.
    [string]$SourceHome,                                            # Omit to use the current host's durable source root.
    [string]$StagingHome,                                           # Omit to use the current host's transaction cache root.
    [string]$RegistryDirectory,                                     # Omit to use the current host's state root.
    [string]$BackupRoot,                                            # Omit to use the current host's durable backup root.
    [string]$BackupPath,                                            # Restore source directory containing backup-manifest.json.
    [string]$DestinationRoot,                                       # Empty restore destination; live roots are never implicit.
    [switch]$Apply                                                   # Enables the exact final mutation reported by preview.
)

$ErrorActionPreference = "Stop"                                    # Dispatch stops on the first command-level failure.
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path       # Resolve resources relative to this installed Skill.
. (Join-Path $scriptRoot "skill-state.ps1")                         # Load shared identity, Git, path, and atomic-write rules.
. (Join-Path $scriptRoot "commands/governance.ps1")                # Load capability taxonomy, evidence readiness, and governance report.
. (Join-Path $scriptRoot "commands/scan.ps1")                      # Load discovery, classification, and Registry output.
. (Join-Path $scriptRoot "commands/stability.ps1")                 # Load stable-baseline capture and read-only routine health.
. (Join-Path $scriptRoot "commands/report.ps1")                    # Load the human-facing count and collision report.
. (Join-Path $scriptRoot "commands/verification.ps1")              # Load optional Runtime and Behavior probes without auto-repair.
. (Join-Path $scriptRoot "commands/install.ps1")                   # Load transactional package/source/hybrid installation.
. (Join-Path $scriptRoot "commands/update.ps1")                    # Load fetch, candidate validation, and fast-forward update.
. (Join-Path $scriptRoot "commands/backup.ps1")                    # Load physical-file backup and link recording.
. (Join-Path $scriptRoot "commands/restore.ps1")                   # Load verified empty-destination restore.

$hostLayout = Get-SkillHostLayout                                  # Resolve operating-system facts once for every dispatched command.
if (-not $SkillHome) { $SkillHome = $hostLayout.skillHome }        # Explicit CLI values always override host defaults.
if (-not $SourceHome) { $SourceHome = $hostLayout.sourceHome }
if (-not $StagingHome) { $StagingHome = $hostLayout.stagingHome }
if (-not $RegistryDirectory) { $RegistryDirectory = $hostLayout.registryDirectory }
if (-not $BackupRoot) { $BackupRoot = $hostLayout.backupRoot }


# --- Dispatch one requested lifecycle action ---
try {
    $result = switch ($Command) {
        "help" {
            [pscustomobject]@{
                status = "PASS"                                    # Help is a read-only successful command.
                commands = @("scan", "registry", "report", "governance", "stabilize", "health", "verify", "install", "update", "backup", "restore")
                applyRule = "Preview by default; add -Apply for final writes."
                platform = $hostLayout.platform                    # Calling agents can see which default layout was selected.
                activityLinkType = $hostLayout.activityLinkType
                registry = $RegistryDirectory
            }
        }
        "scan" {
            Invoke-SkillScan -Paths $Path -ProjectRoot $ProjectRoot -RegistryDirectory $RegistryDirectory -WriteRegistry:$Apply
        }
        "registry" {
            Invoke-SkillScan -Paths $Path -ProjectRoot $ProjectRoot -RegistryDirectory $RegistryDirectory -WriteRegistry:$Apply
        }
        "report" {
            Write-SkillCapabilityReport -RegistryDirectory $RegistryDirectory -Apply:$Apply
        }
        "governance" {
            $governanceRegistry = Invoke-SkillScan -Paths $Path -ProjectRoot $ProjectRoot -RegistryDirectory $RegistryDirectory -WriteRegistry:$Apply # Refresh live evidence before deriving policy suggestions.
            Write-SkillGovernanceReport -Registry $governanceRegistry -RegistryDirectory $RegistryDirectory -Apply:$Apply
        }
        "stabilize" {
            $managerRoot = Split-Path -Parent $scriptRoot           # Source repository owns scripts/, references/, and Skill metadata.
            $managerActivity = Join-Path $SkillHome "skill-lifecycle-manager"
            Save-SkillStabilityBaseline -RegistryDirectory $RegistryDirectory -BackupRoot $BackupRoot -ManagerRoot $managerRoot -ActivityPath $managerActivity -Apply:$Apply
        }
        "health" {
            $managerRoot = Split-Path -Parent $scriptRoot           # Routine checks compare the running code to its frozen Git identity.
            $managerActivity = Join-Path $SkillHome "skill-lifecycle-manager"
            Get-SkillHealth -RegistryDirectory $RegistryDirectory -BackupRoot $BackupRoot -ManagerRoot $managerRoot -ActivityPath $managerActivity -ProjectRoot $ProjectRoot
        }
        "verify" {
            $verificationTarget = Resolve-SkillVerificationTarget -Name $Name -TargetSkill $TargetSkill -RegistryDirectory $RegistryDirectory
            Invoke-SkillVerification -SkillRoot $verificationTarget -RegistryDirectory $RegistryDirectory -Execute:$Apply
        }
        "install" {
            if (-not $Source) { throw "BLOCKED: install requires -Source." }
            Install-SkillAsset -Source $Source -Mode $Mode -Name $Name -SkillPath $SkillPath -Ref $Ref -SkillHome $SkillHome -SourceHome $SourceHome -StagingHome $StagingHome -RegistryDirectory $RegistryDirectory -Apply:$Apply
        }
        "update" {
            if (-not $Name) { throw "BLOCKED: update requires -Name or -Name all." }
            Update-SkillAsset -Name $Name -Ref $Ref -RegistryDirectory $RegistryDirectory -StagingHome $StagingHome -Apply:$Apply
        }
        "backup" {
            $backupPaths = if ($Path -and $Path.Count) { $Path } else { Get-DefaultCapabilityBackupRoots -Layout $hostLayout } # Default scope follows the current host without scanning its full home.
            Backup-AICapabilities -Paths $backupPaths -BackupRoot $BackupRoot -Apply:$Apply
        }
        "restore" {
            if (-not $BackupPath -or -not $DestinationRoot) { throw "BLOCKED: restore requires -BackupPath and -DestinationRoot." }
            Restore-AICapabilities -BackupPath $BackupPath -DestinationRoot $DestinationRoot -Apply:$Apply
        }
    }
    $result | ConvertTo-Json -Depth 14                              # Stable structured feedback supports both humans and calling agents.
    if ($Command -eq "verify" -and $result.status -ne "PASS") { exit 1 } # Automation must not mistake BLOCKED or UNKNOWN evidence for success.
    $global:LASTEXITCODE = 0                                       # Successful internal probes must not leak an earlier Git exit code.
}
catch {
    [pscustomobject]@{ status = "BLOCKED"; command = $Command; error = $_.Exception.Message } | ConvertTo-Json -Depth 6
    exit 1                                                         # Shell callers can gate later steps on the command result.
}
