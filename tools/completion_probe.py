# SPDX-License-Identifier: Apache-2.0
"""Exercise Readline TAB in fresh Bash processes, without executing the input."""
import argparse
import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import time


def complete(line, setup, cwd):
    master, slave = pty.openpty()
    process = subprocess.Popen(["bash", "--noprofile", "--norc", "-i"],
                               stdin=slave, stdout=slave, stderr=slave, cwd=cwd,
                               env={**os.environ, "TERM": "dumb", "INPUTRC": "/dev/null"})
    os.close(slave)

    def until(marker, result=b""):
        deadline = time.monotonic() + 15
        while marker not in result:
            assert time.monotonic() < deadline, result.decode(errors="replace")
            if select.select([master], [], [], 0.1)[0]:
                result += os.read(master, 65536)
        return result

    try:
        os.write(master, ("PS1='READY> '; " + setup + "; "
                         "bind 'set show-all-if-ambiguous off'; "
                         "bind -x '\"\\C-x\":printf \"\\nRESULT:%s\\n\" \"$READLINE_LINE\"'; "
                         "printf '\\nINITIALIZED\\n'\n").encode())
        until(b"\r\nINITIALIZED\r\n")
        # The command under completion is never submitted. Ctrl-X captures the
        # line after Readline itself applies Click's completion/fallback rules.
        os.write(master, line.encode() + b"\t\x18")
        output = until(b"\r\nRESULT:")
        line_output = until(b"\r\n", output.split(b"\r\nRESULT:", 1)[1])
        return line_output.split(b"\r\n", 1)[0].decode()
    finally:
        os.write(master, b"\x15exit\n")
        process.wait(timeout=5)
        os.close(master)


def probe(state, setup="source /usr/share/bash-completion/bash_completion"):
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        (work / "manifest sample.json").write_text("not a valid manifest")
        cases = [("livingproof --ver", "livingproof --version "),
                 ("livingproof cap", "livingproof capability "),
                 ("livingproof capability rep", "livingproof capability report ")]
        if state == "installed":
            cases += [
                ("livingproof capability report gr", "livingproof capability report grade "),
                ("livingproof capability report re", "livingproof capability report render "),
                ("livingproof capability report va", "livingproof capability report validate "),
                ("livingproof capability report grade --out", "livingproof capability report grade --output "),
                ("livingproof capability report render --for", "livingproof capability report render --format "),
                ("livingproof capability report render --format ht", "livingproof capability report render --format html "),
                ("livingproof capability report validate mani", "livingproof capability report validate manifest\\ sample.json "),
                ("livingproof capability report grade -o mani", "livingproof capability report grade -o manifest\\ sample.json "),
            ]
        else:
            cases += [("livingproof capability report re", "livingproof capability report re")]
        for line, expected in cases:
            actual = complete(line, setup, work)
            assert actual == expected, (state, line, actual, expected)
            print(f"PASS {state}: {line!r} -> {actual!r}")
        assert sorted(p.name for p in work.iterdir()) == ["manifest sample.json"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("state", choices=["absent", "installed"])
    parser.add_argument("--setup", default="source /usr/share/bash-completion/bash_completion")
    args = parser.parse_args()
    probe(args.state, args.setup)
