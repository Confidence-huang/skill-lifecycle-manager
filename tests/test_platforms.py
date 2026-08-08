"""Prove host defaults and native activity-link mechanics on Windows and Linux."""

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from skill_lifecycle.cli import execute
from skill_lifecycle.paths import HostLayout, LifecycleBlocked
from skill_lifecycle.platforms import HostPlatform, UnsupportedPlatform, current_platform, platform_for


class PlatformTests(unittest.TestCase):
    """Keep platform behavior behind one directly testable interface."""

    def test_platform_identifiers_are_explicit(self) -> None:
        self.assertEqual(platform_for("linux").name, "linux")
        self.assertEqual(platform_for("linux2").name, "linux")
        self.assertEqual(platform_for("win32").name, "windows")
        with self.assertRaises(UnsupportedPlatform):
            platform_for("darwin")

    def test_linux_defaults_honor_xdg(self) -> None:
        roots = HostPlatform("linux").default_roots(
            home=Path("/users/example"),
            environ={
                "XDG_DATA_HOME": "/data",
                "XDG_STATE_HOME": "/state",
                "XDG_CACHE_HOME": "/cache",
            },
        )
        self.assertEqual(roots.activity, Path("/users/example/.agents/skills"))
        self.assertEqual(roots.data, Path("/data/skill-lifecycle-manager"))
        self.assertEqual(roots.state, Path("/state/skill-lifecycle-manager"))
        self.assertEqual(roots.cache, Path("/cache/skill-lifecycle-manager"))

    def test_windows_defaults_honor_local_app_data(self) -> None:
        roots = HostPlatform("windows").default_roots(
            home=Path("C:/Users/example"),
            environ={"LOCALAPPDATA": "D:/Local"},
        )
        self.assertEqual(roots.activity, Path("C:/Users/example/.agents/skills"))
        self.assertEqual(roots.data, Path("D:/Local/skill-lifecycle-manager/data"))
        self.assertEqual(roots.state, Path("D:/Local/skill-lifecycle-manager/state"))
        self.assertEqual(roots.cache, Path("D:/Local/skill-lifecycle-manager/cache"))

    def test_native_directory_link_round_trip(self) -> None:
        adapter = current_platform()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.mkdir()
            link = root / "active"
            adapter.create_directory_link(target, link)
            self.assertTrue(adapter.is_directory_link(link))
            self.assertEqual(link.resolve(strict=True), target.resolve(strict=True))
            self.assertTrue(adapter.link_target(link))
            adapter.remove_directory_link(link)
            self.assertFalse(adapter.link_exists(link))
            self.assertTrue(target.is_dir())

    def test_windows_junction_rejects_expansion_characters_before_execution(self) -> None:
        adapter = HostPlatform("windows")
        with self.assertRaises(OSError):
            adapter.create_directory_link(Path("C:/target"), Path("C:/bad%PATH%"))

    def test_windows_junction_uses_separate_command_arguments(self) -> None:
        adapter = HostPlatform("windows")
        target = Path("C:/target path")
        link = Path("C:/active path")
        with patch("skill_lifecycle.platforms.subprocess.run", return_value=CompletedProcess([], 0, "", "")) as run:
            adapter.create_directory_link(target, link)
        self.assertEqual(
            run.call_args.args[0],
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        )

    def test_windows_blocks_unrehearsed_manager_promotion(self) -> None:
        adapter = HostPlatform("windows")
        root = Path("C:/fixture")
        host = HostLayout(root / "activity", root / "data", root / "state", root / "cache", adapter)
        with self.assertRaisesRegex(LifecycleBlocked, "Linux-only"):
            execute(Namespace(command="manager-upgrade"), host)


if __name__ == "__main__":
    unittest.main()
