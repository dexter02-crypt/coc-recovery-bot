#!/usr/bin/env python3
"""Build the flat source archive. Exit codes: 0 built, 1 refused/error, 2 usage.

Validation precedes all output writes. Research gaps remain unresolved when the
owner explicitly chooses --allow-gaps; the override only permits packaging.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
from pathlib import Path
import tempfile
from typing import Dict, Optional, Sequence, Union
import zipfile


REQUIRED = (
    "net.py", "coc.py", "coc_recover.py", "readiness.py",
    "support_driver.py", "attempts.py", "probe.py", "scrape.py",
    "selftest.py", "build.py", "sources.json", "obstacles.json",
    "profile.json", "gaps.csv", "README.md", "report.md",
    "research_prompt.md",
)
GAP_HEADER = (
    "id", "area", "what_is_missing", "why_it_matters", "how_to_get_it",
    "blocking", "affects_files",
)
ARCHIVE_NAME = "coc-recover.zip"
MANIFEST_NAME = "MANIFEST.sha256"


class BuildError(Exception):
    """An explicit build refusal or source/output error."""


def _read_sources(root: Path, allow_gaps: bool) -> Dict[str, bytes]:
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    if missing:
        raise BuildError("Missing required files: " + ", ".join(missing))
    try:
        contents = {name: (root / name).read_bytes() for name in REQUIRED}
        reader = csv.DictReader(io.StringIO(contents["gaps.csv"].decode("utf-8-sig")))
        if tuple(reader.fieldnames or ()) != GAP_HEADER:
            raise BuildError("gaps.csv has an invalid header")
        gaps = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise BuildError("Cannot read source files: " + str(exc)) from exc
    if any(row.get("blocking") not in ("yes", "no") for row in gaps):
        raise BuildError("gaps.csv blocking values must be yes or no")
    blocking = [row.get("id") or "unnamed" for row in gaps if row["blocking"] == "yes"]
    if blocking and not allow_gaps:
        raise BuildError(
            "Blocking research gaps: " + ", ".join(blocking)
            + ". Use --allow-gaps to package an explicitly incomplete toolkit."
        )
    return contents


def build(root: Optional[Union[str, Path]] = None, allow_gaps: bool = False) -> Path:
    """Return the archive path after validation and deterministic packaging."""
    directory = Path(root).resolve() if root is not None else Path(__file__).resolve().parent
    contents = _read_sources(directory, allow_gaps)
    manifest = "".join(
        hashlib.sha256(contents[name]).hexdigest() + "  " + name + "\n"
        for name in sorted(contents)
    ).encode("utf-8")
    archive = directory / ARCHIVE_NAME
    try:
        with tempfile.TemporaryDirectory(prefix=".coc-build-", dir=str(directory)) as staging:
            staging_path = Path(staging)
            temporary_archive = staging_path / ARCHIVE_NAME
            with zipfile.ZipFile(
                temporary_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
            ) as output:
                members = dict(contents)
                members[MANIFEST_NAME] = manifest
                for name, payload in sorted(members.items()):
                    item = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    item.create_system = 3
                    item.external_attr = 0o100644 << 16
                    item.compress_type = zipfile.ZIP_DEFLATED
                    output.writestr(item, payload)
            temporary_manifest = staging_path / MANIFEST_NAME
            temporary_manifest.write_bytes(manifest)
            os.replace(str(temporary_manifest), str(directory / MANIFEST_NAME))
            os.replace(str(temporary_archive), str(archive))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise BuildError("Cannot write archive: " + str(exc)) from exc
    return archive


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Build CLI; return 0 on success and 1 on a deliberate refusal or error."""
    parser = argparse.ArgumentParser(description="Build the flat ownership-dossier toolkit")
    parser.add_argument("--allow-gaps", action="store_true", help="package with unresolved blocking research gaps")
    parser.add_argument("--root", type=Path, default=None, help="directory containing the 17 source files")
    args = parser.parse_args(argv)
    try:
        archive = build(args.root, args.allow_gaps)
    except BuildError as exc:
        print("REFUSED: " + str(exc))
        return 1
    print(str(archive))
    print(str(archive.parent / MANIFEST_NAME))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
