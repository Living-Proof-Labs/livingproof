# SPDX-License-Identifier: Apache-2.0
"""Default-startup and same-shell installation regression, run only in containers."""
import argparse
from pathlib import Path
import tempfile

from bash_session import BashSession

ACTIVATE = 'eval "$(livingproof completion bash)"'


def expect(shell, line, expected):
    actual = shell.complete(line)
    assert actual == expected, (line, actual, expected)
    print(f"TAB {line!r} -> {actual!r}", flush=True)


def nested(shell):
    for line, expected in (
        ("livingproof cap", "livingproof capability "),
        ("livingproof capability rep", "livingproof capability report "),
        ("livingproof capability report gr", "livingproof capability report grade "),
        ("livingproof capability report re", "livingproof capability report render "),
        ("livingproof capability report grade --out", "livingproof capability report grade --output "),
        ("livingproof capability report render --format ht", "livingproof capability report render --format html "),
        ("livingproof capability report validate mani", "livingproof capability report validate manifest\\ sample.json "),
    ):
        expect(shell, line, expected)


def probe(released=False):
    activate = 'eval "$(_LIVINGPROOF_COMPLETE=bash_source livingproof)"' if released else ACTIVATE
    startup_files = [Path("/root/.bashrc"), Path("/root/.profile"), Path("/etc/bash.bashrc")]
    original = {p: p.read_bytes() for p in startup_files}
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        (work / "cap-filesystem-fallback").touch()
        (work / "manifest sample.json").write_text("not a valid manifest")
        # A normal shell exists BEFORE apt installs the application. No --norc,
        # test rcfile, or explicit source of the completion framework is used.
        with BashSession(work) as shell:
            shell.run("apt-get install -y --no-install-recommends /packages/livingproof_*_all.deb")
            shell.run("test ! -f /usr/share/bash-completion/bash_completion")
            expect(shell, "livingproof cap", "livingproof cap-filesystem-fallback ")
            if not released:
                help_text = shell.run("livingproof --help")
                assert ACTIVATE in help_text and "README" not in help_text
                status = shell.run("livingproof completion status")
                assert "Bash-completion framework: not found" in status
                assert "cannot inspect or change that shell" in status
            shell.run(activate)
            expect(shell, "livingproof cap", "livingproof capability ")
            # Discover the real independently released plugin after registration.
            shell.run("apt-get install -y --no-install-recommends /reporter.deb")
            nested(shell)
        # Install the framework while ANOTHER normal shell is already running.
        with BashSession(work) as shell:
            shell.run("apt-get install -y --no-install-recommends bash-completion")
            expect(shell, "livingproof cap", "livingproof cap-filesystem-fallback ")
            shell.run(activate)
            nested(shell)
        with BashSession(work) as shell:
            # Stock root .bashrc on these images leaves the framework disabled.
            expect(shell, "livingproof cap", "livingproof cap-filesystem-fallback ")
            shell.run(activate)
            nested(shell)
        # The CLI's documented NEW-shell command. Normal /etc/profile.d startup
        # loads the framework and its lazy loader finds the package-owned file.
        with BashSession(work, login=True) as shell:
            nested(shell)
            shell.run("apt-get remove -y livingproof-capability-report")
            expect(shell, "livingproof capability report re", "livingproof capability report re")
            shell.run("apt-get remove -y livingproof")
        with BashSession(work, login=True) as shell:
            shell.run("test ! -e /usr/share/bash-completion/completions/livingproof; "
                      "! command -v livingproof")
            expect(shell, "livingproof cap", "livingproof cap-filesystem-fallback ")
        assert sorted(p.name for p in work.iterdir()) == ["cap-filesystem-fallback", "manifest sample.json"]
    assert {p: p.read_bytes() for p in startup_files} == original
    print("PASS: default startup, current-shell recovery, login-shell lazy loading, plugins, removal; startup files unchanged", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--released", action="store_true", help="Reproduce 1.2.0 with its legacy activation command")
    probe(parser.parse_args().released)
