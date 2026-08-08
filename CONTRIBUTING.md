# Contributing

Thanks for improving Skill Lifecycle Manager.

1. Open an issue before changing a public contract or host mutation boundary.
2. Keep Windows and Linux behavior behind `skill_lifecycle.platforms`; do not fork the domain logic.
3. Add or update unittest coverage for every behavior change.
4. Run:

   ```text
   uv sync --frozen
   uv run python -m unittest discover -s tests -v
   uv run python tests/runtime.py
   uv run python tests/behavior.py
   uv build
   ```

5. Keep previews zero-write, use subprocess argument arrays, and preserve exact rollback evidence.
6. Do not commit credentials, host-local Registry/baseline files, recovery archives, or absolute
   personal paths.

By submitting a contribution, you agree that it is licensed under Apache-2.0.
