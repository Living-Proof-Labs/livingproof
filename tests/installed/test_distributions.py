# SPDX-License-Identifier: Apache-2.0
"""Native installed-consumer tests with individual visible CI results."""
import os
from pathlib import Path
import platform
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARCH = {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()]
VERSION = next((ROOT / "dist").glob("livingproof-*.whl")).name.split("-")[1]
EVIDENCE = (f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/"
            f"{os.environ['GITHUB_RUN_ID']}" if "GITHUB_RUN_ID" in os.environ else "local execution")


@pytest.fixture(scope="session", autouse=True)
def fresh_probe_records():
    records = ROOT / "dist/compatibility"
    records.mkdir(exist_ok=True)
    for name in ("root-image", "combined-image", "debian-12-slim", "debian-13-slim",
                 "ubuntu-24.04", "wheel-source"):
        (records / f"{name}.json").unlink(missing_ok=True)


def run(args, env=None):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, env=env)
    print(result.stdout)
    print(result.stderr)
    assert result.returncode == 0
    return result.stdout


def docker():
    records = ROOT / "dist/compatibility"
    records.mkdir(exist_ok=True)
    args = ["docker", "run", "--rm"]
    if os.environ.get("PACKAGE_NETWORK"):
        args += ["--network", os.environ["PACKAGE_NETWORK"]]
    if os.environ.get("PACKAGE_PROXY_HOST"):
        args += ["--add-host", os.environ["PACKAGE_PROXY_HOST"]]
    for name in ("http_proxy", "https_proxy", "LIVINGPROOF_GITHUB_TOKEN"):
        if name in os.environ:
            args += ["-e", name]
    if os.environ.get("PACKAGE_CA_BUNDLE"):
        args += ["-v", f"{os.environ['PACKAGE_CA_BUNDLE']}:/run/ca:ro",
                 "-e", "SSL_CERT_FILE=/run/ca", "-e", "PIP_CERT=/run/ca"]
    return args + ["-v", f"{ROOT}/tools/consumer_probe.py:/probe.py:ro",
                   "-v", f"{records}:/results", "-v", f"{ROOT}/dist:/packages:ro",
                   "-v", f"{ROOT}/artifacts/reporter/livingproof-capability-report_"
                   f"{(ROOT / 'reporter-release.txt').read_text().strip()[1:]}_all.deb:/reporter.deb:ro",
                   "-v", f"{ROOT}/artifacts/reporter/source/examples/bundle:/input:ro",
                   "-e", f"COMPATIBILITY_HOST_MACHINE={platform.machine()}",
                   "-e", f"COMPATIBILITY_EVIDENCE={EVIDENCE}"]


@pytest.mark.parametrize("variant,mode", [("", "root"), ("-reporting", "combined")])
def test_saved_container(variant, mode):
    filename = "reporting-image" if variant else "image"
    run(["docker", "load", "-i", str(ROOT / f"dist/{filename}-{ARCH}.tar")])
    image = f"ghcr.io/living-proof-labs/livingproof:{VERSION}{variant}-{ARCH}"
    assert "capability" in run([*docker(), image, "--help"])
    if variant:
        run([*docker(), image, "capability", "report", "validate", "/input/manifest.json"])
    run([*docker(), "--user", f"{os.getuid()}:{os.getgid()}",
         "--entrypoint", "python", image, "/probe.py", mode,
         f"/results/{mode}-image.json"])


@pytest.mark.parametrize("distribution", ["debian:12-slim", "debian:13-slim", "ubuntu:24.04"])
def test_debian_plugins(distribution):
    # Only package assets, fixture data and this probe are mounted, never app source.
    command = ("set -eu; apt-get update -qq; apt-get install -y /packages/livingproof_*_all.deb /packages/python3-livingproof-common_*_all.deb; "
               "cd /tmp; /usr/bin/python3 /probe.py debian /results/"
               + distribution.replace(":", "-") + ".json --reporter-deb "
               "/reporter.deb")
    run([*docker(), distribution, "sh", "-c", command])


def test_wheel_source_and_plugin():
    run(["python", "tools/smoke.py"], env={**os.environ,
        "SMOKE_RECORD": str(ROOT / "dist/compatibility/wheel-source.json"),
        "COMPATIBILITY_EVIDENCE": EVIDENCE})


def test_portable_debian_metadata():
    package, = (ROOT / "dist").glob("livingproof_*_all.deb")
    assert run(["dpkg-deb", "--field", str(package), "Architecture"]).strip() == "all"
    dependencies = run(["dpkg-deb", "--field", str(package), "Depends"])
    assert "python3-click" in dependencies
    assert "livingproof-capability-report" not in dependencies
    listing = run(["dpkg-deb", "--contents", str(package)])
    assert "usr/lib/python3/dist-packages/livingproof" in listing
    assert "entry_points.txt" in listing
    assert ".so" not in listing


@pytest.mark.parametrize("distribution", ["debian:12-slim", "debian:13-slim", "ubuntu:24.04"])
def test_bash_completion_lifecycle(distribution):
    command = (
        "set -eu; apt-get update -qq; "
        "apt-get install -y bash-completion /packages/livingproof_*_all.deb /packages/python3-livingproof-common_*_all.deb; "
        "dpkg-query -S /usr/share/bash-completion/completions/livingproof; "
        "python3 /completion_probe.py absent; "
        "apt-get install -y /reporter.deb; "
        "python3 /completion_probe.py installed; "
        "apt-get remove -y livingproof-capability-report; "
        "python3 /completion_probe.py absent; "
        "apt-get remove -y livingproof; "
        "test ! -e /usr/share/bash-completion/completions/livingproof; "
        "bash --noprofile --norc -c 'source /usr/share/bash-completion/bash_completion; "
        "_completion_loader livingproof || :; "
        "! declare -F _livingproof_completion; ! command -v livingproof'"
    )
    run([*docker(), "-v", f"{ROOT}/tools/completion_probe.py:/completion_probe.py:ro",
         distribution, "sh", "-c", command])


@pytest.mark.parametrize("distribution", ["debian:13-slim", "ubuntu:noble"])
def test_default_bash_startup_and_cli_recovery(distribution):
    command = ("apt-get update -qq && apt-get install -y --no-install-recommends python3 "
               "&& python3 /tools/completion_startup_probe.py")
    run([*docker(), "-v", f"{ROOT}/tools:/tools:ro", distribution, "sh", "-c", command])


@pytest.mark.parametrize("distribution", ["debian:12-slim", "debian:13-slim", "ubuntu:24.04"])
@pytest.mark.parametrize("mode", ["deb", "wheel"])
def test_explicit_plugin_management(distribution, mode):
    if mode == "deb":
        setup = ("apt-get install -y ca-certificates /packages/livingproof_*_all.deb "
                 "/packages/python3-livingproof-common_*_all.deb; "
                 "python3 /management_probe.py deb")
    else:
        setup = ("apt-get install -y ca-certificates python3-venv; "
                 "python3 -m venv /opt/test; "
                 "/opt/test/bin/pip install --no-index --find-links=/packages/wheels livingproof; "
                 "PATH=/opt/test/bin:$PATH /opt/test/bin/python /management_probe.py wheel")
    run([*docker(), "-e", "DEBIAN_FRONTEND=noninteractive",
         "-v", f"{ROOT}/tools/plugin_management_probe.py:/management_probe.py:ro",
         distribution, "sh", "-c", "set -eu; apt-get update -qq; " + setup])
