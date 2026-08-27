"""Prove the CLI can render Unicode JSON through a legacy Windows console encoding."""

from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from skill_lifecycle import cli


class CLIOutputTests(unittest.TestCase):
    """Keep the public JSON stream independent from the host's active code page."""

    def test_standard_streams_are_reconfigured_from_gbk_to_utf8(self) -> None:
        stdout_bytes = io.BytesIO()  # Model the byte sink behind a Windows-native console stream.
        stderr_bytes = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_bytes, encoding="gbk")
        stderr = io.TextIOWrapper(stderr_bytes, encoding="gbk")

        with patch.object(cli.sys, "stdout", stdout), patch.object(cli.sys, "stderr", stderr):
            cli.configure_standard_streams()
            print("Windows ↔ Linux", file=cli.sys.stdout)  # The arrow reproduced the live CP936 failure.
            print("错误 ↔ BLOCKED", file=cli.sys.stderr)
            stdout.flush()
            stderr.flush()

        self.assertEqual(stdout_bytes.getvalue().decode("utf-8").splitlines(), ["Windows ↔ Linux"])
        self.assertEqual(stderr_bytes.getvalue().decode("utf-8").splitlines(), ["错误 ↔ BLOCKED"])
        stdout.detach()  # Keep BytesIO ownership explicit when TextIOWrapper leaves this test scope.
        stderr.detach()


if __name__ == "__main__":
    unittest.main()
