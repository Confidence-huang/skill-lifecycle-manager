<#
Evidence-backed capability governance for the canonical Skill Registry.
This file maps explicit name/description terms into capability domains, measures how complete the
Registry evidence is, and produces a human report without inventing usage, quality, or security data.
Call example: Write-SkillGovernanceReport -Registry $registry -RegistryDirectory "D:\CodexProjects\_skills\registry" -Apply
#>

$script:CapabilityRules = @(                                      # Rules are lexical signals, not claims of semantic equivalence.
    [pscustomobject]@{ Domain = "skill-governance"; Pattern = "(?i)agent-skill-creator|find-skills|plugin-creator|skill-(creator|installer|lifecycle-manager)|cli-hub-meta-skill|\bskill registry\b|\bplugin management\b"; Evidence = "Skill, plugin, or Agent capability lifecycle terms" },
    [pscustomobject]@{ Domain = "software-engineering"; Pattern = "(?i)\b(code|coding|debug|bug|architecture|frontend|github|git|tdd|prototype|implement|repository|pull request|cli|spec-kit|speckit)\b"; Evidence = "Code, Git, testing, architecture, CLI, or specification terms" },
    [pscustomobject]@{ Domain = "documents-presentations"; Pattern = "(?i)\b(document|docs|pdf|powerpoint|ppt|presentation|slide|spreadsheet|excel|visio|formula|letterhead|memorandum)\b"; Evidence = "Document, presentation, spreadsheet, diagram, or PDF terms" },
    [pscustomobject]@{ Domain = "visual-design"; Pattern = "(?i)\b(design|image|graphic|illustration|svg|visual|canvas|overlay|dark mode|light mode)\b"; Evidence = "Image, visual, graphic, or design terms" },
    [pscustomobject]@{ Domain = "video-media"; Pattern = "(?i)\b(video|remotion|caption|motion graphics|audio|transcript|livestream)\b"; Evidence = "Video, motion, caption, audio, or transcript terms" },
    [pscustomobject]@{ Domain = "research-learning"; Pattern = "(?i)\b(research|arxiv|paper|learn|learning|teach|exam|cram|knowledge|obsidian|jupyter|study)\b|学习|教学|考试|知识"; Evidence = "Research, learning, exam, knowledge, Obsidian, or notebook terms" },
    [pscustomobject]@{ Domain = "writing-content"; Pattern = "(?i)\b(writing|article|content|novel|story|humanizer|tone|worldbuilding|opening formula)\b|写作|小说|内容"; Evidence = "Writing, content, novel, story, or tone terms" },
    [pscustomobject]@{ Domain = "business-projects"; Pattern = "(?i)\b(business|project|product|launch|crm|sales|market|money|stock|investment|budget|operating review|kickoff|tracker|strategy)\b|项目|搞钱|岗位|薪资"; Evidence = "Business, project, product, sales, market, finance, or planning terms" },
    [pscustomobject]@{ Domain = "news-information"; Pattern = "(?i)\b(news|newsletter|trending|daily history|people daily)\b|新闻|日报|人民日报"; Evidence = "News, newsletter, trend, or daily-information terms" },
    [pscustomobject]@{ Domain = "automation-operations"; Pattern = "(?i)\b(archive|browser|chrome|computer use|workspace|handoff|publish|session|setup|drive|clipboard|network|automation)\b|自动连接|归档"; Evidence = "Browser, workspace, setup, automation, storage, or operational terms" },
    [pscustomobject]@{ Domain = "hardware-embedded"; Pattern = "(?i)\b(mspm0|mcu|firmware|hardware|embedded|circuit|sensor|motor)\b|电赛|单片机|固件|硬件|电路"; Evidence = "Embedded, firmware, MCU, hardware, circuit, or contest terms" },
    [pscustomobject]@{ Domain = "requirements-planning"; Pattern = "(?i)\b(brainstorm|ideation|requirement|clarif|grill|planning|plan mode|prd|triage)\b|需求|澄清|规划"; Evidence = "Requirements, ideation, planning, clarification, or triage terms" }
)


