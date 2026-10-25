# SPDX-License-Identifier: Apache-2.0
"""Exercise actual devcontainer creation, user lifecycle, plugin opt-in and restart."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_devcontainer_lifecycle():
    executable = os.environ.get("DEVCONTAINER_CLI", "devcontainer")
    options = ["--workspace-folder", str(ROOT)]
    if os.environ.get("DEVCONTAINER_CONFIG"):
        options += ["--override-config", os.environ["DEVCONTAINER_CONFIG"]]
    container = None

    def run(args):
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
        print(result.stdout)
        print(result.stderr)
        assert result.returncode == 0
        return result.stdout

    try:
        output = run([executable, "up", *options])
        result = json.loads(output.strip().splitlines()[-1])
        container = result["containerId"]
        assert result["outcome"] == "success"
        run([executable, "exec", *options, "bash", "-lc",
             "command -v livingproof && livingproof --help && task verify"])
        run([executable, "exec", *options, "bash", "-lc",
             "task plugin:install && task setup && "
             "livingproof capability report validate artifacts/reporter/source/examples/bundle/manifest.json && "
             "livingproof capability report grade artifacts/reporter/source/examples/bundle/manifest.json "
             "-o /tmp/devcontainer-report.json && "
             "livingproof capability report render /tmp/devcontainer-report.json"])
        run(["docker", "restart", container])
        run([executable, "exec", *options, "bash", "-lc",
             "livingproof capability report --help && "
             "_LIVINGPROOF_COMPLETE=bash_source livingproof > /tmp/livingproof-completion.bash && "
             ". /tmp/livingproof-completion.bash"])
    finally:
        if container:
            subprocess.run(["docker", "rm", "-f", container], check=True)
