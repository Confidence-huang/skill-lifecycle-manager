"""Validate the isolated V5 Schemas, artifact identity, and append-only record encoding."""

from __future__ import annotations  # Keep fixture annotations stable on Python 3.12.

import json  # Load synthetic contract cases and prove JSON Lines round trips.
import unittest  # Run Phase A alongside the existing dependency-light regression suite.
from pathlib import Path  # Resolve repository-local Schemas and synthetic fixtures.

from jsonschema import Draft202012Validator, FormatChecker  # Validate every instance with the declared draft.
from referencing import Registry, Resource  # Resolve local $id references without network access.

from skill_lifecycle.contracts import (  # Exercise only pure, host-independent contract functions.
    ContractBlocked,
    build_artifact_identity,
    compute_artifact_id,
    compute_tree_sha256,
    encode_json_line,
    normalize_relative_path,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]  # Tests always locate contracts from this checkout.
SCHEMA_ROOT = REPOSITORY_ROOT / "schemas"  # Draft 2020-12 documents live outside runtime state.
FIXTURE_ROOT = Path(__file__).parent / "fixtures/contracts"  # All Phase A inputs are synthetic.


def load_json(path: Path):
    """Read one UTF-8 fixture or Schema without accepting host-locale decoding."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_schemas() -> tuple[dict[str, dict], Registry]:
    """Load every local Schema, check its meta-schema, and build an offline reference Registry."""
    schemas: dict[str, dict] = {}
    registry = Registry()
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        schema = load_json(path)  # Parsing first proves every Schema is valid JSON.
        Draft202012Validator.check_schema(schema)  # The official meta-schema rejects invalid keywords.
        schemas[path.name] = schema
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return schemas, registry


class SupplyChainContractTests(unittest.TestCase):
    """Prove the Phase A documents and identities without reading live lifecycle state."""

    @classmethod
    def setUpClass(cls) -> None:
        """Build one offline Schema Registry and load deterministic cases for the complete class."""
        cls.schemas, cls.schema_registry = load_schemas()
        cls.cases = load_json(FIXTURE_ROOT / "cases.json")
        cls.tree_cases = load_json(FIXTURE_ROOT / "artifact-tree.json")

    # --- Validate every positive and negative contract fixture ---
    def test_synthetic_documents_match_their_declared_schemas(self) -> None:
        """Require all valid cases to pass and every deliberately invalid case to fail."""
        format_checker = FormatChecker()  # Enforce declared date-time syntax when support is available.
        for case in self.cases["valid"]:
            with self.subTest(case=case["name"], expectation="valid"):
                validator = Draft202012Validator(
                    self.schemas[case["schema"]],
                    registry=self.schema_registry,
                    format_checker=format_checker,
                )
                errors = sorted(validator.iter_errors(case["instance"]), key=lambda error: list(error.path))
                self.assertEqual(errors, [], "\n".join(error.message for error in errors))
        for case in self.cases["invalid"]:
            with self.subTest(case=case["name"], expectation="invalid"):
                validator = Draft202012Validator(
                    self.schemas[case["schema"]],
                    registry=self.schema_registry,
                    format_checker=format_checker,
                )
                errors = list(validator.iter_errors(case["instance"]))
                self.assertTrue(errors, "Negative fixture unexpectedly passed its Schema.")

    # --- Prove host path style cannot change a logical tree identity ---
    def test_slash_style_and_input_order_converge_to_one_tree_hash(self) -> None:
        """Treat Windows separators and ordering as presentation, not artifact identity."""
        linux_hash = compute_tree_sha256(self.tree_cases["linuxStyleEntries"])
        windows_hash = compute_tree_sha256(self.tree_cases["windowsStyleEntries"])
        self.assertEqual(windows_hash, linux_hash)

    # --- Prove changed authoritative bytes produce a different artifact ---
    def test_content_change_produces_a_new_artifact_id(self) -> None:
        """Bind approval identity to complete content rather than only source or commit labels."""
        original_tree = compute_tree_sha256(self.tree_cases["linuxStyleEntries"])
        changed_tree = compute_tree_sha256(self.tree_cases["changedEntries"])
        original = build_artifact_identity(
            "GIT",
            "https://github.com/oil-oil/oil-visual.git",
            "23d8aea9268b688e6036ac53b8f3a5807672a793",
            ".",
            original_tree,
        )
        changed = build_artifact_identity(
            "GIT",
            "https://github.com/oil-oil/oil-visual.git",
            "23d8aea9268b688e6036ac53b8f3a5807672a793",
            ".",
            changed_tree,
        )
        self.assertNotEqual(changed_tree, original_tree)
        self.assertNotEqual(compute_artifact_id(changed), compute_artifact_id(original))

    # --- Prove only frozen artifact facts enter artifactID ---
    def test_artifact_identity_rejects_extra_host_or_approval_fields(self) -> None:
        """Block absolute paths and approval booleans from contaminating immutable identity."""
        tree_sha256 = compute_tree_sha256(self.tree_cases["linuxStyleEntries"])
        identity = build_artifact_identity(
            "GIT",
            "https://github.com/oil-oil/oil-visual.git",
            "23d8aea9268b688e6036ac53b8f3a5807672a793",
            ".",
            tree_sha256,
        )
        first_id = compute_artifact_id(identity)  # The normalized seven-field object is accepted.
        self.assertRegex(first_id, r"^sha256:[0-9a-f]{64}$")
        with self.assertRaises(ContractBlocked):
            compute_artifact_id({**identity, "physicalPath": "/home/a/.agents/skills/oil-visual"})
        with self.assertRaises(ContractBlocked):
            compute_artifact_id({**identity, "approved": True})

    # --- Reject traversal and machine-specific identity paths ---
    def test_relative_path_gate_rejects_escape_and_absolute_forms(self) -> None:
        """Keep every logical path beneath its declared artifact root on both host styles."""
        self.assertEqual(normalize_relative_path("references\\guide.md"), "references/guide.md")
        for unsafe in ("../secret", "/etc/passwd", "C:\\Users\\secret", "//server/share", " padded/path "):
            with self.subTest(path=unsafe):
                with self.assertRaises(ContractBlocked):
                    normalize_relative_path(unsafe)

    # --- Preserve one record per append-only JSON Lines event ---
    def test_json_line_encoder_returns_one_round_trippable_record(self) -> None:
        """Escape embedded newlines while terminating the event with exactly one physical newline."""
        record = {
            "decisionID": "decision-11111111-1111-4111-8111-111111111111",
            "reason": "line one\nline two",
        }
        line = encode_json_line(record)
        self.assertEqual(line.count("\n"), 1)
        self.assertTrue(line.endswith("\n"))
        self.assertEqual(json.loads(line), record)


if __name__ == "__main__":
    unittest.main()
