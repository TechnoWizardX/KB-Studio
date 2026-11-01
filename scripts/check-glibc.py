#!/usr/bin/env python3
"""Report the glibc symbol versions required by a PyInstaller onefile bundle."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

VERSION_RE = re.compile(r"GLIBC_(\d+(?:\.\d+)*)")


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def read_versions(path: Path) -> set[str]:
    result = subprocess.run(
        ["readelf", "--version-info", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    return set(VERSION_RE.findall(result.stdout))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", nargs="?", default="dist/KB-Studio")
    parser.add_argument(
        "--max",
        dest="maximum",
        metavar="VERSION",
        help="fail if the bundle requires a newer glibc",
    )
    args = parser.parse_args()

    if shutil.which("readelf") is None:
        print("error: readelf not found (install binutils)", file=sys.stderr)
        return 2

    binary = Path(args.binary)
    if not binary.is_file():
        print(f"error: not found: {binary}", file=sys.stderr)
        return 2

    bootloader = read_versions(binary)
    highest = max(bootloader, key=version_tuple, default="0")
    required_by: dict[str, list[str]] = {}

    archive = CArchiveReader(str(binary))
    with tempfile.TemporaryDirectory(prefix="kb-studio-glibc-") as tmp:
        tmp_path = Path(tmp)
        count = 0
        for name, entry in archive.toc.items():
            if entry[-1] != "b":
                continue
            data = archive.extract(name)
            if not data.startswith(b"\x7fELF"):
                continue
            count += 1
            path = tmp_path / f"{count:04d}-{Path(name).name}"
            path.write_bytes(data)
            versions = read_versions(path)
            if not versions:
                continue
            version = max(versions, key=version_tuple)
            required_by.setdefault(version, []).append(name)
            if version_tuple(version) > version_tuple(highest):
                highest = version

    print(f"{binary}: {count} ELF files in the bundle")
    print(f"  bootloader: {max(bootloader, key=version_tuple, default='0')}")
    print(f"  bundled:    {highest}")
    for name in sorted(required_by.get(highest, [])):
        print(f"    {name}")

    if args.maximum and version_tuple(highest) > version_tuple(args.maximum):
        print(
            f"error: requires glibc {highest}, limit is {args.maximum}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
