# SPDX-License-Identifier: Apache-2.0
"""Development/CI only: fetch one reviewed, version-pinned reporter release."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "ghcr.io/living-proof-labs/livingproof-capability-report"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def release():
    """Return the pinned tag and its image digests from reporter-release.txt.

    Line one is the exact release tag. Optional following lines are
    ``index|amd64|arm64 sha256:...``: the multi-arch index and per-arch manifests.
    """
    lines = [line.split() for line in
             (ROOT / "reporter-release.txt").read_text().splitlines() if line.strip()]
    if not lines or len(lines[0]) != 1 or not re.fullmatch(r"v\d+\.\d+\.\d+", lines[0][0]):
        raise ValueError("reporter-release.txt must contain an exact published version tag")
    digests = {}
    for line in lines[1:]:
        if (len(line) != 2 or line[0] not in ("index", "amd64", "arm64")
                or line[0] in digests or not DIGEST.fullmatch(line[1])):
            raise ValueError("reporter-release.txt digest lines must be "
                             "'index|amd64|arm64 sha256:<64 hex>'")
        digests[line[0]] = line[1]
    return lines[0][0], digests


def verify_images():
    """Check the pinned digests against the public registry (anonymous)."""
    tag, digests = release()
    if "index" not in digests:
        raise ValueError("reporter-release.txt pins no image index digest")
    raw = subprocess.check_output(["docker", "buildx", "imagetools", "inspect", "--raw",
                                   f"{IMAGE}:{tag[1:]}"])
    if "sha256:" + hashlib.sha256(raw).hexdigest() != digests["index"]:
        raise ValueError(f"{IMAGE}:{tag[1:]} index digest differs from the pin")
    platforms = {m["platform"]["architecture"]: m["digest"]
                 for m in json.loads(raw)["manifests"] if m["platform"]["os"] == "linux"}
    for architecture in ("amd64", "arm64"):
        if architecture in digests and platforms.get(architecture) != digests[architecture]:
            raise ValueError(f"{IMAGE}:{tag[1:]} {architecture} digest differs from the pin")
    print(f"Verified {IMAGE}:{tag[1:]}@{digests['index']}")


def fetch(distributions=False):
    tag, _ = release()
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
    parser.add_argument("--images", action="store_true",
                        help="only verify the pinned image digests against the registry")
    arguments = parser.parse_args()
    verify_images() if arguments.images else fetch(arguments.distributions)
