<#
Layered Skill verification for the v2 reliability model.
The manifest is optional and JSON-compatible YAML: legacy Skills keep Static Health, while opted-in
Skills declare isolated Runtime and Behavior probes. Probes report evidence only and never repair a Skill.
Call example: Invoke-SkillVerification -SkillRoot "C:\skill" -RegistryDirectory "C:\registry" -Execute
#>


# --- Read an optional, dependency-free verification manifest ---
function Get-SkillManifestValue {
    param([AllowNull()][object]$Object, [Parameter(Mandatory)][string]$Name, [AllowNull()][object]$Default = $null)

    if ($null -eq $Object) { return $Default }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}


# --- Read an optional, dependency-free verification manifest ---
function Read-SkillVerificationManifest {
    param([Parameter(Mandatory)][string]$SkillRoot)                 # The Skill root owns both its manifest and declared tests.

    $root = Get-CanonicalPath -Path $SkillRoot                     # Resolve activity links before validating relative test paths.
    $skillFile = Join-Path $root "SKILL.md"
    if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) { throw "BLOCKED: Skill root has no SKILL.md: $root" }
    $metadata = Read-SkillMetadata -SkillFile $skillFile
    $manifestPath = Join-Path $root "skill.manifest.yaml"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        return [pscustomobject]@{ Root = $root; Metadata = $metadata; Path = $null; Manifest = $null; Status = $metadata.Status; Issues = @($metadata.Issues) }
    }

    $issues = [Collections.Generic.List[string]]::new()            # Report all manifest faults in one Static Health result.
    try {
        $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json -ErrorAction Stop # JSON is valid YAML 1.2 and avoids a new parser dependency.
    }
    catch {
        $issues.Add("skill.manifest.yaml must use the documented JSON-compatible YAML subset: $($_.Exception.Message)")
        return [pscustomobject]@{ Root = $root; Metadata = $metadata; Path = $manifestPath; Manifest = $null; Status = "BLOCKED"; Issues = @($issues) }
    }

    if ($metadata.Status -ne "PASS") { foreach ($issue in $metadata.Issues) { $issues.Add([string]$issue) } }
    if ((Get-SkillManifestValue -Object $manifest -Name "schemaVersion") -ne 1) { $issues.Add("schemaVersion must be 1.") }
    if ([string](Get-SkillManifestValue -Object $manifest -Name "name") -ne [string]$metadata.Name) { $issues.Add("Manifest name must match SKILL.md frontmatter name.") }
    $requiredLayers = @(Get-SkillManifestValue -Object $manifest -Name "requiredLayers" -Default @("static"))
    foreach ($layer in $requiredLayers) {
        if ([string]$layer -notin @("static", "runtime", "behavior")) { $issues.Add("Unsupported required layer '$layer'.") }
    }

    foreach ($layerName in @("runtime", "behavior")) {
        $layer = Get-SkillManifestValue -Object $manifest -Name $layerName
        if ($null -eq $layer) {
            if ($requiredLayers -contains $layerName) { $issues.Add("Required layer '$layerName' has no declaration.") }
            continue
        }
        $commandText = [string](Get-SkillManifestValue -Object $layer -Name "command")
        if (-not $commandText) { $issues.Add("Layer '$layerName' requires command."); continue }
        $timeout = [int](Get-SkillManifestValue -Object $layer -Name "timeoutSeconds" -Default 60)
        if ($timeout -lt 1 -or $timeout -gt 3600) { $issues.Add("Layer '$layerName' timeoutSeconds must be 1-3600.") }

        if ($commandText -match "[\\/]") {
            $candidate = if ([IO.Path]::IsPathRooted($commandText)) { $commandText } else { Join-Path $root $commandText }
            try { Assert-PathWithinRoot -Path ([IO.Path]::GetFullPath($candidate)) -Root $root } catch { $issues.Add("Layer '$layerName' command escapes the Skill root.") }
            if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { $issues.Add("Layer '$layerName' command does not exist: $commandText") }
        }
    }

    $status = if ($issues.Count) { "BLOCKED" } else { "PASS" }
    return [pscustomobject]@{ Root = $root; Metadata = $metadata; Path = $manifestPath; Manifest = $manifest; Status = $status; Issues = @($issues) }
}


