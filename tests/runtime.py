"""Runtime probe: import the installed Python package and report its exact version."""

import json  # Return one machine-readable lifecycle result.

from skill_lifecycle import __version__  # Prove the installed package resolves without PYTHONPATH.


print(json.dumps({"status": "PASS", "version": __version__}))  # Startup evidence is intentionally bounded.