# --- Classify one Skill from explicit lexical evidence ---
function Get-SkillCapabilityFacts {
    param(
        [Parameter(Mandatory)][string]$Name,                         # Frontmatter name contributes stable, reviewable vocabulary.
        [AllowNull()][string]$Description                            # Trigger description supplies the intended task language.
    )

    $text = "$Name $Description"                                  # One searchable string keeps every rule deterministic.
    $domains = [Collections.Generic.List[string]]::new()            # Multiple domains are allowed because capabilities can overlap.
    $evidence = [Collections.Generic.List[string]]::new()           # Human reviewers can see why each domain was assigned.
    foreach ($rule in $script:CapabilityRules) {
        if ($text -notmatch $rule.Pattern) { continue }              # No lexical signal means no classification claim.
        $domains.Add($rule.Domain)                                  # Domain names are stable identifiers used by the report.
        $evidence.Add("$($rule.Domain): $($rule.Evidence)")         # Store the rule meaning, not an opaque numeric code.
    }
    if ($domains.Count -eq 0) {
        $domains.Add("unclassified")                               # Unknown semantic meaning stays visible for later review.
        $evidence.Add("unclassified: no taxonomy rule matched the name or description")
    }
    return [pscustomobject]@{ Domains = @($domains); Evidence = @($evidence) }
}


# --- Measure objective governance evidence without rating behavior ---
function New-SkillGovernanceFacts {
    param(
        [Parameter(Mandatory)][object]$Record,                       # Canonical Registry record supplies identity and provenance facts.
        [Parameter(Mandatory)][bool]$IsTopLevel,                    # Activation-root position separates user entries from nested steps.
        [Parameter(Mandatory)][bool]$HasNameCollision               # Equal names need semantic review before consolidation.
    )

    $metadataScore = if ($Record.name -match "^[a-z0-9-]{1,64}$" -and $Record.description) { 25 } else { 0 } # Valid discovery metadata is one quarter of readiness.
    $activationScore = if (@($Record.activePaths).Count -gt 0) { 15 } else { 0 } # At least one observed path proves the capability is exposed.
    $lifecycleScore = if ($Record.lifecycleMode -in @("PACKAGE", "SOURCE", "HYBRID")) { 20 } else { 0 } # A known maintenance mode supports repeatable operations.
    $provenanceScore = 0                                           # Provenance depends on who owns the current physical entity.
    if ($Record.scope -eq "SYSTEM") {
        $provenanceScore = 25                                      # Versioned Codex/plugin paths provide system-manager ownership evidence.
    }
    elseif ($Record.lifecycleMode -in @("SOURCE", "HYBRID")) {
        if ($Record.remote) { $provenanceScore += 12 }              # Remote identifies the update source but is not a trust verdict.
        if ($Record.commit) { $provenanceScore += 13 }              # Full commit pins the exact local source version.
    }
    elseif ($Record.lifecycleMode -eq "PACKAGE") {
        if ($Record.origin) { $provenanceScore += 10 }              # Managed package input records how the copy was acquired.
        if ($Record.remote) { $provenanceScore += 7 }               # Optional remote improves package traceability.
        if ($Record.commit) { $provenanceScore += 8 }               # Optional commit makes a Git-backed package reproducible.
    }
    $identityScore = if ($HasNameCollision) { 0 } else { 15 }      # Collision-free names need no immediate identity disambiguation.
    $readinessScore = $metadataScore + $activationScore + $lifecycleScore + $provenanceScore + $identityScore
    $evidenceTier = if ($readinessScore -ge 90) { "READY_EVIDENCE" } elseif ($readinessScore -ge 75) { "PARTIAL_EVIDENCE" } else { "REVIEW_EVIDENCE" }

    $state = if ($Record.status -ne "PASS" -or $HasNameCollision) { # Concrete issues always outrank location-based convenience states.
        "REVIEW_REQUIRED"
    }
    elseif ($Record.scope -eq "SYSTEM") {
        "SYSTEM_MANAGED"
    }
    elseif (-not $IsTopLevel) {
        "MANAGED_WITH_PARENT"
    }
    else {
        "AVAILABLE"
    }
    $action = switch ($state) {
        "REVIEW_REQUIRED" { "REVIEW_EVIDENCE" }
        "SYSTEM_MANAGED" { "KEEP_SYSTEM_MANAGED" }
        "MANAGED_WITH_PARENT" { "MANAGE_WITH_PARENT" }
        default { "KEEP_AVAILABLE" }
    }

    $gaps = [Collections.Generic.List[string]]::new()               # Missing evidence is explicit and never converted into a low quality claim.
    if ($Record.status -ne "PASS") { $gaps.Add("registryIssues") }
    if ($HasNameCollision) { $gaps.Add("semanticCollisionReview") }
    if ($provenanceScore -lt 25) { $gaps.Add("completeProvenance") }
    $gaps.Add("behavioralEvaluation")                              # Registry structure cannot prove task quality.
    $gaps.Add("usageTelemetry")                                   # No invocation history was authorized or collected.
    $gaps.Add("securityAudit")                                    # Presence in the Registry is not a security review.

    return [pscustomobject]@{
        state = $state                                              # Observed lifecycle position, not an irreversible policy action.
        evidenceReadinessScore = $readinessScore                    # Objective evidence completeness only; never a quality score.
        evidenceTier = $evidenceTier                                # Coarse readiness band keeps the number interpretable.
        qualityEvidence = "UNKNOWN_NO_BEHAVIORAL_EVALUATION"       # A/B quality grades require real forward tests.
        usageEvidence = "UNKNOWN_NO_TELEMETRY"                    # Frequency and last-use data remain unavailable.
        securityEvidence = "UNKNOWN_NOT_AUDITED"                  # No blanket safety claim is inferred from structure.
        overallGrade = "UNRATED"                                  # Missing dimensions prevent a composite grade.
        recommendedAction = $action                                # Suggestions are non-destructive and evidence-bounded.
        gaps = @($gaps)                                            # Exact missing inputs guide later governance work.
    }
}


