# SPDX-License-Identifier: Apache-2.0
"""Verify wheel consumption outside the source tree, optionally with the real reporter."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import venv

from completion_probe import probe as completion_probe

ROOT = Path(__file__).resolve().parents[1]


def run(args, cwd, expected=0, env=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                            capture_output=True, text=True)
    if result.returncode != expected:
        raise RuntimeError(f"{args}: {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


def smoke():
    distribution = Path(os.environ.get("LIVINGPROOF_DIST", ROOT / "dist"))
    wheels = list(distribution.glob("livingproof-*.whl"))
    assert len(wheels) == 1, "Build exactly one candidate wheel first"
    with tempfile.TemporaryDirectory(prefix="livingproof-installed-") as temporary:
        work = Path(temporary)
        venv.create(work / "env", with_pip=True)
        bin_dir = work / "env" / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / "python"
        command = bin_dir / "livingproof"
        run([python, "-m", "pip", "install", wheels[0]], work)
        assert "capability" in run([command], work)
        assert "same Python environment" in run([command, "capability", "report"], work, 1)
        completion_setup = 'eval "$(livingproof completion bash)"'
        user_env = {**os.environ, "XDG_DATA_HOME": str(work / "user-data"),
                    "BASH_COMPLETION_USER_DIR": ""}
        run([command, "completion", "install"], work, env=user_env)
        registration = work / "user-data/bash-completion/completions/livingproof"
        assert registration.is_file()
        previous_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(bin_dir) + os.pathsep + previous_path
        completion_probe("absent", completion_setup)
        completion_probe("absent", f'source "{registration}"')
        run([command, "completion", "install", "--remove"], work, env=user_env)
        assert not registration.exists()
        for shell in ("bash", "zsh", "fish"):
            script = run([command], work, env={**os.environ,
                         "_LIVINGPROOF_COMPLETE": f"{shell}_source"})
            assert "livingproof" in script
        # Build a real installed distribution to exercise importlib.metadata discovery.
        fixture = work / "fixture"
        fixture.mkdir()
        (fixture / "pyproject.toml").write_text(
            '[build-system]\nrequires=["hatchling==1.27.0"]\n'
            'build-backend="hatchling.build"\n[project]\n'
            'name="probe"\nversion="1.0.0"\n'
            '[project.entry-points."livingproof.capability.commands"]\n'
            'probe="probe:command"\n')
        (fixture / "probe.py").write_text(
            'import click\n@click.command()\ndef command():\n    click.echo("installed probe")\n')
        run([python, "-m", "pip", "install", fixture], work)
        assert "installed probe" in run([command, "capability", "probe"], work)
        reporter = os.environ.get("REPORTER_WHEEL")
        bundle = os.environ.get("REPORTER_BUNDLE")
        if not reporter and not bundle and (ROOT / "artifacts/reporter/source").exists():
            installed_candidates = list((ROOT / "artifacts/reporter").glob("*.whl"))
            assert len(installed_candidates) == 1
            reporter = str(installed_candidates[0])
            bundle = str(ROOT / "artifacts/reporter/source/examples/bundle")
        assert bool(reporter) == bool(bundle), "Set both REPORTER_WHEEL and REPORTER_BUNDLE"
        if reporter:
            run([python, "-m", "pip", "install", Path(reporter).resolve()], work)
            completion_probe("installed", completion_setup)
            shutil.copytree(Path(bundle).resolve(), work / "bundle")
            standalone = bin_dir / "livingproof-capability-report"
            for prefix, label in [([command, "capability", "report"], "nested"),
                                  ([standalone], "standalone")]:
                run([*prefix, "--help"], work)
                run([*prefix, "validate", "bundle/manifest.json"], work)
                run([*prefix, "grade", "bundle/manifest.json", "-o", f"{label}.json"], work)
                for format in ("table", "json", "html", "csv"):
                    run([*prefix, "render", f"{label}.json", "--format", format,
                         "-o", f"{label}.{format}.out"], work)
                run([*prefix, "grade", "bundle/manifest.json", "-o", f"{label}.json"], work, 1)
                run([*prefix, "validate", "missing.json"], work, 2)
            assert json.loads((work / "nested.json").read_text()) == json.loads(
                (work / "standalone.json").read_text())
            for format in ("table", "json", "html", "csv"):
                assert (work / f"nested.{format}.out").read_bytes() == (
                    work / f"standalone.{format}.out").read_bytes()
            completion = run([command], work, env={**os.environ,
                "_LIVINGPROOF_COMPLETE": "bash_complete",
                "COMP_WORDS": "livingproof capability report r", "COMP_CWORD": "3"})
            assert "plain,render" in completion
            run([python, "-c", "from livingproof_capability_report import grade, render"], work)
            run([python, "-m", "pip", "uninstall", "-y", "livingproof-capability-report"], work)
            completion_probe("absent", completion_setup)
            run([python, "-m", "pip", "install", Path(reporter).resolve()], work)
            print("PASS: clean installed real reporter delegation, all formats, errors and completion")
        else:
            print("NOT RUN: real reporter consumption (set REPORTER_WHEEL and REPORTER_BUNDLE)")
        sources = list(distribution.glob("livingproof-*.tar.gz"))
        assert len(sources) == 1, "Build exactly one source archive first"
        venv.create(work / "source-env", with_pip=True)
        source_bin = work / "source-env" / ("Scripts" if os.name == "nt" else "bin")
        run([source_bin / "python", "-m", "pip", "install", sources[0]], work)
        assert "capability" in run([source_bin / "livingproof", "--help"], work)
        assert run([command, "--version"], work) == run(
            [source_bin / "livingproof", "--version"], work)
        if os.environ.get("SMOKE_RECORD"):
            record = json.loads(run([python, "-c",
                "import json,platform; from importlib.metadata import version; "
                "print(json.dumps({'os':platform.freedesktop_os_release(), "
                "'architecture':platform.machine(), 'python':platform.python_version(), "
                "'versions':{name:version(name) for name in "
                "('livingproof','livingproof-capability-report')}}))"], work))
            record.update(outcome="PASS", execution="native", install_method="wheel-and-source",
                          evidence=os.environ.get("COMPATIBILITY_EVIDENCE", "local execution"))
            Path(os.environ["SMOKE_RECORD"]).write_text(json.dumps(record, indent=2) + "\n")
        run([python, "-m", "pip", "uninstall", "-y", "livingproof"], work)
        assert not (work / "env/share/bash-completion/completions/livingproof").exists()
        os.environ["PATH"] = previous_path
        print("PASS: root wheel/source, missing plugin, installed discovery and completion generation")


if __name__ == "__main__":
    smoke()
