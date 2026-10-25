# SPDX-License-Identifier: Apache-2.0
"""Explicit contributor action: install the verified wheel into the active environment."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
wheel, = (root / "artifacts/reporter").glob("*.whl")
subprocess.run(["uv", "pip", "install", "--python", sys.executable, str(wheel)], check=True)
print("Reporter installed explicitly; use livingproof capability report --help")