# --- Add governance fields to every Registry record ---
function Add-SkillGovernanceFields {
    param(
        [Parameter(Mandatory)][object[]]$Records,                   # Physical Registry records receive additive governance fields.
        [Parameter(Mandatory)][Collections.Generic.HashSet[string]]$TopLevelIdentities # Physical paths prove top-level exposure.
    )

    $collisionNames = @($Records | Group-Object name | Where-Object Count -gt 1 | ForEach-Object Name)
    foreach ($record in $Records) {
        $isTopLevel = $TopLevelIdentities.Contains([string]$record.physicalPath)
        $hasCollision = $record.name -in $collisionNames
        $capability = Get-SkillCapabilityFacts -Name ([string]$record.name) -Description ([string]$record.description)
        $governance = New-SkillGovernanceFacts -Record $record -IsTopLevel $isTopLevel -HasNameCollision $hasCollision
        $record | Add-Member -NotePropertyName isTopLevel -NotePropertyValue $isTopLevel -Force
        $record | Add-Member -NotePropertyName capabilityDomains -NotePropertyValue @($capability.Domains) -Force
        $record | Add-Member -NotePropertyName capabilityEvidence -NotePropertyValue @($capability.Evidence) -Force
        $record | Add-Member -NotePropertyName governanceState -NotePropertyValue $governance.state -Force
        $record | Add-Member -NotePropertyName evidenceReadinessScore -NotePropertyValue $governance.evidenceReadinessScore -Force
        $record | Add-Member -NotePropertyName evidenceTier -NotePropertyValue $governance.evidenceTier -Force
        $record | Add-Member -NotePropertyName qualityEvidence -NotePropertyValue $governance.qualityEvidence -Force
        $record | Add-Member -NotePropertyName usageEvidence -NotePropertyValue $governance.usageEvidence -Force
        $record | Add-Member -NotePropertyName securityEvidence -NotePropertyValue $governance.securityEvidence -Force
        $record | Add-Member -NotePropertyName overallGrade -NotePropertyValue $governance.overallGrade -Force
        $record | Add-Member -NotePropertyName recommendedAction -NotePropertyValue $governance.recommendedAction -Force
        $record | Add-Member -NotePropertyName governanceGaps -NotePropertyValue @($governance.gaps) -Force
    }

    $domainCounts = [ordered]@{}                                   # Domain counts overlap when one capability has multiple explicit signals.
    $domainNames = @($Records | ForEach-Object capabilityDomains | Sort-Object -Unique)
    foreach ($domain in $domainNames) { $domainCounts[$domain] = @($Records | Where-Object { $_.capabilityDomains -contains $domain }).Count }
    return [pscustomobject]@{
        governanceState = [pscustomobject]@{
            AVAILABLE = @($Records | Where-Object governanceState -eq "AVAILABLE").Count
            SYSTEM_MANAGED = @($Records | Where-Object governanceState -eq "SYSTEM_MANAGED").Count
            MANAGED_WITH_PARENT = @($Records | Where-Object governanceState -eq "MANAGED_WITH_PARENT").Count
            REVIEW_REQUIRED = @($Records | Where-Object governanceState -eq "REVIEW_REQUIRED").Count
        }
        evidenceTier = [pscustomobject]@{
            READY_EVIDENCE = @($Records | Where-Object evidenceTier -eq "READY_EVIDENCE").Count
            PARTIAL_EVIDENCE = @($Records | Where-Object evidenceTier -eq "PARTIAL_EVIDENCE").Count
            REVIEW_EVIDENCE = @($Records | Where-Object evidenceTier -eq "REVIEW_EVIDENCE").Count
        }
        capabilityDomain = [pscustomobject]$domainCounts
        assessmentCoverage = [pscustomobject]@{
            qualityKnown = 0                                      # No blanket behavioral suite covers all installed Skills.
            usageKnown = 0                                        # No invocation telemetry source was present in this scan.
            securityKnown = 0                                     # No uniform per-Skill audit was executed by Registry generation.
            overallRated = 0                                      # Composite grades remain blocked until all required evidence exists.
        }
    }
}


