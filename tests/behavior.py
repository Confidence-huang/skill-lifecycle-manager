"""Behavior probe: scan one isolated Skill and prove native physical identity."""

import json  # Return one bounded machine-readable behavior result.
import tempfile  # Prevent the representative scan from touching live activity or state roots.
from pathlib import Path  # Create native host fixture paths.

from skill_lifecycle.inventory import scan_skills  # Exercise the real installed inventory command.


with tempfile.TemporaryDirectory(prefix="skill-lifecycle-behavior-") as temporary:
    activity = Path(temporary) / "activity"
    skill = activity / "probe"
    skill.mkdir(parents=True)
    entry = "---\nname: probe\ndescription: isolated behavior probe\n---\n\n# Probe\n"
    (skill / "SKILL.md").write_text(entry, encoding="utf-8")
    inventory = scan_skills([activity])

passed = inventory["summary"]["inventory"]["physicalEntries"] == 1
passed = passed and inventory["summary"]["brokenLinks"] == 0
print(json.dumps({"status": "PASS" if passed else "BLOCKED", "physicalEntries": inventory["summary"]["inventory"]["physicalEntries"]}))
