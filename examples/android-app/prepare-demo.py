"""Sign the built example with a disposable key and create reproducible test cases."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
UNSIGNED = ROOT / "examples/android-app/app/build/outputs/bundle/release/app-release.aab"
OUT = ROOT / "build/demo"


def jdk_tool(name):
    java_home = os.environ.get("JAVA_HOME")
    return str(Path(java_home) / "bin" / name) if java_home else name


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(UNSIGNED, OUT / "unsigned.aab")
    bundle = OUT / "candidate.aab"
    with tempfile.TemporaryDirectory() as directory:
        key = Path(directory) / "demo.p12"
        subprocess.run(
            [jdk_tool("keytool"), "-genkeypair", "-keystore", str(key), "-storepass", "changeit",
             "-alias", "demo", "-keyalg", "RSA", "-keysize", "2048",
             "-validity", "365", "-dname", "CN=Disposable Delivery Demo"],
            check=True,
        )
        certificate = subprocess.check_output(
            [jdk_tool("keytool"), "-exportcert", "-keystore", str(key), "-storepass", "changeit",
             "-alias", "demo"],
        )
        subprocess.run(
            [jdk_tool("jarsigner"), "-keystore", str(key), "-storepass", "changeit",
             "-signedjar", str(bundle), str(UNSIGNED), "demo"],
            check=True,
        )
    contract = {
        "application_id": "io.github.leejunhao791.deliverydemo",
        "version_code": 2,
        "version_name": "1.1",
        "upload_certificate_sha256": hashlib.sha256(certificate).hexdigest(),
        "previous_version_code": 1,
    }
    (OUT / "release.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    contract["previous_version_code"] = 2
    (OUT / "repeat-version.json").write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )
    with ZipFile(bundle) as original, ZipFile(OUT / "tampered.aab", "w") as changed:
        for entry in original.infolist():
            data = original.read(entry)
            if entry.filename == "base/dex/classes.dex":
                data += b"tampered"
            changed.writestr(entry, data)
    print(f"Demo artifacts are in {OUT}")


if __name__ == "__main__":
    main()
