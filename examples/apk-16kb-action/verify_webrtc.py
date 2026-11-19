"""Build a ZIP-alignment control and verify the published Action reports."""

import json
import sys
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo


def create_control(apk, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(apk) as source, ZipFile(output, "x") as target:
        for entry in source.infolist():
            # Recreate the local headers without the original APK ZIP padding.
            copy = ZipInfo(entry.filename)
            copy.compress_type = entry.compress_type
            data_offset = target.fp.tell() + 30 + len(copy.filename.encode("utf-8"))
            if copy.compress_type == ZIP_STORED and copy.filename.endswith(".so") and data_offset % 16384 == 0:
                copy.extra = b"\xfe\xca\x01\x00\x00"  # One byte in a valid ZIP extra field.
            target.writestr(copy, source.read(entry))


def verify(pass_report, fail_report, manifest_file):
    passed, failed, manifest = (
        json.loads(path.read_text(encoding="utf-8")) for path in (pass_report, fail_report, manifest_file)
    )
    assert manifest["consumer_configuration"] == ":app:debugRuntimeClasspath", manifest
    webrtc = [item["coordinate"] for item in manifest["artifacts"]
              if item["coordinate"].startswith("io.github.webrtc-sdk:android:")]
    assert len(webrtc) == 1, manifest
    assert passed["status"] == "pass", passed
    assert failed["status"] == "fail", failed
    assert failed["aar_manifest"]["consumer_configuration"] == manifest["consumer_configuration"], failed

    passing = {item["entry"]: item for item in passed["libraries"]}
    failing = {item["entry"]: item for item in failed["libraries"]}
    with ZipFile(passed["apk"]) as original, ZipFile(failed["apk"]) as control:
        for abi in ("arm64-v8a", "x86_64"):
            name = f"lib/{abi}/libjingle_peerconnection_so.so"
            assert (passing[name]["elf"], passing[name]["zip"]) == ("pass", "pass"), passing[name]
            assert (failing[name]["elf"], failing[name]["zip"]) == ("pass", "fail"), failing[name]
            assert original.read(name) == control.read(name), name
            origin = failing[name]["origin"]
            assert origin["status"] == "single_candidate", origin
            assert [item["coordinate"] for item in origin["candidates"]] == webrtc, origin
            print(f"{abi}: original passed, ZIP control failed with candidate {webrtc[0]}")


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    if command == "prepare":
        create_control(*map(Path, args))
    elif command == "verify":
        verify(*map(Path, args))
    else:
        raise SystemExit(f"Unknown command: {command}")
