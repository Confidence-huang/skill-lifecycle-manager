"""Prove Codex plugin observation is structured, honest, and zero-write."""

from __future__ import annotations  # Keep annotations available on Python 3.12.

import json  # Encode representative Codex CLI JSON results.
import subprocess  # Build completed-process fixtures with real return semantics.
import tempfile  # Keep source and marketplace paths inside disposable roots.
import unittest  # Exercise the public observation interface and CLI trigger.
from pathlib import Path  # Build exact local marketplace topology.
from unittest.mock import call, patch  # Replace only the true external Codex CLI adapter.

from skill_lifecycle.cli import execute, parser  # Prove public parsing and dispatch.
from skill_lifecycle.paths import LifecycleBlocked  # Preserve the manager's shared stop gate.
from skill_lifecycle.plugin_inventory import scan_plugins  # Exercise the deep module interface.
from support import layout  # Keep dispatch tests on one isolated host layout.


def completed(arguments: list[str], stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    """Return one bounded subprocess result without starting an external program."""
    return subprocess.CompletedProcess(arguments, returncode, stdout, stderr)


def plugin_payload(source_path: Path, *, marketplace_name: str = "openai-bundled") -> dict:
    """Describe one installed plugin using the documented Codex JSON fields."""
    return {
        "installed": [
            {
                "pluginId": f"sites@{marketplace_name}",
                "name": "sites",
                "marketplaceName": marketplace_name,
                "version": "0.1.34",
                "installed": True,
                "enabled": True,
                "source": {"source": "local", "path": str(source_path)},
                "marketplaceSource": {"sourceType": "local", "source": str(source_path.parent.parent)},
                "installPolicy": "AVAILABLE",
                "authPolicy": "ON_INSTALL",
            }
        ],
        "available": [
            {
                "pluginId": f"visualize@{marketplace_name}",
                "name": "visualize",
                "marketplaceName": marketplace_name,
                "version": "1.0.20",
                "installed": False,
                "enabled": False,
                "source": {"source": "local", "path": str(source_path.parent / "visualize")},
                "installPolicy": "AVAILABLE",
                "authPolicy": "NONE",
            }
        ],
    }


def marketplace_payload(root: Path) -> dict:
    """Describe one configured local marketplace using the documented JSON fields."""
    return {
        "marketplaces": [
            {
                "name": "openai-bundled",
                "root": str(root),
                "marketplaceSource": {"sourceType": "local", "source": str(root)},
            }
        ]
    }


class PluginInventoryTests(unittest.TestCase):
    """Validate the read-only Codex adapter and evidence normalization."""

    def test_scan_normalizes_installed_plugin_without_claiming_runtime_or_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "marketplace"
            source = root / "plugins" / "sites"
            source.mkdir(parents=True)
            responses = [
                completed(["/opt/codex", "--version"], "codex-cli 0.146.0\n"),
                completed([], json.dumps(plugin_payload(source))),
                completed([], json.dumps(marketplace_payload(root))),
            ]
            with patch("skill_lifecycle.plugin_inventory.shutil.which", return_value="/opt/codex"), patch(
                "skill_lifecycle.plugin_inventory.subprocess.run", side_effect=responses
            ) as run:
                result = scan_plugins("/opt/codex")

        plugin = result["plugins"][0]
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["action"], "PLUGINS_SCANNED")
        self.assertEqual(result["codexVersion"], "codex-cli 0.146.0")
        self.assertEqual(result["summary"]["installed"], 1)
        self.assertEqual(result["summary"]["available"], 0)
        self.assertEqual(plugin["evidenceStatus"], "PASS")
        self.assertEqual(plugin["sourceStatus"], "PASS")
        self.assertEqual(plugin["marketplaceStatus"], "PASS")
        self.assertEqual(plugin["runtimeStatus"], "NOT_RUN")
        self.assertEqual(plugin["authenticationStatus"], "UNKNOWN")
        self.assertEqual(result["mutations"], 0)
        options = {"text": True, "capture_output": True, "check": False, "timeout": 30, "shell": False}
        self.assertEqual(
            run.call_args_list,
            [
                call(["/opt/codex", "--version"], **options),
                call(["/opt/codex", "plugin", "list", "--json"], **options),
                call(["/opt/codex", "plugin", "marketplace", "list", "--json"], **options),
            ],
        )

    def test_available_flag_includes_available_entries_and_exact_cli_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "marketplace"
            source = root / "plugins" / "sites"
            source.mkdir(parents=True)
            (root / "plugins" / "visualize").mkdir()
            responses = [
                completed([], "codex-cli 0.146.0\n"),
                completed([], json.dumps(plugin_payload(source))),
                completed([], json.dumps(marketplace_payload(root))),
            ]
            with patch("skill_lifecycle.plugin_inventory.shutil.which", return_value="codex"), patch(
                "skill_lifecycle.plugin_inventory.subprocess.run", side_effect=responses
            ) as run:
                result = scan_plugins(include_available=True)

        self.assertEqual(result["summary"]["available"], 1)
        self.assertEqual(result["availablePlugins"][0]["authenticationStatus"], "NOT_CONFIGURED")
        self.assertEqual(run.call_args_list[1].args[0], ["codex", "plugin", "list", "--available", "--json"])

    def test_missing_codex_cli_blocks_without_starting_a_process(self) -> None:
        with patch("skill_lifecycle.plugin_inventory.shutil.which", return_value=None), patch(
            "skill_lifecycle.plugin_inventory.subprocess.run"
        ) as run:
            with self.assertRaisesRegex(LifecycleBlocked, "Codex command was not found"):
                scan_plugins("missing-codex")
        run.assert_not_called()

    def test_nonzero_codex_command_blocks_with_bounded_diagnostic(self) -> None:
        response = completed([], "", returncode=2, stderr="plugin command failed token=topsecret")
        with patch("skill_lifecycle.plugin_inventory.shutil.which", return_value="codex"), patch(
            "skill_lifecycle.plugin_inventory.subprocess.run", return_value=response
        ):
            with self.assertRaises(LifecycleBlocked) as raised:
                scan_plugins()
        self.assertIn("plugin command failed token=[REDACTED]", str(raised.exception))
        self.assertNotIn("topsecret", str(raised.exception))

    def test_malformed_json_blocks_instead_of_inventing_inventory(self) -> None:
        responses = [completed([], "codex-cli 0.146.0\n"), completed([], "not-json")]
        with patch("skill_lifecycle.plugin_inventory.shutil.which", return_value="codex"), patch(
            "skill_lifecycle.plugin_inventory.subprocess.run", side_effect=responses
        ):
            with self.assertRaisesRegex(LifecycleBlocked, "valid JSON"):
                scan_plugins()

    def test_missing_marketplace_and_local_source_degrade_record_to_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing_source = Path(temporary) / "missing" / "plugins" / "sites"
            payload = plugin_payload(missing_source, marketplace_name="missing-marketplace")
            responses = [
                completed([], "codex-cli 0.146.0\n"),
                completed([], json.dumps(payload)),
                completed([], json.dumps({"marketplaces": []})),
            ]
            with patch("skill_lifecycle.plugin_inventory.shutil.which", return_value="codex"), patch(
                "skill_lifecycle.plugin_inventory.subprocess.run", side_effect=responses
            ):
                result = scan_plugins()

        plugin = result["plugins"][0]
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(plugin["evidenceStatus"], "UNKNOWN")
        self.assertEqual(plugin["sourceStatus"], "UNKNOWN")
        self.assertEqual(plugin["marketplaceStatus"], "UNKNOWN")
        self.assertIn("Local plugin source path does not exist.", plugin["issues"])
        self.assertIn("Configured marketplace was not observed.", plugin["issues"])

    def test_source_outside_marketplace_root_is_visible_topology_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "marketplace"
            outside = base / "outside" / "sites"
            root.mkdir()
            (root / "plugins").mkdir()  # Keep the lexical escape path traversable before normalization.
            outside.mkdir(parents=True)
            escaped_source = root / "plugins" / ".." / ".." / "outside" / "sites"
            responses = [
                completed([], "codex-cli 0.146.0\n"),
                completed([], json.dumps(plugin_payload(escaped_source))),
                completed([], json.dumps(marketplace_payload(root))),
            ]
            with patch("skill_lifecycle.plugin_inventory.shutil.which", return_value="codex"), patch(
                "skill_lifecycle.plugin_inventory.subprocess.run", side_effect=responses
            ):
                result = scan_plugins()

        plugin = result["plugins"][0]
        self.assertEqual(plugin["marketplaceStatus"], "UNKNOWN")
        self.assertIn("Local plugin source is outside the observed marketplace root.", plugin["issues"])

    def test_cli_parser_and_dispatch_preserve_exact_plugin_request(self) -> None:
        parsed = parser().parse_args(["plugins", "--available", "--codex-command", "/opt/codex"])
        expected = {"status": "PASS", "action": "PLUGINS_SCANNED", "mutations": 0}
        with tempfile.TemporaryDirectory() as temporary, patch(
            "skill_lifecycle.cli.scan_plugins", return_value=expected
        ) as observe:
            result = execute(parsed, layout(Path(temporary)))
        self.assertTrue(parsed.available)
        self.assertEqual(parsed.codex_command, "/opt/codex")
        self.assertEqual(result, expected)
        observe.assert_called_once_with("/opt/codex", True)


if __name__ == "__main__":
    unittest.main()
