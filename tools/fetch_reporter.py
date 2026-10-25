# SPDX-License-Identifier: Apache-2.0
"""Development/CI only: fetch one reviewed, version-pinned reporter release."""
import hashlib
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def fetch():
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
        raise ValueError("Use a fresh artifacts/reporter directory for release verification")
    subprocess.run(["git", "clone", "--depth", "1", "--branch", tag,
                    "https://github.com/Living-Proof-Labs/livingproof-capability-report.git",
                    str(source)], check=True)
    print(f"Verified reporter {tag}: {filename}")


if __name__ == "__main__":
    fetch()