# --- Expand only documented, non-shell placeholders ---
function Expand-SkillVerificationValue {
    param(
        [Parameter(Mandatory)][string]$Value,                       # Argument value is passed as one process token after expansion.
        [Parameter(Mandatory)][string]$SkillRoot,
        [Parameter(Mandatory)][string]$TempRoot
    )

    $expanded = $Value.Replace("{skillRoot}", $SkillRoot).Replace("{tempRoot}", $TempRoot)
    $environmentTokens = [regex]::Matches($expanded, "\{env:(?<name>[A-Za-z_][A-Za-z0-9_]*)\}")
    foreach ($token in $environmentTokens) {
        $environmentName = $token.Groups["name"].Value
        $environmentValue = [Environment]::GetEnvironmentVariable($environmentName)
        if ([string]::IsNullOrWhiteSpace($environmentValue)) { throw "UNKNOWN: Required environment variable '$environmentName' is not set." }
        $expanded = $expanded.Replace($token.Value, $environmentValue)
    }
    return $expanded                                                # No Invoke-Expression or shell interpolation is permitted.
}


# --- Compare declared top-level JSON evidence ---
function Test-SkillVerificationJSONExpectation {
    param([Parameter(Mandatory)][object]$Actual, [Parameter(Mandatory)][object]$Expected)

    foreach ($property in $Expected.PSObject.Properties) {
        $actualProperty = $Actual.PSObject.Properties[$property.Name]
        if ($null -eq $actualProperty) { return $false }
        if (($actualProperty.Value | ConvertTo-Json -Compress -Depth 8) -ne ($property.Value | ConvertTo-Json -Compress -Depth 8)) { return $false }
    }
    return $true
}


# --- Bound diagnostics and mask common credential-bearing environment values ---
function Protect-SkillVerificationText {
    param([AllowEmptyString()][string]$Text)

    $safeText = [regex]::Replace($Text, "\x1B\[[0-?]*[ -/]*[@-~]", "") # ANSI color never participates in evidence matching or persistence.
    foreach ($entry in [Environment]::GetEnvironmentVariables().GetEnumerator()) {
        if ([string]$entry.Key -notmatch "(?i)(token|password|cookie|secret|api[_-]?key|authorization)") { continue }
        $value = [string]$entry.Value
        if ($value.Length -ge 4) { $safeText = $safeText.Replace($value, "[REDACTED]") }
    }
    return $safeText.Substring(0, [Math]::Min(8192, $safeText.Length))
}


