"""Assert outputs from the remotely invoked APK 16 KB Action."""

import json
import os
from pathlib import Path


for prefix, status, code, outcome in (
    ("PASS", "pass", "0", "success"),
    ("FAIL", "fail", "1", "failure"),
    ("INVALID", "invalid", "2", "failure"),
    ("NO_NATIVE", "not_applicable", "3", "success"),
):
    assert os.environ[prefix + "_STATUS"] == status, prefix
    assert os.environ[prefix + "_CODE"] == code, prefix
    assert os.environ[prefix + "_OUTCOME"] == outcome, prefix
    report = json.loads(Path(os.environ[prefix + "_REPORT"]).read_text(encoding="utf-8"))
    assert report["status"] == status, report
    assert Path(report["apk"]).is_file(), report
    if status == "fail":
        libraries = {item["entry"].split("/")[-1]: item["origin"] for item in report["libraries"]}
        assert libraries["libunique.so"]["status"] == "single_candidate", libraries
        assert libraries["libshared.so"]["status"] == "multiple_candidates", libraries
        assert libraries["libchanged.so"]["status"] == "unknown", libraries
        assert [candidate["coordinate"] for candidate in libraries["libshared.so"]["candidates"]] == [
            "example:first:1.0", "example:second:1.0",
        ], libraries
        assert libraries["libchanged.so"]["candidates"] == [], libraries
    print(prefix + " verified with checker exit " + code)