# --- Generate the capability graph and governance report ---
function Write-SkillGovernanceReport {
    param(
        [Parameter(Mandatory)][object]$Registry,                    # Use the live scan object so preview and apply report identical facts.
        [Parameter(Mandatory)][string]$RegistryDirectory,           # Generated report belongs beside the canonical Registry.
        [switch]$Apply                                              # Preview returns summary data without writing the report.
    )

    if (-not $Registry.summary.governanceState) { throw "BLOCKED: Registry has no Phase 2 governance fields; regenerate it first." }
    $lines = [Collections.Generic.List[string]]::new()              # Deterministic line assembly keeps generated diffs reviewable.
    $lines.Add("# Skill Capability Governance")
    $lines.Add("")
    $lines.Add("Generated from the live Registry at $($Registry.generatedAt).")
    $lines.Add("")
    $lines.Add("## Governance boundary")
    $lines.Add("")
    $lines.Add("``evidenceReadinessScore`` measures metadata, activation, lifecycle, provenance, and collision evidence. It is not a quality, popularity, safety, or business-value score.")
    $lines.Add("")
    $lines.Add("All Skills remain ``UNRATED`` because no uniform behavioral evaluation, invocation telemetry, and security audit cover the complete inventory. This report never authorizes automatic deletion, freezing, merging, or upgrading.")
    $lines.Add("")
    $lines.Add("## Observed lifecycle states")
    $lines.Add("")
    $lines.Add("| State | Count | Meaning |")
    $lines.Add("|---|---:|---|")
    $lines.Add("| AVAILABLE | $($Registry.summary.governanceState.AVAILABLE) | Top-level PASS entry; keep available pending usage evidence. |")
    $lines.Add("| SYSTEM_MANAGED | $($Registry.summary.governanceState.SYSTEM_MANAGED) | Codex or plugin-managed PASS entry. |")
    $lines.Add("| MANAGED_WITH_PARENT | $($Registry.summary.governanceState.MANAGED_WITH_PARENT) | Nested PASS entry governed with its parent Skill or repository. |")
    $lines.Add("| REVIEW_REQUIRED | $($Registry.summary.governanceState.REVIEW_REQUIRED) | Registry issue, provenance gap, or name collision needs review. |")
    $lines.Add("")
    $lines.Add("## Evidence readiness")
    $lines.Add("")
    $lines.Add("| Tier | Count |")
    $lines.Add("|---|---:|")
    $lines.Add("| READY_EVIDENCE | $($Registry.summary.evidenceTier.READY_EVIDENCE) |")
    $lines.Add("| PARTIAL_EVIDENCE | $($Registry.summary.evidenceTier.PARTIAL_EVIDENCE) |")
    $lines.Add("| REVIEW_EVIDENCE | $($Registry.summary.evidenceTier.REVIEW_EVIDENCE) |")
    $lines.Add("")
    $lines.Add("## Capability graph")
    $lines.Add("")
    $lines.Add("Domain counts may overlap because one Skill can expose more than one explicit capability signal.")
    $lines.Add("")
    $lines.Add("| Domain | Physical records | Top-level entries |")
    $lines.Add("|---|---:|---:|")
    foreach ($property in $Registry.summary.capabilityDomain.PSObject.Properties) {
        $domain = $property.Name
        $topLevelCount = @($Registry.skills | Where-Object { $_.isTopLevel -and $_.capabilityDomains -contains $domain }).Count
        $lines.Add("| ``$domain`` | $($property.Value) | $topLevelCount |")
    }
    foreach ($property in $Registry.summary.capabilityDomain.PSObject.Properties) {
        $domain = $property.Name
        $domainSkills = @($Registry.skills | Where-Object { $_.isTopLevel -and $_.capabilityDomains -contains $domain } | Sort-Object name, physicalPath)
        $lines.Add("")
        $lines.Add("### ``$domain``")
        $lines.Add("")
        if ($domainSkills.Count -eq 0) { $lines.Add("No top-level entries."); continue }
        foreach ($skill in $domainSkills) { $lines.Add("- ``$($skill.name)`` — $($skill.governanceState), evidence $($skill.evidenceReadinessScore)/100") }
    }
    $reviewSkills = @($Registry.skills | Where-Object governanceState -eq "REVIEW_REQUIRED" | Sort-Object name, physicalPath)
    $lines.Add("")
    $lines.Add("## Review queue")
    $lines.Add("")
    if ($reviewSkills.Count -eq 0) { $lines.Add("No records currently require evidence review.") }
    else { foreach ($skill in $reviewSkills) { $lines.Add("- ``$($skill.name)`` — ``$($skill.physicalPath)`` — $($skill.issues -join '; ')") } }
    $lines.Add("")
    $lines.Add("## Next evidence needed before A/B/freeze/archive decisions")
    $lines.Add("")
    $lines.Add("1. Behavioral evaluation on representative tasks for quality evidence.")
    $lines.Add("2. Explicit, privacy-bounded invocation telemetry for frequency and last-use evidence.")
    $lines.Add("3. Per-Skill script, dependency, network, and instruction audit for security evidence.")
    $lines.Add("4. Human confirmation of semantic overlap and business criticality before merging or retiring anything.")

    $reportPath = Join-Path $RegistryDirectory "skill-governance-report.md"
    if ($Apply) { Write-AtomicText -Path $reportPath -Content (($lines -join "`n") + "`n") -OwnerRoot $RegistryDirectory }
    return [pscustomobject]@{
        status = "PASS"                                            # Governance facts were derived without requiring destructive actions.
        action = if ($Apply) { "GOVERNED" } else { "PREVIEW" }
        reportPath = $reportPath
        governanceState = $Registry.summary.governanceState
        evidenceTier = $Registry.summary.evidenceTier
        capabilityDomain = $Registry.summary.capabilityDomain
        assessmentCoverage = $Registry.summary.assessmentCoverage
    }
}
