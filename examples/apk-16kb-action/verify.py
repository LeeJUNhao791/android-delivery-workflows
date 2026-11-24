"""Assert outputs from the remotely invoked APK 16 KB Action."""

import json
import os
import struct
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile


for prefix, status, code, outcome in (
    ("PASS", "pass", "0", "success"),
    ("FAIL", "fail", "1", "failure"),
    ("ZIP_ONLY", "fail", "1", "failure"),
    ("INVALID", "invalid", "2", "failure"),
    ("NO_NATIVE", "not_applicable", "3", "success"),
):
    assert os.environ[prefix + "_STATUS"] == status, prefix
    assert os.environ[prefix + "_CODE"] == code, prefix
    assert os.environ[prefix + "_OUTCOME"] == outcome, prefix
    report = json.loads(Path(os.environ[prefix + "_REPORT"]).read_text(encoding="utf-8"))
    assert report["status"] == status, report
    apk = Path(report["apk"])
    assert apk.is_file(), report
    if prefix == "FAIL":
        libraries = {item["entry"].split("/")[-1]: item["origin"] for item in report["libraries"]}
        assert libraries["libunique.so"]["status"] == "single_candidate", libraries
        assert libraries["libshared.so"]["status"] == "multiple_candidates", libraries
        assert libraries["libchanged.so"]["status"] == "unknown", libraries
        assert [candidate["coordinate"] for candidate in libraries["libshared.so"]["candidates"]] == [
            "example:first:1.0", "example:second:1.0",
        ], libraries
        assert libraries["libchanged.so"]["candidates"] == [], libraries
    elif prefix == "ZIP_ONLY":
        [library] = report["libraries"]
        assert (library["entry"], library["abi"], library["elf"], library["zip"]) == (
            "lib/arm64-v8a/libaligned.so", "arm64-v8a", "pass", "fail",
        ), library
        with ZipFile(apk) as control, ZipFile(apk.with_name("passing app.apk")) as passing:
            entry = control.getinfo(library["entry"])
            assert entry.compress_type == ZIP_STORED, entry
            assert control.read(entry) == passing.read(entry.filename), entry
        with apk.open("rb") as stream:
            # The ZIP local header stores both variable field lengths at byte 26.
            stream.seek(entry.header_offset + 26)
            name_size, extra_size = struct.unpack("<HH", stream.read(4))
        offset = entry.header_offset + 30 + name_size + extra_size
        assert library["zip_data_offset"] == offset and offset % 16384 != 0, library
        print(f"ARM64 ELF passed at unaligned ZIP data offset {offset}")
    print(prefix + " verified with checker exit " + code)
