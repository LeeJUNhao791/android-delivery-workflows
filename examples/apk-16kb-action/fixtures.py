"""Prepare synthetic APKs for the cross-repository Action contract check."""

import runpy
import struct
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


toolkit, output = map(Path, sys.argv[1:])
generate = toolkit / "skills/apk-page-size-check/examples/generate_origins.py"
runpy.run_path(str(generate))["generate"](output)

# The toolkit example contains single, multiple and unknown AAR matches.
# Change only the synthetic ELF alignment to create a passing input as well.
with ZipFile(output / "app.apk") as source:
    aligned = bytearray(source.read("lib/arm64-v8a/libunique.so"))
struct.pack_into("<Q", aligned, 112, 16384)  # ELF64 PT_LOAD p_align
with ZipFile(output / "passing app.apk", "w", compression=ZIP_DEFLATED) as archive:
    archive.writestr("AndroidManifest.xml", "synthetic fixture manifest")
    archive.writestr("lib/arm64-v8a/libaligned.so", aligned)
with ZipFile(output / "no-native.apk", "w") as archive:
    archive.writestr("AndroidManifest.xml", "synthetic fixture manifest")
(output / "invalid.apk").write_bytes(b"synthetic invalid APK")
