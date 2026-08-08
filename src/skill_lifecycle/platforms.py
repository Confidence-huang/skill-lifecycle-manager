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
            if any(character in value for character in ('"', "%", "!", "\r", "\n")):
                raise OSError("Windows junction paths cannot contain cmd expansion characters.")
        command = f'mklink /J "{link}" "{target}"'
        completed = subprocess.run(
            ["cmd.exe", "/d", "/s", "/c", command],
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
