import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

SPEC = importlib.util.spec_from_file_location(
    "upgrade", Path(__file__).resolve().parents[1] / "upgrade.py"
)
upgrade = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upgrade)


class InstallDiagnosisTests(unittest.TestCase):
    def test_extracts_install_code(self):
        result = upgrade.diagnose(
            "Performing Streamed Install\nadb: failed to install old.apk: "
            "Failure [INSTALL_FAILED_VERSION_DOWNGRADE: version 1 < 2]"
        )
        self.assertEqual(result["code"], "INSTALL_FAILED_VERSION_DOWNGRADE")
        self.assertIn("versionCode", result["next_step"])

    def test_does_not_infer_a_code_from_the_filename(self):
        result = upgrade.diagnose("adb: cannot stat INSTALL_FAILED_VERSION_DOWNGRADE.apk")
        self.assertIsNone(result["code"])


class UpgradeTests(unittest.TestCase):
    def transport(self, *, saved="demo-record", downgrade="INSTALL_FAILED_VERSION_DOWNGRADE"):
        def adb(*args):
            if args == ("shell", "pm", "list", "packages", upgrade.PACKAGE):
                return 0, ""
            if args[:2] == ("shell", "dumpsys"):
                version = 1 if adb.version == 1 else 2
                return 0, f"    versionCode={version} minSdk=23"
            if args[0] == "install":
                if args[-1] == "old.apk" and adb.version == 2:
                    return 1, f"Failure [{downgrade}]"
                adb.version = 1 if args[-1] == "old.apk" else 2
                return 0, "Success"
            if args[:3] == ("shell", "am", "start"):
                return 0, "Status: ok\nActivity: " + upgrade.COMPONENT
            if args[-1].endswith(" cat files/upgrade-record.txt"):
                return 0, saved
            return 0, ""
        adb.version = 0
        return Mock(side_effect=adb)

    def test_upgrade_and_downgrade_check_use_the_same_record(self):
        adb = self.transport()
        report = upgrade.verify(adb, Path("old.apk"), Path("new.apk"), "demo-record")
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["installed_version"], 2)
        self.assertEqual(report["downgrade"]["code"], "INSTALL_FAILED_VERSION_DOWNGRADE")
        self.assertIn(unittest.mock.call("install", "-r", "new.apk"), adb.call_args_list)
        self.assertIn(unittest.mock.call("install", "-r", "old.apk"), adb.call_args_list)

    def test_refuses_to_modify_an_existing_install(self):
        adb = Mock(return_value=(0, f"package:{upgrade.PACKAGE}\n"))
        report = upgrade.verify(adb, Path("old.apk"), Path("new.apk"), "demo-record")
        self.assertEqual(report["result"], "BLOCKED")
        adb.assert_called_once()

    def test_data_loss_fails_before_attempting_downgrade(self):
        adb = self.transport(saved="wrong")
        report = upgrade.verify(adb, Path("old.apk"), Path("new.apk"), "demo-record")
        self.assertEqual(report["result"], "FAIL")
        self.assertNotIn(unittest.mock.call("install", "-r", "old.apk"), adb.call_args_list)

    def test_unrelated_install_failure_is_not_a_pass(self):
        report = upgrade.verify(
            self.transport(downgrade="INSTALL_FAILED_UPDATE_INCOMPATIBLE"),
            Path("old.apk"), Path("new.apk"), "demo-record",
        )
        self.assertEqual(report["result"], "FAIL")

    def test_accepts_only_the_expected_demo_package_and_version(self):
        self.assertTrue(upgrade.matches_apk(
            f"package: name='{upgrade.PACKAGE}' versionCode='1' versionName='1'", 1
        ))
        self.assertFalse(upgrade.matches_apk(
            f"package: name='{upgrade.PACKAGE}.other' versionCode='1'", 1
        ))
        self.assertFalse(upgrade.matches_apk(
            f"package: name='{upgrade.PACKAGE}' versionCode='2'", 1
        ))