# --- Run one declared probe without a command shell ---
function Invoke-SkillVerificationLayer {
    param(
        [Parameter(Mandatory)][string]$LayerName,
        [Parameter(Mandatory)][object]$Declaration,
        [Parameter(Mandatory)][string]$SkillRoot,
        [Parameter(Mandatory)][string]$TempRoot
    )

    $startedAt = Get-Date
    try {
        $commandValue = Expand-SkillVerificationValue -Value ([string](Get-SkillManifestValue -Object $Declaration -Name "command")) -SkillRoot $SkillRoot -TempRoot $TempRoot
        $arguments = @(Get-SkillManifestValue -Object $Declaration -Name "arguments" -Default @() | ForEach-Object { Expand-SkillVerificationValue -Value ([string]$_) -SkillRoot $SkillRoot -TempRoot $TempRoot })
        if ($commandValue -match "[\\/]") {
            $program = if ([IO.Path]::IsPathRooted($commandValue)) { [IO.Path]::GetFullPath($commandValue) } else { [IO.Path]::GetFullPath((Join-Path $SkillRoot $commandValue)) }
            Assert-PathWithinRoot -Path $program -Root $SkillRoot
            if (-not (Test-Path -LiteralPath $program -PathType Leaf)) { throw "Probe command not found: $program" }
        }
        else {
            $resolvedCommand = Get-Command $commandValue -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            if (-not $resolvedCommand) { throw "UNKNOWN: Probe executable is unavailable: $commandValue" }
            $program = $resolvedCommand.Source
        }

        if ([IO.Path]::GetExtension($program) -ieq ".ps1") {
            $powerShell = Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            if (-not $powerShell) { throw "UNKNOWN: PowerShell 7 executable 'pwsh' is unavailable." }
            $arguments = @("-NoProfile", "-File", $program) + $arguments
            $program = $powerShell.Source
        }

        $startInfo = [Diagnostics.ProcessStartInfo]::new()
        $startInfo.FileName = $program
        $startInfo.WorkingDirectory = $SkillRoot
        $startInfo.UseShellExecute = $false                         # Direct process invocation prevents shell metacharacter expansion.
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $startInfo.CreateNoWindow = $true
        foreach ($argument in $arguments) { $null = $startInfo.ArgumentList.Add([string]$argument) }

        $process = [Diagnostics.Process]::new()
        $process.StartInfo = $startInfo
        if (-not $process.Start()) { throw "Probe process did not start." }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $timeoutSeconds = [int](Get-SkillManifestValue -Object $Declaration -Name "timeoutSeconds" -Default 60)
        if (-not $process.WaitForExit($timeoutSeconds * 1000)) {
            $process.Kill($true)
            $process.WaitForExit()
            throw "Probe timed out after $timeoutSeconds seconds."
        }
        $stdout = $stdoutTask.GetAwaiter().GetResult().Trim()
        $stderr = $stderrTask.GetAwaiter().GetResult().Trim()
        $expectation = Get-SkillManifestValue -Object $Declaration -Name "expect"
        $expectedExit = [int](Get-SkillManifestValue -Object $expectation -Name "exitCode" -Default 0)
        $issues = [Collections.Generic.List[string]]::new()
        if ($process.ExitCode -ne $expectedExit) { $issues.Add("Expected exit code $expectedExit but received $($process.ExitCode).") }
        foreach ($text in @(Get-SkillManifestValue -Object $expectation -Name "stdoutContains" -Default @())) {
            if (-not $stdout.Contains([string]$text, [StringComparison]::Ordinal)) { $issues.Add("stdout did not contain declared marker '$text'.") }
        }
        $jsonExpectation = Get-SkillManifestValue -Object $expectation -Name "stdoutJsonEquals"
        if ($null -ne $jsonExpectation) {
            try { $actualJSON = $stdout | ConvertFrom-Json -ErrorAction Stop }
            catch { $issues.Add("stdout was not one JSON document: $($_.Exception.Message)"); $actualJSON = $null }
            if ($actualJSON -and -not (Test-SkillVerificationJSONExpectation -Actual $actualJSON -Expected $jsonExpectation)) { $issues.Add("stdout JSON did not match declared fields.") }
        }
        $status = if ($issues.Count) { "BLOCKED" } else { "PASS" }
        return [pscustomobject]@{
            status = $status; durationMilliseconds = [int]((Get-Date) - $startedAt).TotalMilliseconds; exitCode = $process.ExitCode
            command = $program; arguments = @($arguments | ForEach-Object { Protect-SkillVerificationText -Text ([string]$_) }); stdout = Protect-SkillVerificationText -Text $stdout; stderr = Protect-SkillVerificationText -Text $stderr; issues = @($issues)
        }
    }
    catch {
        $status = if ($_.Exception.Message.StartsWith("UNKNOWN:")) { "UNKNOWN" } else { "BLOCKED" }
        return [pscustomobject]@{ status = $status; durationMilliseconds = [int]((Get-Date) - $startedAt).TotalMilliseconds; exitCode = $null; command = $null; arguments = @(); stdout = ""; stderr = ""; issues = @($_.Exception.Message) }
    }
}


