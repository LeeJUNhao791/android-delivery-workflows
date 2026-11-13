"""Verify a demo APK upgrade or diagnose saved adb install output."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

PACKAGE = "io.github.leejunhao791.deliverydemo.upgrade"
COMPONENT = PACKAGE + "/.UpgradeActivity"
HINTS = {
    "INSTALL_FAILED_VERSION_DOWNGRADE": "Build with a versionCode greater than the installed version.",
    "INSTALL_FAILED_UPDATE_INCOMPATIBLE": "Compare the signing certificates of both APKs.",
    "INSTALL_FAILED_INSUFFICIENT_STORAGE": "Check available device storage.",
    "INSTALL_FAILED_OLDER_SDK": "Compare the APK minSdk with the device API level.",
    "INSTALL_FAILED_USER_RESTRICTED": "Check USB installation permissions and device policy.",
}


def diagnose(output):
    match = re.search(r"Failure\s*\[\s*((?:INSTALL_FAILED|INSTALL_PARSE_FAILED)_[A-Z0-9_]+)\b", output)
    code = match[1] if match else None
    return {
        "code": code,
        "next_step": HINTS.get(code, "Inspect the full install output and check the target device."),
        "output": output,
    }


def command(*args):
    process = subprocess.run(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", timeout=120, check=False,
    )
    return process.returncode, process.stdout.strip()


def matches_apk(output, version):
    return bool(re.search(
        rf"^package: name='{re.escape(PACKAGE)}' versionCode='{version}'(?:\s|$)",
        output, re.MULTILINE,
    ))


def check_apks(aapt, apksigner_jar, baseline, candidate, java="java"):
    fingerprints = []
    for apk, version in ((baseline, 1), (candidate, 2)):
        if not apk.is_file():
            raise ValueError(f"APK does not exist: {apk}")
        status, output = command(aapt, "dump", "badging", str(apk))
        if status or not matches_apk(output, version):
            raise ValueError(f"{apk}: expected {PACKAGE} with versionCode {version}")
        status, output = command(java, "-jar", str(apksigner_jar), "verify", "--print-certs", str(apk))
        certs = re.findall(r"^Signer #\d+ certificate SHA-256 digest: ([a-fA-F0-9]{64})$", output, re.MULTILINE)
        if status or len(certs) != 1:
            raise ValueError(f"{apk}: expected one verified APK signing certificate\n{output}")
        fingerprints.append(certs[0].lower())
    if fingerprints[0] != fingerprints[1]:
        raise ValueError("The APK signing certificates differ.")
    return fingerprints[0]


def verify(adb, baseline, candidate, record):
    report = {"package": PACKAGE, "result": "FAIL", "steps": []}

    def step(name, *args, check=None):
        status, output = adb(*args)
        passed = status == 0 and (check is None or check(output))
        entry = {"step": name, "result": "PASS" if passed else "FAIL", "output": output}
        if args[0] == "install" and not passed:
            entry["diagnosis"] = diagnose(output)
        report["steps"].append(entry)
        return passed

    status, output = adb("shell", "pm", "list", "packages", PACKAGE)
    if status or f"package:{PACKAGE}" in output.splitlines():
        report.update(result="BLOCKED", reason="Use a device without an existing Upgrade Demo install.",
                      output=output)
        return report

    def launch(name):
        return step(name, "shell", "am", "start", "-W", "-n", COMPONENT,
                    check=lambda text: "Status: ok" in text and (
                        COMPONENT in text or f"{PACKAGE}/{PACKAGE}.UpgradeActivity" in text
                    ))

    def version(name, expected):
        return step(name, "shell", "dumpsys", "package", PACKAGE,
                    check=lambda text: bool(re.search(rf"^\s*versionCode={expected}(?:\s|$)", text, re.M)))

    def read(name):
        return step(name, "shell", f"run-as {PACKAGE} cat files/upgrade-record.txt",
                    check=lambda text: text == record)

    def success(output):
        return "Success" in output.splitlines()

    if not step("install_baseline", "install", str(baseline), check=success):
        return report
    if not version("baseline_version", 1) or not launch("launch_baseline"):
        return report
    seed = f"run-as {PACKAGE} sh -c 'mkdir -p files && printf %s {record} > files/upgrade-record.txt'"
    if not step("write_record", "shell", seed) or not read("read_baseline_record"):
        return report
    if not step("install_candidate", "install", "-r", str(candidate), check=success):
        return report
    if not version("candidate_version", 2) or not launch("launch_candidate") or not read("read_candidate_record"):
        return report
    status, output = adb("install", "-r", str(baseline))
    diagnosis = diagnose(output)
    report["downgrade"] = diagnosis
    rejected = status != 0 and diagnosis["code"] == "INSTALL_FAILED_VERSION_DOWNGRADE"
    report["steps"].append({
        "step": "reject_downgrade", "result": "PASS" if rejected else "FAIL", "output": output,
    })
    if rejected and version("version_after_rejection", 2) and read("record_after_rejection"):
        report.update(result="PASS", installed_version=2, record=record)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    diagnostic = modes.add_parser("diagnose", help="classify a saved adb install log")
    diagnostic.add_argument("log", type=Path)
    run = modes.add_parser("verify", help="run the upgrade and downgrade checks on a test device")
    run.add_argument("--serial", required=True, help="device serial from adb devices")
    run.add_argument("--adb", default="adb")
    run.add_argument("--aapt", required=True)
    run.add_argument("--apksigner-jar", type=Path, required=True)
    run.add_argument("--java", default="java")
    run.add_argument("--baseline", type=Path, required=True)
    run.add_argument("--candidate", type=Path, required=True)
    run.add_argument("--report", type=Path, default=Path("build/adb-upgrade/report.json"))
    args = parser.parse_args()
    try:
        if args.mode == "diagnose":
            print(json.dumps(diagnose(args.log.read_text(encoding="utf-8-sig")), indent=2))
            return 0
        baseline, candidate = args.baseline.resolve(), args.candidate.resolve()
        fingerprint = check_apks(args.aapt, args.apksigner_jar, baseline, candidate, args.java)

        def adb(*command_args):
            return command(args.adb, "-s", args.serial, *command_args)

        status, device = adb("get-state")
        if status or device != "device":
            raise ValueError(f"ADB target is unavailable: {device}")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        report = verify(adb, baseline, candidate, "demo-" + uuid4().hex)
        report["apk_signer_sha256"] = fingerprint
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"{report['result']}: {args.report}")
        return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[report["result"]]
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"Upgrade check error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
