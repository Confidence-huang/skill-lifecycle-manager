"""
Terminate one isolated PACKAGE install after activation and before Registry publication.

The parent test supplies disposable roots through environment variables, writes the durable
transaction record, and launches this script with the candidate virtual-environment Python. The
replacement Registry writer exits the process immediately, so normal exception cleanup cannot run.
"""

from __future__ import annotations  # Keep the fixture aligned with the Python 3.12 product contract.

import os  # Read explicit temporary roots and perform the injected hard process exit.
from pathlib import Path  # Convert environment text into exact fixture paths.

from skill_lifecycle import operations  # Replace only the child process's final Registry trigger.
from support import layout  # Construct a HostLayout wholly beneath the parent-owned temporary root.


# --- Stop after activation without running Python cleanup ---
def exit_before_registry(*_arguments, **_keywords):
    """Exit with the Phase C sentinel code when install reaches final Registry publication."""
    os._exit(86)  # A hard exit bypasses `finally` and ordinary exception handlers by design.


# --- Run one isolated interrupted install ---
def main() -> None:
    """Install the supplied package until the injected final-publication interruption occurs."""
    host_root = Path(os.environ["PHASE_C_HOST_ROOT"])  # The parent creates and later inspects this root.
    package_root = Path(os.environ["PHASE_C_PACKAGE_ROOT"])  # Synthetic input never references live Skills.
    operations.write_registry = exit_before_registry  # Inject failure at the documented last-write boundary.
    operations.install_skill(layout(host_root), str(package_root), "package")  # The sentinel exit must occur here.
    raise RuntimeError("Phase C interruption did not occur.")  # Reaching this line means the fault hook failed.


if __name__ == "__main__":
    main()
