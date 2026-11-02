# SPDX-License-Identifier: Apache-2.0
"""Release inputs must be explicitly versioned and checksum verified before install."""
import hashlib
import importlib.util
from io import BytesIO
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "fetch_reporter", Path(__file__).resolve().parents[2] / "tools/fetch_reporter.py")
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)


def test_rejects_moving_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(fetcher, "ROOT", tmp_path)
    (tmp_path / "reporter-release.txt").write_text("main")
    with pytest.raises(ValueError, match="exact published version"):
        fetcher.fetch()


@pytest.mark.parametrize("tampered", [False, True])
def test_checksum_precedes_source_consumption(tmp_path, monkeypatch, tampered):
    monkeypatch.setattr(fetcher, "ROOT", tmp_path)
    (tmp_path / "reporter-release.txt").write_text("v1.4.0")
    data = b"package content"
    filename = "livingproof_capability_report-1.4.0-py3-none-any.whl"
    checksum = f"{hashlib.sha256(data).hexdigest()}  {filename}\n".encode()
    requested = []
    cloned = []

    def urlopen(url, timeout):
        requested.append(url)
        return BytesIO(checksum if url.endswith("SHA256SUMS")
                       else b"changed" if tampered else data)

    monkeypatch.setattr(fetcher, "urlopen", urlopen)
    monkeypatch.setattr(fetcher.subprocess, "run", lambda args, check: cloned.append(args))
    if tampered:
        with pytest.raises(ValueError, match="checksum mismatch"):
            fetcher.fetch()
        assert not cloned
        assert not (tmp_path / "artifacts/reporter" / filename).exists()
    else:
        fetcher.fetch()
        assert (tmp_path / "artifacts/reporter" / filename).read_bytes() == data
        assert "v1.4.0" in cloned[0]
    assert all("/releases/download/v1.4.0/" in url for url in requested)


def test_release_pins_tag_and_image_digests(tmp_path, monkeypatch):
    monkeypatch.setattr(fetcher, "ROOT", tmp_path)
    index, amd64 = "sha256:" + "a" * 64, "sha256:" + "b" * 64
    (tmp_path / "reporter-release.txt").write_text(f"v3.0.1\nindex {index}\namd64 {amd64}\n")
    assert fetcher.release() == ("v3.0.1", {"index": index, "amd64": amd64})


@pytest.mark.parametrize("line", ["index sha256:short", "riscv sha256:" + "a" * 64,
                                  "index latest"])
def test_release_rejects_malformed_digest_pins(tmp_path, monkeypatch, line):
    monkeypatch.setattr(fetcher, "ROOT", tmp_path)
    (tmp_path / "reporter-release.txt").write_text(f"v3.0.1\n{line}\n")
    with pytest.raises(ValueError, match="digest lines"):
        fetcher.release()


def test_repository_pin_is_digest_pinned():
    tag, digests = fetcher.release()
    assert set(digests) == {"index", "amd64", "arm64"}
    assert tag.startswith("v3.")
