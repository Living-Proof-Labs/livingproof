# SPDX-License-Identifier: Apache-2.0
"""Fresh runners pull public version manifests without registry credentials."""
import os
from pathlib import Path
import platform
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("suffix,mode", [("", "root"), ("-reporting", "combined")])
def test_anonymous_native_registry(suffix, mode):
    image = f"ghcr.io/living-proof-labs/livingproof:{os.environ['VERSION']}{suffix}"
    subprocess.run(["docker", "pull", image], check=True)
    arch = subprocess.check_output(["docker", "image", "inspect", image,
                                    "--format", "{{.Architecture}}"], text=True).strip()
    assert arch == {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()]
    subprocess.run(["docker", "run", "--rm", image, "--help"], check=True)
    subprocess.run(["docker", "run", "--rm", "--user", "65532:65532", "--entrypoint", "python",
                    "-e", f"COMPATIBILITY_HOST_MACHINE={platform.machine()}",
                    "-v", f"{ROOT}/tools/consumer_probe.py:/probe.py:ro",
                    "-v", f"{ROOT}/artifacts/reporter/source/examples/bundle:/input:ro",
                    image, "/probe.py", mode, "/tmp/registry-result.json"], check=True)
