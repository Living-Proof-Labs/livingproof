# SPDX-License-Identifier: Apache-2.0
"""Use PyPA installer and dpkg-deb; apt owns interpreter and dependencies."""
import subprocess
import tempfile
from pathlib import Path

from installer import install
from installer.destinations import SchemeDictionaryDestination
from installer.sources import WheelFile

ROOT = Path(__file__).resolve().parents[1]


def build():
    wheels = list((ROOT / "dist").glob("livingproof-*-py3-none-any.whl"))
    if len(wheels) != 1:
        raise ValueError("Expected one pure-Python livingproof wheel")
    wheel = wheels[0]
    version = wheel.name.split("-")[1]
    with tempfile.TemporaryDirectory(prefix="livingproof-deb-") as temporary:
        stage = Path(temporary)
        destination = SchemeDictionaryDestination(
            scheme_dict={"purelib": "/usr/lib/python3/dist-packages",
                         "platlib": "/usr/lib/python3/dist-packages", "scripts": "/usr/bin",
                         "headers": "/usr/include/livingproof", "data": "/usr"},
            interpreter="/usr/bin/python3", script_kind="posix", destdir=str(stage),
            bytecode_optimization_levels=[])
        with WheelFile.open(wheel) as source:
            install(source, destination, additional_metadata={"INSTALLER": b"apt/dpkg\n"})
        control = stage / "DEBIAN"
        control.mkdir()
        (control / "control").write_text(f"""Package: livingproof
Version: {version}
Section: python
Priority: optional
Architecture: all
Depends: python3-livingproof-common (= 1.0.0), python3 (>= 3.11), python3-click (>= 8.1), python3-packaging (>= 23)
Recommends: bash-completion
Suggests: livingproof-capability-report (>= 1.4.0)
Maintainer: Living Proof Labs <rivet@rollerbot.ai>
Description: Thin Living Proof Labs command with installed plugin discovery
""")
        for name, command in (("postinst", "py3compile -p livingproof"),
                              ("prerm", "py3clean -p livingproof")):
            script = control / name
            script.write_text(f"#!/bin/sh\nset -e\n{command}\n")
            script.chmod(0o755)
        documentation = stage / "usr/share/doc/livingproof"
        documentation.mkdir(parents=True)
        (documentation / "copyright").write_text((ROOT / "LICENSE.md").read_text())
        for license in (ROOT / "LICENSES").iterdir():
            (documentation / license.name).write_bytes(license.read_bytes())
        stage.chmod(0o755)
        for path in stage.rglob("*"):
            path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(stage),
                        str(ROOT / "dist" / f"livingproof_{version}_all.deb")], check=True)


if __name__ == "__main__":
    build()
