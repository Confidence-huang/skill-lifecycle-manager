"""Prove Phase B shadow generation stays isolated, explicit, and non-authoritative."""

from __future__ import annotations  # Keep fixture annotations stable on Python 3.12.

import hashlib  # Verify that Registry and report bytes are unchanged and correctly referenced.
import json  # Create explicit synthetic Registry/source inputs and parse published outputs.
import subprocess  # Build real Git object fixtures without shell interpolation.
import tempfile  # Keep every source, Registry, and shadow output outside live host roots.
import unittest  # Run Phase B beside the existing lifecycle regression suite.
from pathlib import Path  # Express isolated host layouts and committed Skill paths.

from jsonschema import Draft202012Validator, FormatChecker  # Validate every generated document.

from skill_lifecycle.paths import HostLayout, LifecycleBlocked  # Assert the established stop gate.
from skill_lifecycle.shadow import (  # Exercise preview, publication, and pure document generation.
    OBSERVED_FIELDS,
    build_shadow_bundle,
    document_bytes,
    observed_state,
    preview_shadow,
    write_shadow,
)
from tests.test_contracts import load_schemas  # Reuse the offline Draft 2020-12 Registry.


def git(repository: Path, *arguments: str) -> str:
    """Run one fixture-local Git command and return stripped UTF-8 output."""
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        capture_output=True,
        check=True,
    )  # Argument arrays make temporary paths ordinary data on both Windows and Linux.
    return completed.stdout.strip()


def create_source(repository: Path, name: str, remote: str, skill_path: str = ".", lfs: bool = False) -> dict:
    """Create one clean pinned Git source with a committed Skill and optional LFS pointer trap."""
    repository.mkdir(parents=True)
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.name", "Fixture Author")
    git(repository, "config", "user.email", "fixture@example.invalid")
    git(repository, "config", "core.autocrlf", "false")
    git(repository, "remote", "add", "origin", remote)
    skill_root = repository if skill_path == "." else repository / Path(skill_path)
    skill_root.mkdir(parents=True, exist_ok=True)
    (skill_root / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Synthetic {name} fixture.\n---\n\n# {name}\n",
        encoding="utf-8",
        newline="\n",
    )  # A real committed entry proves name parsing comes from Git, not the worktree.
    (repository / "README.md").write_text("shared source facts\n", encoding="utf-8", newline="\n")
    if lfs:
        (repository / "asset.bin").write_bytes(
            b"version https://git-lfs.github.com/spec/v1\n"
            b"oid sha256:1111111111111111111111111111111111111111111111111111111111111111\n"
            b"size 123\n"
        )  # Pointer bytes must never be accepted as the unavailable large-file content.
    git(repository, "add", "--", "README.md", str((skill_root / "SKILL.md").relative_to(repository)))
    if lfs:
        git(repository, "add", "--", "asset.bin")
    git(repository, "commit", "-m", f"add {name} fixture")
    return {
        "repository": repository,
        "skillRoot": skill_root,
        "skillPath": skill_path,
        "name": name,
        "remote": remote,
        "commit": git(repository, "rev-parse", "HEAD"),
    }


def registry_record(source: dict, lifecycle_mode: str = "SOURCE") -> dict:
    """Return the complete 4.1 observed-state subset required by the shadow projection."""
    skill_file = source["skillRoot"] / "SKILL.md"
    return {
        "name": source["name"],
        "description": f"Synthetic {source['name']} fixture.",
        "status": "PASS",
        "scope": "USER",
        "lifecycleMode": lifecycle_mode,
        "activePaths": [str(source["skillRoot"])],
        "physicalPath": str(source["skillRoot"]),
        "origin": None,
        "sourceRepository": str(source["repository"]),
        "remote": source["remote"],
        "branch": "main",
        "commit": source["commit"],
        "entryCount": 1,
        "issues": [],
        "isTopLevel": source["skillPath"] == ".",
        "capabilityDomains": ["synthetic"],
        "capabilityEvidence": ["synthetic fixture"],
        "skillSHA256": hashlib.sha256(skill_file.read_bytes()).hexdigest().upper(),
        "sourceDirty": False,
        "lifecycleSHA256": None,
        "updates": None,
    }


def source_declaration(source: dict, role: str, lifecycle_mode: str = "SOURCE") -> dict:
    """Pin one fixture source and express a suggestion without manufacturing approval."""
    return {
        "role": role,
        "repositoryPath": str(source["repository"]),
        "skillPath": source["skillPath"],
        "expectedName": source["name"],
        "canonicalSource": source["remote"],
        "expectedCommit": source["commit"],
        "suggestedLifecycleMode": lifecycle_mode,
        "suggestedActivity": "ACTIVE" if role == "ACTIVE_OBSERVED" else "INACTIVE",
        "targetScopes": ["USER"],
    }


