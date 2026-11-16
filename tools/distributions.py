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


def registry_runtime_packages(lock):
    """Registry wheels for the root package's runtime dependencies.

    The reporter wheelhouse is extracted first and can carry an older copy of
    the same distribution. Staging replaces that copy with the locked wheel.
    URL-sourced dependencies such as livingproof-common are fetched separately.
    """
    root = next(package for package in lock["package"] if package["name"] == "livingproof")
    names = {item["name"] for item in root["dependencies"]}
    return [package for package in lock["package"]
            if package["name"] in names and "registry" in package.get("source", {})]


def _fetch_wheel(url):
    with urlopen(url, timeout=60) as response:
        return response.read()


def _wheel_distribution(filename):
    return filename.split("-", 1)[0]


def stage_locked_runtime_wheels(lock, wheels, fetch=_fetch_wheel):
    """Write locked runtime wheels, replacing any other version already present."""
    wheels = Path(wheels)
    for package in registry_runtime_packages(lock):
        asset, = package["wheels"]
        content = fetch(asset["url"])
        if "sha256:" + hashlib.sha256(content).hexdigest() != asset["hash"]:
            raise ValueError(f"Locked {package['name']} wheel checksum mismatch")
        filename = asset["url"].rsplit("/", 1)[1]
        distribution = _wheel_distribution(filename)
        for existing in list(wheels.glob("*.whl")):
            if _wheel_distribution(existing.name) == distribution and existing.name != filename:
                existing.unlink()
        (wheels / filename).write_bytes(content)


def build():
    subprocess.run(["python", "tools/fetch_reporter.py", "--distributions"], cwd=ROOT, check=True)
    wheel, = (ROOT / "dist").glob("livingproof-*.whl")
    version = wheel.name.split("-")[1]
    reporter_version = (ROOT / "reporter-release.txt").read_text().split()[0][1:]
    with tarfile.open(ROOT / f"artifacts/reporter/wheelhouse-{ARCH}.tar.gz") as archive:
        archive.extractall(ROOT / "dist", filter="data")
    shutil.copyfile(wheel, ROOT / "dist/wheels" / wheel.name)
    common = ROOT / "dist/livingproof_common-1.0.0-py3-none-any.whl"
    shutil.copyfile(common, ROOT / "dist/wheels" / common.name)
    # Reporter wheelhouse copies of root runtime dependencies are replaced with
    # the locked wheels. livingproof-common was copied above from its reviewed release.
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    stage_locked_runtime_wheels(lock, ROOT / "dist/wheels")
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
