"""Check every APK generated for a synthetic ARM64/API 35 target."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from zipfile import BadZipFile, ZipFile

from preflight import diagnostic, run_tool

DEVICE_SPEC = {
    "supportedAbis": ["arm64-v8a"],
    "supportedLocales": ["en-US"],
    "screenDensity": 480,
    "sdkVersion": 35,
}
CHECKER_STATUSES = {0: "pass", 1: "fail", 2: "invalid", 3: "not_applicable"}


def build_apk_set(bundle, bundletool, scratch):
    def jdk_tool(name):
        java_home = os.environ.get("JAVA_HOME")
        return str(Path(java_home) / "bin" / name) if java_home else name

    spec = scratch / "device.json"
    spec.write_text(json.dumps(DEVICE_SPEC), encoding="utf-8")
    apk_set = scratch / "candidate.apks"
    key = scratch / "split-check.p12"
    # Build signed splits without using the candidate's upload key.
    generated = run_tool(
        jdk_tool("keytool"), "-genkeypair", "-keystore", str(key), "-storetype", "PKCS12",
        "-storepass", "changeit", "-alias", "split-check", "-keyalg", "RSA", "-keysize", "2048",
        "-validity", "365", "-dname", "CN=Disposable Split Check",
    )
    if generated.returncode:
        raise ValueError(f"keytool: {diagnostic(generated)}")
    built = run_tool(
        jdk_tool("java"), "-jar", str(bundletool), "build-apks", f"--bundle={bundle}",
        f"--output={apk_set}", "--mode=default", f"--device-spec={spec}", f"--ks={key}",
        "--ks-key-alias=split-check", "--ks-pass=pass:changeit", "--key-pass=pass:changeit",
    )
    if built.returncode:
        raise ValueError(f"bundletool build-apks: {diagnostic(built)}")
    return apk_set


def check_split(archive, member, checker, scratch):
    apk = scratch / "split.apk"
    code = None
    try:
        # Use a fixed extraction path. APK-set member names are report data.
        with archive.open(member) as source, apk.open("wb") as destination:
            shutil.copyfileobj(source, destination)
        checked = run_tool(sys.executable, "-B", str(checker), str(apk))
        code = checked.returncode
        report = json.loads(checked.stdout)
        if (not isinstance(report, dict) or code not in CHECKER_STATUSES
                or report.get("status") != CHECKER_STATUSES[code]):
            raise ValueError(f"unexpected Toolkit status for exit {code}: {diagnostic(checked)}")
    except (OSError, BadZipFile, ValueError) as error:
        report = {"status": "error", "detail": str(error)}
    report["apk"] = member.filename
    return code, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--checker", type=Path, required=True, help="Toolkit check_apk.py")
    parser.add_argument("--bundletool", type=Path, default=os.environ.get("BUNDLETOOL_JAR"),
                        help="path to bundletool-all JAR (or set BUNDLETOOL_JAR)")
    parser.add_argument("--report-dir", type=Path, default=Path("build/preflight"))
    args = parser.parse_args()
    report_dir = args.report_dir / "arm64-16kb"
    report_dir.mkdir(parents=True, exist_ok=True)
    splits = []
    summary = {"device_spec": DEVICE_SPEC, "splits": splits}
    try:
        for previous in report_dir.glob("*.json"):
            if previous.is_file() and re.fullmatch(r"[0-9]{3,}\.json", previous.name):
                previous.unlink()
        if not args.bundletool or not args.bundletool.is_file():
            raise ValueError("provide a bundletool-all JAR with --bundletool or BUNDLETOOL_JAR")
        if not args.checker.is_file():
            raise ValueError(f"Toolkit checker not found: {args.checker}")
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            apk_set = build_apk_set(args.bundle.resolve(), args.bundletool.resolve(), scratch)
            with ZipFile(apk_set) as archive:
                members = sorted(
                    (member for member in archive.infolist() if member.filename.endswith(".apk")),
                    key=lambda member: member.filename,
                )
                if not members:
                    raise ValueError("bundletool produced no APKs for the ARM64/API 35 target")
                for index, member in enumerate(members, start=1):
                    code, report = check_split(archive, member, args.checker.resolve(), scratch)
                    name = f"{index:03}.json"
                    (report_dir / name).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                    status = report["status"]
                    splits.append({"apk": member.filename, "status": status, "exit_code": code,
                                   "report": name})
                    print(f"  {member.filename!r}: {status} ({name})")
                    if report.get("detail") and status in {"error", "invalid"}:
                        print(f"    {report['detail']!r}")
                    for library in report.get("libraries", []):
                        elf, zip_status = library["elf"], library["zip"]
                        if {"fail", "invalid"} & {elf, zip_status}:
                            print(f"    {library['entry']!r}: ELF {elf}, ZIP {zip_status}")
    except (OSError, BadZipFile, ValueError) as error:
        summary["detail"] = str(error)
        print(f"Split alignment error: {str(error)!r}", file=sys.stderr)

    statuses = {split["status"] for split in splits}
    if "detail" in summary or "error" in statuses:
        result, code = "ERROR", 2
    elif statuses & {"fail", "invalid"}:
        result, code = "FAIL", 1
    else:
        result, code = "PASS", 0
    summary["result"] = result
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (report_dir / "summary.md").write_text(
        f"\n## ARM64/API 35 split alignment — {result}\n\n"
        f"Processed {len(splits)} APKs. See `arm64-16kb/summary.json` and the per-APK reports "
        "in the preflight artifact.\n", encoding="utf-8",
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
