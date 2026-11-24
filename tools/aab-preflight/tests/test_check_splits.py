import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

CLI = Path(__file__).resolve().parents[1] / "check_splits.py"


class SplitAlignmentTests(unittest.TestCase):
    def check_set(self, checker_results, expected_exit, expected_result, *, retry=False):
        self.assertTrue(CLI.is_file(), "the split gate CLI is missing")
        spec = importlib.util.spec_from_file_location("check_splits", CLI)
        gate = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", [str(CLI.parent), *sys.path]):
            spec.loader.exec_module(gate)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apk_set = root / "candidate.apks"
            with ZipFile(apk_set, "w") as archive:
                archive.writestr("toc.pb", b"metadata")
                for apk, code, report in checker_results:
                    archive.writestr(apk, json.dumps({"code": code, "report": report}))
            checker = root / "checker.py"
            checker.write_text(
                "import json, pathlib, sys\n"
                "payload = json.loads(pathlib.Path(sys.argv[1]).read_bytes())\n"
                "print(json.dumps(payload['report']))\n"
                "sys.exit(payload['code'])\n", encoding="utf-8",
            )
            report_dir = root / "report"
            report_dir.mkdir()
            metadata = report_dir / "report.json"
            metadata.write_text('{"result":"PASS"}', encoding="utf-8")
            split_dir = report_dir / "arm64-16kb"
            if retry:
                split_dir.mkdir()
                (split_dir / "001.json").write_text('{"status":"pass"}', encoding="utf-8")
                (split_dir / "003-notes.json").write_text("local notes", encoding="utf-8")
            jar = root / "bundletool.jar"
            jar.touch()
            with patch.object(gate, "build_apk_set", return_value=apk_set):
                with patch("sys.argv", [str(CLI), "candidate.aab", "--checker", str(checker),
                                        "--bundletool", str(jar), "--report-dir", str(report_dir)]):
                    self.assertEqual(gate.main(), expected_exit)
            self.assertEqual(json.loads(metadata.read_bytes()), {"result": "PASS"})
            if retry:
                self.assertFalse((split_dir / "001.json").exists())
                self.assertEqual((split_dir / "003-notes.json").read_text(encoding="utf-8"),
                                 "local notes")
            summary = json.loads((split_dir / "summary.json").read_bytes())
            self.assertEqual(summary["result"], expected_result)
            self.assertEqual(summary["device_spec"], {
                "supportedAbis": ["arm64-v8a"], "supportedLocales": ["en-US"],
                "screenDensity": 480, "sdkVersion": 35,
            })
            self.assertIn(expected_result, (split_dir / "summary.md").read_text(encoding="utf-8"))
            self.assertFalse(list(report_dir.rglob("*.apk")))
            self.assertFalse(list(report_dir.rglob("*.apks")))
            self.assertEqual(len(summary["splits"]), len(checker_results))
            reports = {}
            for entry in summary["splits"]:
                report = json.loads((split_dir / entry["report"]).read_bytes())
                self.assertEqual(entry["apk"], report["apk"])
                self.assertEqual(entry["status"], report["status"])
                reports[entry["apk"]] = (entry["exit_code"], report)
            return reports

    def test_accepts_aligned_and_no_native_splits(self):
        native = "splits/base-arm64_v8a.apk"
        master = "splits/base-master.apk"
        aligned = [{"entry": "lib/arm64-v8a/libpageprobe.so", "elf": "pass", "zip": "pass",
                    "zip_data_offset": 16384}]
        reports = self.check_set([
            (native, 0, {"status": "pass", "libraries": aligned}),
            (master, 3, {"status": "not_applicable", "libraries": []}),
        ], 0, "PASS")
        self.assertEqual(reports[native][1]["libraries"], aligned)
        self.assertEqual(reports[master][1]["status"], "not_applicable")

    def test_rejects_zip_only_failure_and_keeps_other_split_report(self):
        native = "feature/base-arm64_v8a.apk"
        master = "splits/base-arm64_v8a.apk"
        bad_zip = [{"entry": "lib/arm64-v8a/libpageprobe.so", "elf": "pass", "zip": "fail",
                    "zip_data_offset": 4096}]
        reports = self.check_set([
            (native, 1, {"status": "fail", "libraries": bad_zip}),
            (master, 3, {"status": "not_applicable", "libraries": []}),
        ], 1, "FAIL")
        self.assertEqual(reports[native][0], 1)
        self.assertEqual(reports[native][1]["libraries"], bad_zip)
        self.assertEqual(reports[master][0], 3)

    def test_rejects_apk_set_without_apks(self):
        self.check_set([], 2, "ERROR")

    def test_error_on_retry_removes_previous_split_reports(self):
        self.check_set([], 2, "ERROR", retry=True)

    def test_rejects_invalid_split(self):
        self.check_set([("splits/base-master.apk", 2, {"status": "invalid", "libraries": []})],
                       1, "FAIL")

    def test_rejects_unexpected_checker_exit(self):
        self.check_set([("splits/base-master.apk", 9, {"status": "pass", "libraries": []})],
                       2, "ERROR")
