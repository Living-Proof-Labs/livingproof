# SPDX-License-Identifier: Apache-2.0
"""Generate release evidence from actual probes, retaining missing and failed cases."""
import hashlib
import json
from pathlib import Path
import platform
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ARCH = {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()]
records = []
xml = ROOT / "artifacts/installed-tests.xml"
failures = [t.attrib.get("name", "") for t in ET.parse(xml).iter("testcase")
            if t.find("failure") is not None or t.find("error") is not None] if xml.exists() else []
for name, test in [("root-image", "test_saved_container[-root]"),
                   ("combined-image", "test_saved_container[-reporting-combined]"),
                   ("debian-12-slim", "test_debian_plugins[debian:12-slim]"),
                   ("debian-13-slim", "test_debian_plugins[debian:13-slim]"),
                   ("ubuntu-24.04", "test_debian_plugins[ubuntu:24.04]"),
                   ("wheel-source", "test_wheel_source_and_plugin")]:
    path = DIST / "compatibility" / f"{name}.json"
    record = json.loads(path.read_text()) if path.exists() else {"probe": name}
    if test in failures:
        record["outcome"] = "FAIL"
    record.setdefault("outcome", "NOT_COMPLETED")
    records.append(record)
DIST.mkdir(exist_ok=True)
(DIST / f"compatibility-{ARCH}.json").write_text(json.dumps(
    {"schema_version": "1.0.0", "host_architecture": ARCH, "records": records}, indent=2) + "\n")
lines = [f"## Installed compatibility: {ARCH}", "",
         "| Actual runtime / probe | Python | Installation | Outcome | Evidence |",
         "| --- | --- | --- | --- | --- |"]
for record in records:
    values = [record.get("os", {}).get("PRETTY_NAME", record.get("probe", "unknown")),
              record.get("python", "unknown"), record.get("install_method", "not completed"),
              record["outcome"], record.get("evidence", "not completed")]
    lines.append("| " + " | ".join(str(v).replace("|", "\\|") for v in values) + " |")
text = "\n".join(lines) + "\n"
(DIST / f"compatibility-{ARCH}.md").write_text(text)
print(text)
assets = [DIST / f"image-{ARCH}.tar", DIST / f"reporting-image-{ARCH}.tar",
          DIST / f"compatibility-{ARCH}.json", DIST / f"compatibility-{ARCH}.md"]
if ARCH == "amd64":
    assets += [*DIST.glob("*.whl"), *DIST.glob("livingproof-*.tar.gz"), *DIST.glob("*.deb")]
with (DIST / f"SHA256SUMS-{ARCH}").open("w") as stream:
    for path in sorted(assets):
        if path.is_file():
            with path.open("rb") as source:
                checksum = hashlib.file_digest(source, "sha256").hexdigest()
            stream.write(f"{checksum}  {path.name}\n")
