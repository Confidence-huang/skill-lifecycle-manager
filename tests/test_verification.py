"""Prove legacy compatibility, preview boundaries, declared probes, and redaction."""

import json  # Inspect persisted bounded verification evidence.
import sys  # Use the current uv-managed Python as a deterministic probe executable.
import tempfile  # Keep reports and Skill fixtures disposable.
import unittest  # Run with the standard library.
from pathlib import Path  # Create exact Skill roots and report paths.

from skill_lifecycle.verification import verify_target
from support import create_skill, layout, write_manifest


class VerificationTests(unittest.TestCase):
    """Validate Static/Runtime/Behavior evidence without automatic repair."""

    def test_python_placeholder_uses_current_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            skill = create_skill(root / "skill", "portable")
            probe = {
                "command": "{python}",
                "arguments": ["-c", "import json; print(json.dumps({'status': 'PASS'}))"],
                "expect": {"exitCode": 0, "stdoutJsonEquals": {"status": "PASS"}},
            }
            write_manifest(skill, runtime=probe, required=["static", "runtime"])
            result = verify_target(host, skill, True)
        runtime = next(layer for layer in result["layers"] if layer["layer"] == "runtime")
        self.assertEqual(runtime["status"], "PASS")
        self.assertEqual(Path(runtime["command"]).resolve(), Path(sys.executable).resolve())

    def test_legacy_skill_reports_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            skill = create_skill(root / "skill", "legacy")
            result = verify_target(host, skill, False)
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual([layer["status"] for layer in result["layers"]], ["PASS", "NOT_CONFIGURED", "NOT_CONFIGURED"])
        self.assertFalse(host.state_root.exists())

    def test_preview_marks_configured_layers_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            skill = create_skill(root / "skill", "preview")
            probe = {"command": sys.executable, "arguments": ["-c", "print('{}')"]}
            write_manifest(skill, runtime=probe, behavior=probe, required=["static", "runtime", "behavior"])
            result = verify_target(host, skill, False)
        self.assertEqual([layer["status"] for layer in result["layers"]], ["PASS", "NOT_RUN", "NOT_RUN"])
        self.assertFalse(host.state_root.exists())

    def test_applied_runtime_and_behavior_pass_and_persist_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            skill = create_skill(root / "skill", "passing")
            probe = {
                "command": sys.executable,
                "arguments": ["-c", "import json; print(json.dumps({'status':'PASS'}))"],
                "timeoutSeconds": 10,
                "expect": {"exitCode": 0, "stdoutJsonEquals": {"status": "PASS"}},
            }
            write_manifest(skill, runtime=probe, behavior=probe, required=["static", "runtime", "behavior"])
            result = verify_target(host, skill, True)
            report = json.loads(Path(result["reportPath"]).read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(report["autoRepair"], False)
        self.assertEqual([layer["status"] for layer in report["layers"]], ["PASS", "PASS", "PASS"])

    def test_failed_required_probe_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            skill = create_skill(root / "skill", "blocked")
            probe = {"command": sys.executable, "arguments": ["-c", "raise SystemExit(3)"], "expect": {"exitCode": 0}}
            write_manifest(skill, runtime=probe, required=["static", "runtime"])
            result = verify_target(host, skill, True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("Expected exit 0", result["layers"][1]["issues"][0])

    def test_missing_environment_placeholder_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            skill = create_skill(root / "skill", "unknown")
            probe = {"command": sys.executable, "arguments": ["-c", "print('{env:SLM_TEST_MISSING}')"]}
            write_manifest(skill, runtime=probe, required=["static", "runtime"])
            result = verify_target(host, skill, True)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIn("SLM_TEST_MISSING", result["layers"][1]["issues"][0])

    def test_sensitive_probe_output_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = layout(root / "host")
            skill = create_skill(root / "skill", "redacted")
            probe = {"command": sys.executable, "arguments": ["-c", "print('token=super-secret')"], "expect": {"exitCode": 0}}
            write_manifest(skill, runtime=probe, required=["static", "runtime"])
            result = verify_target(host, skill, True)
        self.assertNotIn("super-secret", result["layers"][1]["stdout"])
        self.assertIn("[REDACTED]", result["layers"][1]["stdout"])


if __name__ == "__main__":
    unittest.main()
