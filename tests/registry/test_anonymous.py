# SPDX-License-Identifier: Apache-2.0
"""Fresh runners pull public version manifests without registry credentials."""
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import tarfile
import hashlib

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def anonymous_docker_config():
    with tempfile.TemporaryDirectory() as config:
        original = os.environ.get("DOCKER_CONFIG")
        os.environ["DOCKER_CONFIG"] = config
        yield
        if original is None:
            os.environ.pop("DOCKER_CONFIG", None)
        else:
            os.environ["DOCKER_CONFIG"] = original


@pytest.mark.parametrize("suffix,mode", [("", "root"), ("-reporting", "combined")])
def test_anonymous_native_registry(suffix, mode):
    image = f"ghcr.io/living-proof-labs/livingproof:{os.environ['VERSION']}{suffix}"
    subprocess.run(["docker", "pull", image], check=True)
    tagged = image
    digests = json.loads(subprocess.check_output(
        ["docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"], text=True))
    image, = [digest for digest in digests
              if digest.startswith("ghcr.io/living-proof-labs/livingproof@sha256:")]
    subprocess.run(["docker", "pull", image], check=True)
    version = subprocess.check_output(["docker", "run", "--rm", image, "--version"], text=True)
    assert version.splitlines()[0] == f"livingproof, version {os.environ['VERSION']}"
    arch = subprocess.check_output(["docker", "image", "inspect", image,
                                    "--format", "{{.Architecture}}"], text=True).strip()
    assert arch == {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()]
    filename = "reporting-image" if suffix else "image"
    with tarfile.open(ROOT / f"dist/{filename}-{arch}.tar") as archive:
        manifest = json.load(archive.extractfile("manifest.json"))
        entry, = manifest
        config = archive.extractfile(entry["Config"]).read()
        expected_id = "sha256:" + hashlib.sha256(config).hexdigest()
    actual_id = subprocess.check_output(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True).strip()
    assert actual_id == expected_id, "Registry image differs from the tested CI-built archive"
    installed = subprocess.check_output(
        ["docker", "run", "--rm", "--entrypoint", "python", image, "-c",
         "import importlib.metadata; print(importlib.metadata.version('livingproof'))"], text=True)
    assert installed.strip() == os.environ["VERSION"]
    subprocess.run(["docker", "run", "--rm", image, "--help"], check=True)
    subprocess.run(["docker", "run", "--rm", "--user", "65532:65532", "--entrypoint", "python",
                    "-e", f"COMPATIBILITY_HOST_MACHINE={platform.machine()}",
                    "-v", f"{ROOT}/tools/consumer_probe.py:/probe.py:ro",
                    "-v", f"{ROOT}/artifacts/reporter/source/examples/bundle:/input:ro",
                    image, "/probe.py", mode, "/tmp/registry-result.json"], check=True)

    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    record = output / f"registry-{arch}.json"
    data = json.loads(record.read_text()) if record.exists() else {}
    data[mode] = {"tag": tagged, "image": image, "platform": f"linux/{arch}",
                  "package_version": os.environ["VERSION"], "local_image_id": actual_id,
                  "matches_ci_archive": True, "outcome": "PASS"}
    record.write_text(json.dumps(data, indent=2) + "\n")
    (output / f"registry-{arch}.md").write_text(
        f"\n## Verified containers: linux/{arch}\n\n"
        "These are registry manifest digests, not local image IDs.\n\n" +
        "\n".join(f"### {name}\n\n```sh\ndocker pull --platform linux/{arch} {row['image']}\n"
                  f"docker run --rm --platform linux/{arch} {row['image']} --help\n```\n"
                  for name, row in sorted(data.items())))
