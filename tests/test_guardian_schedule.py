"""Prove daily scheduling is cross-platform, preview-first, and scan-only."""

from __future__ import annotations  # Keep fixture annotations stable on Python 3.12.

import tempfile  # Keep generated Linux unit files below one disposable home.
import unittest  # Run schedule acceptance with the standard library.
from pathlib import Path  # Build exact Linux and Windows schedule paths.
from subprocess import CompletedProcess  # Return deterministic scheduler command results.
from unittest.mock import patch  # Prevent tests from changing the real user scheduler.

from skill_lifecycle.guardian import schedule_guardian  # Exercise the public Guardian schedule command.
from skill_lifecycle.paths import HostLayout, LifecycleBlocked  # Build explicit platform layouts and assert stops.
from skill_lifecycle.platforms import HostPlatform  # Test both host schedule implementations on one runner.


# --- Build one isolated layout for a named platform ---
def platform_layout(root: Path, name: str) -> HostLayout:
    """Return a layout whose schedule command carries four exact lifecycle roots."""
    return HostLayout(root / "activity", root / "data", root / "state", root / "cache", HostPlatform(name))


class GuardianScheduleTests(unittest.TestCase):
    """Ensure scheduling can run daily scans but cannot silently enter the update transaction."""

    def test_linux_preview_contains_scan_only_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = platform_layout(root, "linux")
            result = schedule_guardian(host, "03:15", False, home=root / "home")
        self.assertIn("guardian", result["command"])
        self.assertIn("scan", result["command"])
        self.assertIn("--apply", result["command"])
        self.assertNotIn("update", result["command"])
        self.assertEqual(result["mutations"], 0)

    def test_linux_apply_creates_new_user_timer_and_enables_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = platform_layout(root, "linux")
            with patch("skill_lifecycle.platforms.subprocess.run", return_value=CompletedProcess([], 0, "", "")) as run:
                result = schedule_guardian(host, "03:15", True, home=root / "home")
            self.assertTrue(Path(result["servicePath"]).is_file())
            self.assertTrue(Path(result["timerPath"]).is_file())
            self.assertEqual(run.call_count, 2)
        self.assertEqual(result["mutations"], 3)

    def test_linux_refuses_to_overwrite_an_existing_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            host = platform_layout(root, "linux")
            unit_root = root / "home" / ".config" / "systemd" / "user"
            unit_root.mkdir(parents=True)
            (unit_root / "skill-lifecycle-guardian.service").write_text("keep\n", encoding="utf-8")
            with self.assertRaisesRegex(LifecycleBlocked, "already exists"):
                schedule_guardian(host, "03:15", True, home=root / "home")

    def test_windows_preview_uses_task_scheduler_and_scan_only(self) -> None:
        root = Path("C:/fixture")
        host = platform_layout(root, "windows")
        result = schedule_guardian(host, "04:20", False, home=Path("C:/Users/example"))
        self.assertEqual(result["platform"], "windows")
        self.assertIn("guardian", result["command"])
        self.assertIn("scan", result["command"])
        self.assertNotIn("update", result["command"])
        self.assertEqual(result["mutations"], 0)

    def test_windows_apply_refuses_existing_task_and_creates_only_when_absent(self) -> None:
        root = Path("C:/fixture")
        host = platform_layout(root, "windows")
        absent_then_created = [CompletedProcess([], 1, "", "not found"), CompletedProcess([], 0, "", "")]
        with patch("skill_lifecycle.platforms.subprocess.run", side_effect=absent_then_created) as run:
            result = schedule_guardian(host, "04:20", True, home=Path("C:/Users/example"))
        self.assertEqual(result["mutations"], 1)
        self.assertEqual(run.call_args_list[1].args[0][0], "schtasks.exe")
        self.assertNotIn("/F", run.call_args_list[1].args[0])

        with patch("skill_lifecycle.platforms.subprocess.run", return_value=CompletedProcess([], 0, "exists", "")):
            with self.assertRaisesRegex(LifecycleBlocked, "already exists"):
                schedule_guardian(host, "04:20", True, home=Path("C:/Users/example"))

    def test_schedule_rejects_line_break_in_a_root_before_platform_mutation(self) -> None:
        root = Path("/tmp/unsafe\nroot")
        host = platform_layout(root, "linux")
        with patch("skill_lifecycle.platforms.subprocess.run") as run:
            with self.assertRaisesRegex(LifecycleBlocked, "line breaks"):
                schedule_guardian(host, "03:15", True, home=Path("/tmp/home"))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
