# SPDX-License-Identifier: Apache-2.0
"""Build two native container variants from verified installed-package inputs."""
import hashlib
import tomllib
from urllib.request import urlopen
import os
import platform
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCH = {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()]


def build():
    subprocess.run(["python", "tools/fetch_reporter.py", "--distributions"], cwd=ROOT, check=True)
    wheel, = (ROOT / "dist").glob("livingproof-*.whl")
    version = wheel.name.split("-")[1]
    reporter_version = (ROOT / "reporter-release.txt").read_text().strip()[1:]
    with tarfile.open(ROOT / f"artifacts/reporter/wheelhouse-{ARCH}.tar.gz") as archive:
        archive.extractall(ROOT / "dist", filter="data")
    shutil.copyfile(wheel, ROOT / "dist/wheels" / wheel.name)
    common = ROOT / "dist/livingproof_common-1.0.0-py3-none-any.whl"
    shutil.copyfile(common, ROOT / "dist/wheels" / common.name)
    # Root runtime dependency, independent of the reporter's wheelhouse.
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    package, = [p for p in lock['package'] if p['name'] == 'packaging']
    asset, = package['wheels']
    with urlopen(asset['url'], timeout=60) as response:
        content = response.read()
    if 'sha256:' + hashlib.sha256(content).hexdigest() != asset['hash']:
        raise ValueError('Locked packaging wheel checksum mismatch')
    (ROOT / 'dist/wheels' / asset['url'].rsplit('/', 1)[1]).write_bytes(content)
    extra = []
    if os.environ.get("PACKAGE_NETWORK"):
        extra += ["--network", os.environ["PACKAGE_NETWORK"]]
    if os.environ.get("PACKAGE_PROXY_HOST"):
        extra += ["--add-host", os.environ["PACKAGE_PROXY_HOST"]]
    for variant, target, filename in (("", "runtime", "image"),
                                      ("-reporting", "reporting", "reporting-image")):
        image = f"ghcr.io/living-proof-labs/livingproof:{version}{variant}-{ARCH}"
        subprocess.run(["docker", "build", *extra, "--target", target,
                        "--build-arg", f"VERSION={version}", "--build-arg",
                        f"REPORTER_VERSION={reporter_version}", "-t", image, "."],
                       cwd=ROOT, check=True)
        subprocess.run(["docker", "save", "-o", str(ROOT / f"dist/{filename}-{ARCH}.tar"),
                        image], check=True)


if __name__ == "__main__":
    build()
