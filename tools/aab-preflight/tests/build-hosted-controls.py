"""Build two disposable signed alignment controls from the hosted demo AAB."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

root = Path("build/hosted-alignment-proof")
module = root / "base.zip"
fixture = root / "fixture"
bundletool = ["java", "-jar", os.environ["BUNDLETOOL_JAR"]]
seed = root / "input/candidate.aab"
assert hashlib.sha256(seed.read_bytes()).hexdigest() == (
    "8f97fd69755c2b784302b01302ebbdf6f9396ef1bd77217f2c0b6daf14c27acc"
)
subprocess.run([sys.executable, "-B", "examples/apk-16kb-action/fixtures.py", sys.argv[1],
                str(fixture)], check=True)
with ZipFile(fixture / "passing app.apk") as generated:
    elf = generated.read("lib/arm64-v8a/libaligned.so")
print("Shared synthetic ELF SHA-256", hashlib.sha256(elf).hexdigest())
with ZipFile(seed) as source, ZipFile(module, "w") as base:
    for member in source.infolist():
        if member.filename.startswith("base/") and not member.is_dir():
            base.writestr(member.filename.removeprefix("base/"), source.read(member))
    base.writestr("lib/arm64-v8a/libaligned.so", elf)

key = root / "proof.p12"
subprocess.run(["keytool", "-genkeypair", "-keystore", str(key), "-storetype", "PKCS12",
                "-storepass", "changeit", "-alias", "proof", "-keyalg", "RSA",
                "-keysize", "2048", "-validity", "1", "-dname", "CN=Disposable AAB CI proof"],
               check=True)
certificate = subprocess.check_output(["keytool", "-exportcert", "-keystore", str(key),
                                       "-storepass", "changeit", "-alias", "proof"])
contract = json.loads((root / "input/release.json").read_bytes())
contract["upload_certificate_sha256"] = hashlib.sha256(certificate).hexdigest()

for alignment in ("16K", "4K"):
    config = root / f"config-{alignment}.json"
    config.write_text(json.dumps({"optimizations": {"uncompressNativeLibraries": {
        "enabled": True, "alignment": f"PAGE_ALIGNMENT_{alignment}",
    }}}), encoding="utf-8")
    unsigned = root / f"unsigned-{alignment}.aab"
    output = root / alignment
    output.mkdir()
    subprocess.run([*bundletool, "build-bundle", f"--modules={module}", f"--config={config}",
                    f"--output={unsigned}"], check=True)
    subprocess.run(["jarsigner", "-keystore", str(key), "-storepass", "changeit",
                    "-signedjar", str(output / "candidate.aab"), str(unsigned), "proof"], check=True)
    (output / "release.json").write_text(json.dumps(contract), encoding="utf-8")
