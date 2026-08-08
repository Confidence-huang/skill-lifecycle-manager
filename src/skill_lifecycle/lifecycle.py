"""
Compatibility imports for the earlier Linux-native MVP module path.

New code should import the business modules directly. These exports preserve local callers while the
formal `skill-lifecycle-manager` identity replaces the temporary `linux-skill-lifecycle` product.
"""

from skill_lifecycle.inventory import scan_skills, write_registry  # Preserve inventory caller names.
from skill_lifecycle.freshness import check_updates  # Expose read-only PACKAGE release evidence to compatibility callers.
from skill_lifecycle.operations import create_backup, install_skill, restore_backup  # Preserve mutation caller names.
from skill_lifecycle.paths import HostLayout, LifecycleBlocked  # Preserve shared host and stop types.
from skill_lifecycle.stability import health as check_health  # Preserve the previous health symbol.

__all__ = [
    "HostLayout",
    "LifecycleBlocked",
    "check_health",
    "check_updates",
    "create_backup",
    "install_skill",
    "restore_backup",
    "scan_skills",
    "write_registry",
]  # Make the temporary compatibility surface explicit and removable in a later major version.
