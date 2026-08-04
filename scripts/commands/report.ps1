<#
Human-facing Skill capability report generated from the canonical Registry.
The report separates physical files, exact names, top-level activations, nested entries, aliases,
and collisions so a filesystem count is never presented as the Codex Desktop list size.
Call example: Write-SkillCapabilityReport -RegistryDirectory "D:\CodexProjects\_skills\registry" -Apply
#>


# --- Build or persist the capability count report ---
function Write-SkillCapabilityReport {
    param(
        [Parameter(Mandatory)][string]$RegistryDirectory,           # Canonical JSON and generated report share one state directory.
        [switch]$Apply                                               # Preview returns facts without creating the Markdown file.
    )

    $registryPath = Join-Path $RegistryDirectory "skills-registry.json"
    if (-not (Test-Path -LiteralPath $registryPath -PathType Leaf)) { throw "BLOCKED: Canonical Registry is missing; run registry -Apply first." }
    $registry = Get-Content -Raw -LiteralPath $registryPath | ConvertFrom-Json # JSON remains the sole machine-readable authority.
    if (-not $registry.summary.inventory) { throw "BLOCKED: Registry predates the explicit inventory view; regenerate it first." }

    $collisionGroups = @($registry.skills | Group-Object name | Where-Object Count -gt 1 | Sort-Object Name)
    $lines = [Collections.Generic.List[string]]::new()              # Line assembly keeps the generated document deterministic.
    $lines.Add("# Skill Capability Inventory")
    $lines.Add("")
    $lines.Add("Generated from ``$registryPath`` at $($registry.generatedAt).")
    $lines.Add("")
    $lines.Add("## Count views")
    $lines.Add("")
    $lines.Add("| View | Count | Meaning |")
    $lines.Add("|---|---:|---|")
    $lines.Add("| Physical entries | $($registry.summary.inventory.physicalEntries) | Resolved, deduplicated physical ``SKILL.md`` entities across all scanned roots. |")
    $lines.Add("| Unique names | $($registry.summary.inventory.uniqueNames) | Exact frontmatter names; semantic overlap is not inferred. |")
    $lines.Add("| Top-level entries | $($registry.summary.inventory.topLevelEntries) | Direct children of scanned activation roots, closest to a conventional user install list. |")
    $lines.Add("| Nested entries | $($registry.summary.inventory.nestedEntries) | Parent-Skill steps, Codex system internals, and plugin-contained Skills. |")
    $lines.Add("| Activation aliases | $($registry.summary.inventory.activationAliases) | Extra activity-link or compatibility paths already excluded from the physical count. |")
    $lines.Add("| Name-collision groups | $($registry.summary.inventory.nameCollisionGroups) | Exact names backed by multiple physical entities. |")
    $lines.Add("")
    $lines.Add("> Physical entries are not Codex Desktop rows. Desktop may namespace, rename, hide, or selectively expose plugin and template Skills.")
    $lines.Add("")
    $lines.Add("## Evidence state")
    $lines.Add("")
    $lines.Add("- PASS: $($registry.summary.status.PASS)")
    $lines.Add("- BLOCKED: $($registry.summary.status.BLOCKED)")
    $lines.Add("- UNKNOWN: $($registry.summary.status.UNKNOWN)")
    $lines.Add("")
    $lines.Add("## Exact-name collisions")
    $lines.Add("")
    if ($collisionGroups.Count -eq 0) {
        $lines.Add("No exact-name collisions were found.")         # An empty section is still an explicit verified result.
    }
    else {
        foreach ($group in $collisionGroups) {
            $lines.Add("### ``$($group.Name)`` ($($group.Count) physical entries)")
            $lines.Add("")
            foreach ($skill in $group.Group) { $lines.Add("- ``$($skill.physicalPath)`` [$($skill.status)]") }
            $lines.Add("")
        }
    }
    $lines.Add("## Interpretation boundary")
    $lines.Add("")
    $lines.Add("This report does not infer semantic duplicates, usage frequency, deprecation, or business-critical status. Those require usage evidence or human review; equal names and hashes alone do not grant merge or deletion authority.")

    $reportPath = Join-Path $RegistryDirectory "skill-capability-report.md"
    $result = [pscustomobject]@{
        status = "PASS"                                            # Registry structure supplied every required count view.
        action = if ($Apply) { "REPORTED" } else { "PREVIEW" }
        reportPath = $reportPath
        inventory = $registry.summary.inventory
        collisionNames = @($collisionGroups | ForEach-Object Name) # Explicit enumeration remains valid when no collisions exist.
    }
    if ($Apply) { Write-AtomicText -Path $reportPath -Content (($lines -join "`n") + "`n") -OwnerRoot $RegistryDirectory }
    return $result                                                  # JSON feedback exposes the same facts as the Markdown report.
}
