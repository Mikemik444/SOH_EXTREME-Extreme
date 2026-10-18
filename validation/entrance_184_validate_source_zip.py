"""Verify fresh source ZIP timestamps with real extraction across time zones."""
from datetime import datetime, timezone
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prepare_source_delivery import write_source_archive


def main():
    created = datetime.now(timezone.utc).replace(microsecond=0)
    files = {"soh/SohExtremeVersion.h": (ROOT / "source/soh/SohExtremeVersion.h").read_bytes()}
    cases = []
    with tempfile.TemporaryDirectory(prefix="soh-source-timestamps-") as temporary:
        directory = Path(temporary)
        archive = directory / "source-files.zip"
        stamp = write_source_archive(archive, files, created)
        with zipfile.ZipFile(archive) as zipped:
            for info in zipped.infolist():
                extra = info.extra
                ut_id, ut_size, flags, unix_time = struct.unpack("<HHBI", extra[:9])
                assert (ut_id, ut_size, flags, unix_time) == (0x5455, 5, 1, int(created.timestamp()))
                ntfs_id, ntfs_size, reserved, tag, size, modified, accessed, born = struct.unpack("<HHIHHQQQ", extra[9:])
                assert (ntfs_id, ntfs_size, reserved, tag, size) == (0x000A, 32, 0, 1, 24)
                assert modified == accessed == born
                epoch_delta = (created - datetime(1601, 1, 1, tzinfo=timezone.utc)).total_seconds()
                assert modified == int(epoch_delta) * 10_000_000
                assert info.date_time == stamp and info.date_time != (2026, 10, 17, 0, 0, 0)
        for index, zone in enumerate(("UTC0", "UTC-14", "UTC+12")):
            destination = directory / str(index)
            environment = dict(os.environ, TZ=zone)
            completed = subprocess.run(["unzip", "-qq", str(archive), "-d", str(destination)],
                                       env=environment, capture_output=True, text=True, check=True)
            output = destination / "soh/SohExtremeVersion.h"
            assert output.read_bytes() == files["soh/SohExtremeVersion.h"]
            assert int(output.stat().st_mtime) == int(created.timestamp())
            cases.append({"timezone": zone, "exit_code": completed.returncode,
                          "modification_unix_seconds": int(output.stat().st_mtime),
                          "matches_package_creation_time": True, "content_preserved": True})
    report = {"status": "passed", "target_version": "1.8.4", "cases": cases,
              "unzip_version": subprocess.check_output(["unzip", "-v"], text=True).splitlines()[0],
              "package_created_utc": created.isoformat().replace("+00:00", "Z"),
              "source_zip_writer_sha256": sha256(inspect.getsource(write_source_archive).encode()).hexdigest(),
              "source_header_sha256": sha256(files["soh/SohExtremeVersion.h"]).hexdigest(),
              "central_utc_and_ntfs_fields_verified": True,
              "scope": "Actual current outer ZIP writer and Info-ZIP extraction in three time zones. Windows Explorer extraction was not run; clean-first remains the rebuild guarantee.",
              "format_references": [
                  "https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT",
                  "https://commons.apache.org/proper/commons-compress/xref/org/apache/commons/compress/archivers/zip/X5455_ExtendedTimestamp.html",
              ]}
    (ROOT / "tests/entrance_184_source_zip_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
