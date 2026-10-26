# SPDX-License-Identifier: Apache-2.0
"""Black-box scenarios: only release fixture data is mounted into fresh consumers."""
import platform
from pathlib import Path
import shlex
import subprocess

from pytest_bdd import given, parsers, scenarios, then, when

ROOT = Path(__file__).resolve().parents[2]
scenarios("installed.feature")


@given(parsers.parse("the {variant} installed image"), target_fixture="consumer")
def consumer(variant):
    assert variant in ("root-only", "reporting")
    wheel, = (ROOT / "dist").glob("livingproof-*.whl")
    version = wheel.name.split("-")[1]
    arch = {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()]
    suffix = "-reporting" if variant == "reporting" else ""
    return {"image": f"ghcr.io/living-proof-labs/livingproof:{version}{suffix}-{arch}"}


@when(parsers.parse('I run "{command}"'))
def invoke(consumer, command):
    args = shlex.split(command)
    assert args.pop(0) == "livingproof"
    fixture = ROOT / "artifacts/reporter/source/examples/bundle"
    assert fixture.is_dir(), "Run task images to fetch the pinned release fixtures"
    invocation = ["docker", "run", "--rm", "--network=none", "--read-only",
                  "--tmpfs", "/tmp", "-v", f"{fixture}:/input:ro", consumer["image"], *args]
    result = subprocess.run(invocation, capture_output=True, text=True, timeout=60)
    consumer["result"] = result
    print(f"$ {command}\nimage: {consumer['image']}\nexit: {result.returncode}\n"
          f"{result.stdout}{result.stderr}")


@then(parsers.parse("the exit status is {expected:d}"))
def exit_status(consumer, expected):
    result = consumer["result"]
    assert result.returncode == expected, result.stdout + result.stderr


@then(parsers.parse('the output contains "{text}"'))
def output_contains(consumer, text):
    result = consumer["result"]
    assert text in result.stdout + result.stderr
