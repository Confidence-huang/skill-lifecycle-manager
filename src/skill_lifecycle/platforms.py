"""Host-specific paths and activity-entry mechanics behind one narrow interface.

Lifecycle policy stays in the domain modules.  This adapter owns only the facts that genuinely
differ by host: default storage roots and the directory-link primitive used for one active entry.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class UnsupportedPlatform(RuntimeError):
    """Stop before a lifecycle command runs on an unimplemented host family."""


@dataclass(frozen=True)
class PlatformRoots:
    """Resolved default roots without creating host state."""

    activity: Path
    data: Path
    state: Path
    cache: Path


@dataclass(frozen=True)
class HostPlatform:
    """Deep platform seam consumed by path, inventory, transaction, and health modules."""

    name: str

    def default_roots(
        self,
        *,
        home: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> PlatformRoots:
        """Return host defaults while keeping environment reads injectable for tests."""
        user_home = home or Path.home()
        variables = os.environ if environ is None else environ
        if self.name == "linux":
            data_home = Path(variables.get("XDG_DATA_HOME", user_home / ".local/share"))
            state_home = Path(variables.get("XDG_STATE_HOME", user_home / ".local/state"))
            cache_home = Path(variables.get("XDG_CACHE_HOME", user_home / ".cache"))
            return PlatformRoots(
                activity=user_home / ".agents/skills",
                data=data_home / "skill-lifecycle-manager",
                state=state_home / "skill-lifecycle-manager",
                cache=cache_home / "skill-lifecycle-manager",
            )
        if self.name == "windows":
            local = Path(variables.get("LOCALAPPDATA", user_home / "AppData/Local"))
            owner = local / "skill-lifecycle-manager"
            return PlatformRoots(
                activity=user_home / ".agents/skills",
                data=owner / "data",
                state=owner / "state",
                cache=owner / "cache",
            )
        raise UnsupportedPlatform(f"Unsupported host platform: {self.name}")

    def is_directory_link(self, path: Path) -> bool:
        """Recognize the platform's directory activation primitive without following it."""
        return path.is_symlink() or (self.name == "windows" and path.is_junction())

    def link_exists(self, path: Path) -> bool:
        """Treat broken links and junctions as occupied activity entries."""
        return path.exists() or self.is_directory_link(path)

    def link_target(self, path: Path) -> str:
        """Return stable target evidence for a supported directory link."""
        if not self.is_directory_link(path):
            raise OSError(f"Path is not a supported directory link: {path}")
        if path.is_symlink():
            return os.readlink(path)
        return str(path.resolve(strict=True))

    def create_directory_link(self, target: Path, link: Path) -> None:
        """Create one directory symlink on Linux or one junction on Windows."""
        if self.name == "linux":
            os.symlink(target, link, target_is_directory=True)
            return
        if self.name != "windows":
            raise UnsupportedPlatform(f"Unsupported host platform: {self.name}")
        for value in (str(link), str(target)):
            if any(character in value for character in ('"', "%", "!", "&", "|", "<", ">", "^", "(", ")", "\r", "\n")):
                raise OSError("Windows junction paths cannot contain cmd expansion characters.")
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise OSError(f"Windows junction creation failed: {detail}")

    def remove_directory_link(self, path: Path) -> None:
        """Remove only the link entity; never recurse into its target."""
        if not self.is_directory_link(path):
            raise OSError(f"Refusing to remove a non-link activity entry: {path}")
        if path.is_junction() and not path.is_symlink():
            path.rmdir()
        else:
            path.unlink()

    def guardian_schedule(
        self,
        command: list[str],
        schedule_time: str,
        apply: bool,
        *,
        home: Path | None = None,
    ) -> dict[str, object]:
        """Preview or install one scan-only daily schedule through the host-native scheduler."""
        if any("\n" in value or "\r" in value for value in command):
            raise OSError("Guardian schedule command values cannot contain line breaks.")
        user_home = home or Path.home()  # Tests may isolate the schedule root without changing process HOME.
        if self.name == "linux":
            return self._linux_guardian_schedule(command, schedule_time, apply, user_home)
        if self.name == "windows":
            return self._windows_guardian_schedule(command, schedule_time, apply)
        raise UnsupportedPlatform(f"Unsupported host platform: {self.name}")

    def _linux_guardian_schedule(
        self,
        command: list[str],
        schedule_time: str,
        apply: bool,
        user_home: Path,
    ) -> dict[str, object]:
        """Install new systemd user units and remove them again if activation fails."""
        unit_root = user_home / ".config" / "systemd" / "user"
        service_path = unit_root / "skill-lifecycle-guardian.service"
        timer_path = unit_root / "skill-lifecycle-guardian.timer"
        escaped = [
            f'"{value.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34)).replace(chr(37), chr(37) * 2)}"'
            for value in command
        ]  # Quotes preserve spaces; doubled percent signs prevent systemd specifier expansion.
        service_text = "\n".join([
            "[Unit]",
            "Description=Skill Lifecycle Guardian daily evidence scan",
            "",
            "[Service]",
            "Type=oneshot",
            f"ExecStart={' '.join(escaped)}",
            "",
        ])
        timer_text = "\n".join([
            "[Unit]",
            "Description=Run Skill Lifecycle Guardian daily",
            "",
            "[Timer]",
            f"OnCalendar=*-*-* {schedule_time}:00",
            "Persistent=true",
            "Unit=skill-lifecycle-guardian.service",
            "",
            "[Install]",
            "WantedBy=timers.target",
            "",
        ])
        result: dict[str, object] = {
            "platform": "linux",
            "servicePath": str(service_path),
            "timerPath": str(timer_path),
            "command": command,
            "mutations": 0,
        }
        if not apply:
            return result
        if service_path.exists() or timer_path.exists():
            raise OSError("Guardian schedule already exists; refusing to overwrite it.")

        unit_root.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []
        try:
            service_path.write_text(service_text, encoding="utf-8")
            created.append(service_path)
            timer_path.write_text(timer_text, encoding="utf-8")
            created.append(timer_path)
            reload_result = subprocess.run(["systemctl", "--user", "daemon-reload"], text=True, capture_output=True, check=False)
            if reload_result.returncode:
                raise OSError(reload_result.stderr.strip() or "systemd user daemon reload failed")
            enable_result = subprocess.run(["systemctl", "--user", "enable", "--now", "skill-lifecycle-guardian.timer"], text=True, capture_output=True, check=False)
            if enable_result.returncode:
                raise OSError(enable_result.stderr.strip() or "systemd user timer activation failed")
        except BaseException:
            for path in reversed(created):
                path.unlink(missing_ok=True)  # Remove only new unit files owned by this failed installation.
            raise
        return {**result, "mutations": 3}

    def _windows_guardian_schedule(
        self,
        command: list[str],
        schedule_time: str,
        apply: bool,
    ) -> dict[str, object]:
        """Install one new Task Scheduler entry without overwriting an existing user task."""
        task_name = "Skill Lifecycle Guardian"
        task_command = subprocess.list2cmdline(command)  # Windows quoting stays data passed to schtasks.exe.
        result: dict[str, object] = {
            "platform": "windows",
            "taskName": task_name,
            "taskCommand": task_command,
            "command": command,
            "mutations": 0,
        }
        if not apply:
            return result
        existing = subprocess.run(["schtasks.exe", "/Query", "/TN", task_name], text=True, capture_output=True, check=False)
        if existing.returncode == 0:
            raise OSError("Guardian schedule already exists; refusing to overwrite it.")
        created = subprocess.run(
            ["schtasks.exe", "/Create", "/SC", "DAILY", "/ST", schedule_time, "/TN", task_name, "/TR", task_command],
            text=True,
            capture_output=True,
            check=False,
        )
        if created.returncode:
            raise OSError(created.stderr.strip() or created.stdout.strip() or "Windows scheduled task creation failed")
        return {**result, "mutations": 1}


def platform_for(platform_name: str) -> HostPlatform:
    """Normalize Python's platform identifier into one supported adapter."""
    if platform_name.startswith("linux"):
        return HostPlatform("linux")
    if platform_name == "win32":
        return HostPlatform("windows")
    raise UnsupportedPlatform(f"Only Windows and Linux are supported; observed {platform_name!r}.")


def current_platform() -> HostPlatform:
    """Return the adapter for the running interpreter."""
    return platform_for(sys.platform)
