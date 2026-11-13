import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "tools/aab-preflight/preflight.py"
FIXTURES = Path(os.environ.get("AAB_TEST_FIXTURES", ROOT / "build/demo"))


class PreflightTests(unittest.TestCase):
    def run_case(self, *, name="candidate.aab", changes=None, expected_exit=0):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            contract = json.loads((FIXTURES / "release.json").read_text(encoding="utf-8"))
            contract.update(changes or {})
            config = tmp / "release.json"
            config.write_text(json.dumps(contract))
            bundle = FIXTURES / name
            result = subprocess.run(
                [sys.executable, str(CLI), str(bundle), "--expect", str(config),
                 "--report-dir", str(tmp / "report"), "--commit", "test-commit"],
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, expected_exit, result.stdout + result.stderr)
            report = json.loads((tmp / "report/report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["sha256"], hashlib.sha256(bundle.read_bytes()).hexdigest())
            self.assertEqual(report["commit"], "test-commit")
            markdown = (tmp / "report/report.md").read_text(encoding="utf-8")
            self.assertIn(report["sha256"], markdown)
            self.assertIn(report["result"], markdown)
            return {check["name"]: check["status"] for check in report["checks"]}

    def test_release(self):
        self.assertTrue(all(status == "PASS" for status in self.run_case().values()))

    def test_repeated_version(self):
        checks = self.run_case(changes={"previous_version_code": 2}, expected_exit=1)
        self.assertEqual(checks["version_code_increased"], "FAIL")

    def test_wrong_identity_and_certificate(self):
        checks = self.run_case(changes={
            "application_id": "org.example.wrong",
            "version_name": "wrong",
            "upload_certificate_sha256": "0" * 64,
        }, expected_exit=1)
        for name in ("application_id", "version_name", "upload_certificate_sha256"):
            self.assertEqual(checks[name], "FAIL")

    def test_unsigned(self):
        self.assertEqual(
            self.run_case(name="unsigned.aab", expected_exit=1)["signature"], "FAIL"
        )

    def test_tampered(self):
        self.assertEqual(
            self.run_case(name="tampered.aab", expected_exit=1)["signature"], "FAIL"
        )

    def test_invalid_contract_exits_before_opening_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            config = tmp / "release.json"
            config.write_text('{"application_id": true}')
            result = subprocess.run(
                [sys.executable, str(CLI), str(tmp / "absent.aab"), "--expect", str(config),
                 "--report-dir", str(tmp / "report")],
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("release.json: application_id", result.stderr)
            self.assertFalse((tmp / "report").exists())


if __name__ == "__main__":
    unittest.main()
