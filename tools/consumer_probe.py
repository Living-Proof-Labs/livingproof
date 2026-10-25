# SPDX-License-Identifier: Apache-2.0
"""Run inside clean consumers; the application checkout is never mounted."""
import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile


def run(args, expected=0):
    result = subprocess.run(args, cwd="/tmp", capture_output=True, text=True)
    assert result.returncode == expected, (args, result.stdout, result.stderr)
    return result.stdout + result.stderr


def root_only():
    assert "capability" in run(["livingproof", "--help"])
    assert "No packages are installed automatically" in run(
        ["livingproof", "capability", "report"], expected=1)


def combined():
    from livingproof.cli import main
    from livingproof_capability_report import grade
    assert "/workspace" not in __import__("livingproof").__file__
    assert main and grade
    with tempfile.TemporaryDirectory() as temporary:
        outputs = Path(temporary)
        for prefix, name in ((["livingproof", "capability", "report"], "nested"),
                             (["livingproof-capability-report"], "standalone")):
            run([*prefix, "validate", "/input/manifest.json"])
            run([*prefix, "grade", "/input/manifest.json", "-o", str(outputs / f"{name}.json")])
            for format in ("table", "json", "html", "csv"):
                run([*prefix, "render", str(outputs / f"{name}.json"), "--format", format,
                     "-o", str(outputs / f"{name}.{format}.out")])
            run([*prefix, "grade", "/input/manifest.json", "-o", str(outputs / f"{name}.json")], 1)
            run([*prefix, "validate", "/input/missing.json"], 2)
        assert (outputs / "nested.json").read_bytes() == (outputs / "standalone.json").read_bytes()
        for format in ("table", "json", "html", "csv"):
            assert (outputs / f"nested.{format}.out").read_bytes() == (
                outputs / f"standalone.{format}.out").read_bytes()
        report = json.loads((outputs / "nested.json").read_text())
        decisions = {d["result_id"]: d["status"] for d in report["decisions"]}
        assert decisions["v1.1.1-slow"] == "PASS"
        assert decisions["v1.2.0-slow"] == "FAIL"
        assert decisions["v1.2.0-insufficient"] == "INSUFFICIENT_EVIDENCE"
        print((outputs / "nested.table.out").read_text())
    completion = subprocess.run(["livingproof"], env={**os.environ,
        "_LIVINGPROOF_COMPLETE": "bash_complete",
        "COMP_WORDS": "livingproof capability report r", "COMP_CWORD": "3"},
        capture_output=True, text=True, check=True)
    assert "plain,render" in completion.stdout
    return {name: metadata.version(name) for name in
            ("livingproof", "livingproof-capability-report", "click", "jsonschema")}


def probe(args):
    assert platform.machine() == os.environ["COMPATIBILITY_HOST_MACHINE"]
    versions = {"livingproof": metadata.version("livingproof"), "click": metadata.version("click")}
    if args.mode in ("root", "debian"):
        root_only()
    if args.mode == "debian":
        assert __import__("livingproof").__file__.startswith("/usr/lib/python3/dist-packages/")
        run(["apt-get", "install", "-y", args.reporter_deb])
    if args.mode in ("combined", "debian"):
        versions = combined()
    if args.mode == "debian":
        assert __import__("livingproof_capability_report").__file__.startswith(
            "/usr/lib/python3/dist-packages/")
        run(["apt-get", "remove", "-y", "livingproof-capability-report"])
        root_only()
        run(["apt-get", "install", "-y", args.reporter_deb])
        run(["apt-get", "remove", "-y", "livingproof"])
        run(["livingproof-capability-report", "--help"])
        run(["python3", "-c", "import importlib.util; "
             "assert importlib.util.find_spec('livingproof') is None"])
    record = {"os": platform.freedesktop_os_release(), "architecture": platform.machine(),
              "python": platform.python_version(), "execution": "native",
              "install_method": args.mode, "versions": versions, "outcome": "PASS",
              "evidence": os.environ.get("COMPATIBILITY_EVIDENCE", "local execution")}
    Path(args.output).write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["root", "combined", "debian"])
    parser.add_argument("output")
    parser.add_argument("--reporter-deb")
    probe(parser.parse_args())
