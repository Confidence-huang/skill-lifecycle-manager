"""Focused tests for the read-only v6 doctor aggregation."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from skill_lifecycle.doctor import doctor
from skill_lifecycle.paths import HostLayout


class DoctorTests(unittest.TestCase):
    def test_doctor_is_read_only_and_preserves_unknown_domains(self) -> None:
        host = HostLayout.default()
        with patch("skill_lifecycle.doctor.manager_identity", return_value={"status": "PASS"}), patch(
            "skill_lifecycle.doctor.health", return_value={"status": "PASS", "mutations": 0}
        ), patch(
            "skill_lifecycle.doctor.scan_plugins", return_value={"status": "PASS", "mutations": 0}
        ), patch(
            "skill_lifecycle.doctor.shutil.which", return_value=None
        ):
            result = doctor(host, Path("/tmp/project"))
        self.assertEqual(result["action"], "DOCTOR_CHECKED")
        self.assertEqual(result["mcp"]["status"], "NOT_CONFIGURED")
        self.assertIn(result["migration"]["status"], {"PASS", "WARN"})
        self.assertEqual(result["update"]["status"], "NOT_RUN")
        self.assertEqual(result["mutations"], 0)


if __name__ == "__main__":
    unittest.main()
