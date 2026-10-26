# SPDX-License-Identifier: Apache-2.0
"""Real interactive Bash with its normal startup files and Readline."""
import os
import pty
import select
import subprocess
import time


class BashSession:
    def __init__(self, cwd, login=False):
        self.master, slave = pty.openpty()
        self.process = subprocess.Popen(["bash", *(["--login"] if login else []), "-i"],
                                        stdin=slave, stdout=slave, stderr=slave, cwd=cwd,
                                        env={**os.environ, "TERM": "dumb", "INPUTRC": "/dev/null"})
        os.close(slave)
        self.run("PS1='READY> '; bind 'set show-all-if-ambiguous off'; "
                 "bind -x '\"\\C-x\":printf \"\\nRESULT:%s\\n\" \"$READLINE_LINE\"'")

    def until(self, marker, result=b"", timeout=180):
        deadline = time.monotonic() + timeout
        while marker not in result:
            assert time.monotonic() < deadline, result.decode(errors="replace")
            if select.select([self.master], [], [], 0.1)[0]:
                result += os.read(self.master, 65536)
        return result

    def run(self, command):
        os.write(self.master, (command + "; printf '\\nDONE:%s\\n' \"$?\"\n").encode())
        output = self.until(b"\r\nDONE:")
        tail = self.until(b"\r\n", output.split(b"\r\nDONE:", 1)[1])
        assert tail.split(b"\r\n", 1)[0] == b"0", output.decode(errors="replace")
        return output.decode(errors="replace")

    def complete(self, line):
        os.write(self.master, line.encode() + b"\t\x18")
        output = self.until(b"\r\nRESULT:")
        tail = self.until(b"\r\n", output.split(b"\r\nRESULT:", 1)[1])
        os.write(self.master, b"\x15")
        return tail.split(b"\r\n", 1)[0].decode()

    def close(self):
        os.write(self.master, b"\x15exit\n")
        try:
            self.process.wait(timeout=5)
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            os.close(self.master)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