class ShadowTests(unittest.TestCase):
    """Validate generation, isolation, collision gates, and incomplete-object refusal."""

    def setUp(self) -> None:
        """Create one bounded host layout and two independent committed Skill sources."""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.active = create_source(
            self.root / "sources/active-skill",
            "active-skill",
            "https://example.invalid/active-skill.git",
        )
        self.reviewed = create_source(
            self.root / "reviewed/reviewed-skill",
            "reviewed-skill",
            "https://example.invalid/reviewed-skill.git",
            "skills/reviewed-skill",
        )
        self.host = HostLayout(
            activity_root=self.root / "activity",
            data_root=self.root / "data",
            state_root=self.root / "state",
            cache_root=self.root / "cache",
        )
        self.registry_path = self.root / "inputs/skills-registry.json"
        self.source_set_path = self.root / "inputs/shadow-source-set.json"
        self.output_root = self.host.data_root / "shadows/run-1"
        self.registry_path.parent.mkdir(parents=True)
        self.write_registry([registry_record(self.active)])
        self.write_source_set(
            [
                source_declaration(self.active, "ACTIVE_OBSERVED"),
                source_declaration(self.reviewed, "REVIEW_ONLY"),
            ]
        )

    def tearDown(self) -> None:
        """Release only this test's temporary directory after assertions finish."""
        self.temporary.cleanup()

    def write_registry(self, records: list[dict]) -> None:
        """Write one frozen Registry v1 input without invoking live inventory code."""
        payload = {
            "schemaVersion": 1,
            "generator": "skill-lifecycle-manager/4.1.0",
            "generatedAt": "2026-08-07T00:30:00+08:00",
            "platform": "synthetic",
            "roots": [str(self.root / "activity")],
            "summary": {"total": len(records)},
            "inventoryFingerprint": "A" * 64,
            "skills": records,
            "brokenLinks": [],
        }
        self.registry_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")

    def write_source_set(self, sources: list[dict]) -> None:
        """Write one deterministic source set whose timestamp becomes output evidence time."""
        payload = {
            "schemaVersion": 1,
            "documentType": "AI_CAPABILITY_SHADOW_SOURCE_SET",
            "hostID": "synthetic-host",
            "generatedAt": "2026-08-07T00:30:00+08:00",
            "expectedRegistrySHA256": hashlib.sha256(self.registry_path.read_bytes()).hexdigest(),
            "targetAgents": ["CODEX"],
            "policyVersion": "shadow-policy-v1",
            "sources": sources,
        }
        self.source_set_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")

    def assert_document_schema(self, path: str, payload: dict) -> None:
        """Resolve the expected local Schema from one generated document path and require zero errors."""
        schema_name = (
            "artifact-manifest.schema.json"
            if path.startswith("artifacts/")
            else "evidence.schema.json"
            if path.startswith("evidence/")
            else "shadow-report.schema.json"
            if path == "shadow-report.json"
            else "lock-candidates.schema.json"
        )
        schemas, registry = load_schemas()
        validator = Draft202012Validator(
            schemas[schema_name],
            registry=registry,
            format_checker=FormatChecker(),
        )
        errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
        self.assertEqual(errors, [], "\n".join(error.message for error in errors))

    # --- Preview every Phase B document without creating output ---
    def test_preview_is_zero_write_and_preserves_41_observed_state(self) -> None:
        """Keep Registry/source bytes stable while retaining the complete required 4.1 observed subset."""
        registry_before = hashlib.sha256(self.registry_path.read_bytes()).hexdigest()
        active_status_before = git(self.active["repository"], "status", "--porcelain=v1")
        bundle = build_shadow_bundle(self.registry_path, self.source_set_path)
        preview = preview_shadow(self.host, self.registry_path, self.source_set_path, self.output_root)

        self.assertEqual(preview["mutations"], 0)
        self.assertFalse(self.output_root.exists())
        self.assertEqual(hashlib.sha256(self.registry_path.read_bytes()).hexdigest(), registry_before)
        self.assertEqual(git(self.active["repository"], "status", "--porcelain=v1"), active_status_before)
        self.assertEqual(bundle.summary, {"artifacts": 2, "evidence": 2, "activeObserved": 1, "reviewedOnly": 1, "blocked": 0, "unmanaged": 1})

        report = bundle.documents["shadow-report.json"]
        active_record = next(record for record in report["records"] if record["name"] == "active-skill")
        reviewed_record = next(record for record in report["records"] if record["name"] == "reviewed-skill")
        expected_observed = {
            field: registry_record(self.active)[field] for field in OBSERVED_FIELDS
        }  # Exact equality proves the projection did not silently drop or rewrite required 4.1 facts.
        self.assertEqual(active_record["observedState"], expected_observed)
        self.assertEqual(active_record["convergenceStatus"], "UNMANAGED")
        self.assertIsNone(reviewed_record["observedState"])
        self.assertEqual(reviewed_record["convergenceStatus"], "NOT_EVALUATED")
        report_sha256 = hashlib.sha256(document_bytes(report)).hexdigest()
        for path, evidence in bundle.documents.items():
            if path.startswith("evidence/"):
                self.assertEqual(evidence["reportSHA256"], report_sha256)
                self.assertEqual(evidence["reportPath"], "shadow-report.json")
        lock_candidates = bundle.documents["lock-candidates.json"]
        self.assertTrue(lock_candidates["entries"])

        self.assertTrue(all(entry["approvalDecisionID"] is None for entry in lock_candidates["entries"]))
        self.assertTrue(all(entry["eligibility"] == "BLOCKED_MISSING_APPROVAL" for entry in lock_candidates["entries"]))
        for path, payload in bundle.documents.items():
            with self.subTest(path=path):
                self.assert_document_schema(path, payload)

        source_set = json.loads(self.source_set_path.read_text(encoding="utf-8"))
        schemas, schema_registry = load_schemas()
        source_errors = list(
            Draft202012Validator(
                schemas["shadow-source-set.schema.json"],
                registry=schema_registry,
                format_checker=FormatChecker(),
            ).iter_errors(source_set)
        )
        self.assertEqual(source_errors, [])

    def test_observed_state_preserves_non_null_freshness_contract(self) -> None:
        """Retain normalized PACKAGE release evidence as data without executing its command contract."""
        package_record = registry_record(self.active, lifecycle_mode="PACKAGE")
        package_record["lifecycleSHA256"] = "A" * 64
        package_record["updates"] = {
            "strategy": "git-tags",
            "repository": "https://example.invalid/active-skill.git",
            "tagPrefix": "v",
            "baselineVersion": "1.2.3",
            "cli": {"command": "active-skill", "arguments": ["version"]},
        }

        projected = observed_state(package_record)

        self.assertEqual(projected["lifecycleSHA256"], "A" * 64)
        self.assertEqual(projected["updates"], package_record["updates"])

    # --- Publish only a new isolated tree and refuse overwrite ---
    def test_apply_publishes_exact_shadow_documents_once(self) -> None:
        """Write exact preview bytes beneath data-root/shadows and hard-block a second publication."""
        bundle = build_shadow_bundle(self.registry_path, self.source_set_path)
        result = write_shadow(self.host, self.registry_path, self.source_set_path, self.output_root)
        self.assertEqual(result["action"], "SHADOW_WRITTEN")
        self.assertEqual(result["mutations"], len(bundle.documents))
        for path, payload in bundle.documents.items():
            with self.subTest(path=path):
                self.assertEqual((self.output_root / Path(path)).read_bytes(), document_bytes(payload))
        with self.assertRaises(LifecycleBlocked):
            write_shadow(self.host, self.registry_path, self.source_set_path, self.output_root)
        with self.assertRaises(LifecycleBlocked):
            preview_shadow(self.host, self.registry_path, self.source_set_path, self.root / "outside/run")

    # --- Stop before ambiguous names or physical identity loss ---
    def test_name_collision_and_physical_misclassification_are_blocked(self) -> None:
        """Reject duplicate desired identities and a Registry path that points at another entity."""
        duplicate = source_declaration(self.reviewed, "REVIEW_ONLY")
        duplicate["expectedName"] = self.active["name"]
        self.write_source_set([source_declaration(self.active, "ACTIVE_OBSERVED"), duplicate])
        with self.assertRaises(LifecycleBlocked):
            build_shadow_bundle(self.registry_path, self.source_set_path)

        wrong_record = registry_record(self.active)
        wrong_record["physicalPath"] = str(self.reviewed["skillRoot"])
        self.write_registry([wrong_record])
        self.write_source_set([source_declaration(self.active, "ACTIVE_OBSERVED")])
        with self.assertRaises(LifecycleBlocked):
            build_shadow_bundle(self.registry_path, self.source_set_path)

    # --- Pin preview and apply to one exact observed Registry file ---
    def test_registry_byte_drift_is_blocked_before_shadow_generation(self) -> None:
        """Reject even valid JSON when its bytes no longer match the source-set Registry pin."""
        with self.registry_path.open("ab") as registry_file:
            registry_file.write(b"\n")  # Whitespace preserves JSON meaning but changes frozen evidence bytes.
        with self.assertRaisesRegex(LifecycleBlocked, "Registry bytes"):
            build_shadow_bundle(self.registry_path, self.source_set_path)
        self.assertFalse(self.output_root.exists())

    # --- Refuse an unavailable Git LFS object ---
    def test_lfs_pointer_is_not_treated_as_complete_artifact_content(self) -> None:
        """Block a repository whose commit contains only a Git LFS pointer for one declared file."""
        lfs_source = create_source(
            self.root / "reviewed/lfs-skill",
            "lfs-skill",
            "https://example.invalid/lfs-skill.git",
            lfs=True,
        )
        self.write_source_set([source_declaration(lfs_source, "REVIEW_ONLY")])
        with self.assertRaisesRegex(LifecycleBlocked, "LFS pointers"):
            build_shadow_bundle(self.registry_path, self.source_set_path)


if __name__ == "__main__":
    unittest.main()