# --- Verify one Skill and optionally persist immutable evidence ---
function Invoke-SkillVerification {
    param(
        [Parameter(Mandatory)][string]$SkillRoot,
        [Parameter(Mandatory)][string]$RegistryDirectory,
        [switch]$Execute,                                           # Preview validates declarations but does not run external processes.
        [switch]$InstallPhase                                       # Installation runs only layers explicitly marked runOnInstall.
    )

    $read = Read-SkillVerificationManifest -SkillRoot $SkillRoot
    $static = [pscustomobject]@{ status = $read.Status; issues = @($read.Issues); manifestPath = $read.Path }
    $runtime = [pscustomobject]@{ status = if ($read.Manifest) { "NOT_RUN" } else { "NOT_CONFIGURED" }; issues = @() }
    $behavior = [pscustomobject]@{ status = if ($read.Manifest) { "NOT_RUN" } else { "NOT_CONFIGURED" }; issues = @() }
    $temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("skill-verification-" + [guid]::NewGuid().ToString("N"))

    if ($Execute -and $read.Status -eq "PASS" -and $read.Manifest) {
        New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
        try {
            foreach ($layerName in @("runtime", "behavior")) {
                $declaration = Get-SkillManifestValue -Object $read.Manifest -Name $layerName
                if ($null -eq $declaration) { continue }
                if ($InstallPhase -and -not [bool](Get-SkillManifestValue -Object $declaration -Name "runOnInstall" -Default $false)) { continue }
                $result = Invoke-SkillVerificationLayer -LayerName $layerName -Declaration $declaration -SkillRoot $read.Root -TempRoot $temporaryRoot
                if ($layerName -eq "runtime") { $runtime = $result } else { $behavior = $result }
            }
        }
        finally {
            if (Test-Path -LiteralPath $temporaryRoot) { Remove-Item -LiteralPath $temporaryRoot -Recurse -Force } # Only this invocation's unique temp root is removed.
        }
    }

    $health = [ordered]@{ static = $static; runtime = $runtime; behavior = $behavior }
    $required = if ($read.Manifest) { @(Get-SkillManifestValue -Object $read.Manifest -Name "requiredLayers" -Default @("static")) } else { @("static") }
    $requiredStatuses = @($required | ForEach-Object { [string]$health[$_].status })
    $overallStatus = if ($requiredStatuses -contains "BLOCKED") { "BLOCKED" } elseif ($requiredStatuses -contains "UNKNOWN") { "UNKNOWN" } else { "PASS" }
    $action = if ($Execute) { "VERIFIED" } else { "PREVIEW" }
    $reportPath = if ($Execute) { Join-Path (Join-Path $RegistryDirectory "health-reports/$($read.Metadata.Name)") "$((Get-Date).ToString('yyyyMMddTHHmmssfff')).json" } else { $null }
    $report = [pscustomobject]@{
        schemaVersion = 1; status = $overallStatus; action = $action; name = $read.Metadata.Name; skillRoot = $read.Root
        verifiedAt = if ($Execute) { (Get-Date).ToString("o") } else { $null }; installPhase = [bool]$InstallPhase
        requiredLayers = $required; health = [pscustomobject]$health; reportPath = $reportPath; mutations = if ($Execute) { 1 } else { 0 }
        autoRepair = $false
    }
    if ($Execute) { Write-AtomicText -Path $reportPath -Content (($report | ConvertTo-Json -Depth 12) + "`n") -OwnerRoot $RegistryDirectory }
    return $report
}


# --- Resolve one explicit verification target from path or Registry identity ---
function Resolve-SkillVerificationTarget {
    param([string]$Name, [string]$TargetSkill, [Parameter(Mandatory)][string]$RegistryDirectory)

    if ($TargetSkill) { return Get-CanonicalPath -Path $TargetSkill }
    if (-not $Name) { throw "BLOCKED: verify requires -TargetSkill or one exact Registry -Name." }
    $registryPath = Join-Path $RegistryDirectory "skills-registry.json"
    if (-not (Test-Path -LiteralPath $registryPath -PathType Leaf)) { throw "BLOCKED: Registry does not exist: $registryPath" }
    $registry = Get-Content -Raw -LiteralPath $registryPath | ConvertFrom-Json
    $matches = @($registry.skills | Where-Object name -eq $Name)
    if ($matches.Count -ne 1) { throw "BLOCKED: Registry name '$Name' resolved to $($matches.Count) physical Skills." }
    return Get-CanonicalPath -Path $matches[0].physicalPath
}
