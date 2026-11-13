"""Check an Android App Bundle against a release contract."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree

ANDROID = "{http://schemas.android.com/apk/res/android}"
TOOL_DIR = Path(__file__).resolve().parent
CONTRACT_FIELDS = {
    "application_id": lambda v: isinstance(v, str) and bool(v.strip()),
    "version_code": lambda v: type(v) is int and v > 0,
    "version_name": lambda v: isinstance(v, str) and bool(v.strip()),
    "upload_certificate_sha256": lambda v: isinstance(v, str)
    and bool(re.fullmatch(r"[0-9a-fA-F]{64}", v)),
}


def read_contract(path):
    try:
        contract = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise ValueError(f"{path}: {error}") from error
    if not isinstance(contract, dict):
        raise ValueError(f"{path}: expected a JSON object")
    for field, valid in CONTRACT_FIELDS.items():
        if not valid(contract.get(field)):
            raise ValueError(f"{path}: {field} is missing or invalid")
    unknown = contract.keys() - CONTRACT_FIELDS.keys() - {"previous_version_code"}
    if unknown:
        raise ValueError(f"{path}: unknown field(s): {', '.join(sorted(unknown))}")
    if "previous_version_code" in contract:
        previous = contract["previous_version_code"]
        if type(previous) is not int or previous < 1:
            raise ValueError(f"{path}: previous_version_code must be a positive integer")
    contract["upload_certificate_sha256"] = contract["upload_certificate_sha256"].lower()
    return contract


def run_tool(*args):
    return subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )


def diagnostic(result):
    lines = (result.stderr or result.stdout).strip().splitlines()
    return lines[0] if lines else f"exit {result.returncode}"


def check_bundle(bundle, contract, bundletool):
    checks = []

    def record(name, expected, actual, passed):
        checks.append({
            "name": name, "expected": expected, "actual": actual,
            "status": "PASS" if passed else "FAIL",
        })

    java = str(Path(os.environ["JAVA_HOME"]) / "bin/java") if os.environ.get("JAVA_HOME") else "java"
    cmd = [java, "-jar", str(bundletool)]
    validation = run_tool(*cmd, "validate", f"--bundle={bundle}")
    record("structure", "valid AAB", diagnostic(validation) if validation.returncode else "valid AAB",
           validation.returncode == 0)
    if not validation.returncode:
        dump = run_tool(*cmd, "dump", "manifest", f"--bundle={bundle}", "--module=base")
        if dump.returncode:
            record("manifest", "readable base manifest", diagnostic(dump), False)
        else:
            manifest = ElementTree.fromstring(dump.stdout)
            raw_code = manifest.get(ANDROID + "versionCode", "")
            actual = {
                "application_id": manifest.get("package"),
                "version_code": int(raw_code) if raw_code.isdecimal() else None,
                "version_name": manifest.get(ANDROID + "versionName"),
            }
            for field, value in actual.items():
                record(field, contract[field], value, value == contract[field])
            if "previous_version_code" in contract:
                previous = contract["previous_version_code"]
                code = actual["version_code"]
                record("version_code_increased", f"> {previous}", code,
                       code is not None and code > previous)

    signer = run_tool(java, str(TOOL_DIR / "BundleSigner.java"), str(bundle))
    record("signature", "all entries signed by one certificate",
           diagnostic(signer) if signer.returncode else "verified", signer.returncode == 0)
    if not signer.returncode:
        certificate = signer.stdout.strip()
        expected = contract["upload_certificate_sha256"]
        record("upload_certificate_sha256", expected, certificate, certificate == expected)
    return checks


def write_report(path, report):
    path.mkdir(parents=True, exist_ok=True)
    (path / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        f"# AAB release preflight — {report['result']}", "",
        f"- Bundle SHA-256 `{report['sha256']}`",
        f"- Source commit `{report['commit'] or 'not supplied'}`", "",
        "| Check | Expected | Actual | Result |",
        "| --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        cells = [str(check[key]).replace("|", r"\|").replace("\n", " ")
                 for key in ("name", "expected", "actual", "status")]
        lines.append("| " + " | ".join(cells) + " |")
    (path / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--expect", type=Path, required=True, help="release contract JSON")
    parser.add_argument("--bundletool", type=Path, default=os.environ.get("BUNDLETOOL_JAR"),
                        help="path to bundletool-all JAR (or set BUNDLETOOL_JAR)")
    parser.add_argument("--report-dir", type=Path, default=Path("build/preflight"))
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA"),
                        help="source commit of the bundle, if known")
    args = parser.parse_args()
    try:
        contract = read_contract(args.expect)
        if not args.bundletool or not args.bundletool.is_file():
            raise ValueError("provide a bundletool-all JAR with --bundletool or BUNDLETOOL_JAR")
        if args.bundle.suffix.lower() != ".aab":
            raise ValueError(f"{args.bundle}: expected an .aab file")
        bundle = args.bundle.resolve()
        with bundle.open("rb") as stream:
            sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        checks = check_bundle(bundle, contract, args.bundletool.resolve())
        passed = all(check["status"] == "PASS" for check in checks)
        report = {"result": "PASS" if passed else "FAIL", "bundle": bundle.name,
                  "sha256": sha256, "commit": args.commit, "checks": checks}
        write_report(args.report_dir, report)
    except (OSError, ValueError, ElementTree.ParseError) as error:
        print(f"Preflight error: {error}", file=sys.stderr)
        return 2

    print(f"{report['result']}: {args.report_dir / 'report.md'}")
    for check in checks:
        if check["status"] == "FAIL":
            print(f"  {check['name']}: expected {check['expected']}, got {check['actual']}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
