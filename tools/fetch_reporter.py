# SPDX-License-Identifier: Apache-2.0
"""Development/CI only: fetch one reviewed, version-pinned reporter release."""
import argparse
import hashlib
import platform
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def fetch(distributions=False):
    tag = (ROOT / "reporter-release.txt").read_text().strip()
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("reporter-release.txt must contain an exact published version tag")
    destination = ROOT / "artifacts" / "reporter"
    destination.mkdir(parents=True, exist_ok=True)
    filename = f"livingproof_capability_report-{tag[1:]}-py3-none-any.whl"
    base = ("https://github.com/Living-Proof-Labs/livingproof-capability-report/"
            f"releases/download/{tag}")
    with urlopen(base + "/SHA256SUMS", timeout=60) as response:
        checksums = response.read().decode()
    filenames = [filename]
    if distributions:
        architecture = {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()]
        filenames += [f"livingproof-capability-report_{tag[1:]}_all.deb",
                      f"wheelhouse-{architecture}.tar.gz"]
    for filename in filenames:
        expected = {line.split()[0] for line in checksums.splitlines()
                    if len(line.split()) == 2 and line.split()[1] == filename}
        if len(expected) != 1:
            raise ValueError(f"Expected one consistent published checksum for {filename}")
        with urlopen(base + "/" + filename, timeout=60) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() not in expected:
            raise ValueError("Reporter release checksum mismatch")
        (destination / filename).write_bytes(content)
    source = destination / "source"
    if source.exists():
        actual = subprocess.check_output(["git", "-C", str(source), "describe", "--tags",
                                          "--exact-match"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"],
                                        text=True).strip()
        if actual != tag or dirty:
            raise ValueError("Existing reporter source must be clean at the pinned release tag")
    else:
        subprocess.run(["git", "clone", "--depth", "1", "--branch", tag,
                        "https://github.com/Living-Proof-Labs/livingproof-capability-report.git",
                        str(source)], check=True)
    print(f"Verified reporter {tag}: {filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--distributions", action="store_true")
    fetch(parser.parse_args().distributions)
