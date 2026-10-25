# SPDX-License-Identifier: Apache-2.0
"""Write checksums for the exact wheel and source release assets."""
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "dist"
assets = sorted([*root.glob("*.whl"), *root.glob("*.tar.gz"), *root.glob("*.deb")])
if len(assets) < 3:
    raise SystemExit("Expected wheel, source and Debian assets")
(root / "SHA256SUMS").write_text("".join(
    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in assets))
