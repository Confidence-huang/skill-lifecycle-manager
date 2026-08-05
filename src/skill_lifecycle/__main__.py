"""Run the command-line entry when Python executes the package as a module."""

from skill_lifecycle.cli import main  # Import the single CLI trigger.


if __name__ == "__main__":
    raise SystemExit(main())  # Return the CLI exit code to the calling shell.
