# SPDX-License-Identifier: Apache-2.0
"""Pinned runtime dependencies must match the lock and the offline image wheels.

The runtime image installs with ``pip --no-index`` from ``dist/wheels``. That
directory starts as the reporter wheelhouse; ``tools/distributions.py`` then
stages locked root wheels on top. A ``pyproject.toml`` pin that ``uv.lock``
resolved differently, or that this staging leaves out, fails here.
"""
import hashlib
import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _distributions():
    path = ROOT / "tools" / "distributions.py"
    spec = importlib.util.spec_from_file_location("distributions", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_runtime_pins(text):
    pins = {}
    for requirement in tomllib.loads(text)["project"]["dependencies"]:
        name, separator, version = requirement.partition("==")
        if separator != "==" or not name or not version or any(
                token in version for token in " ,;<>!"):
            continue
        pins[name] = version
    return pins


def resolved_versions(lock):
    return {package["name"]: package["version"]
            for package in lock["package"] if "version" in package}


def registry_names(lock):
    return {package["name"] for package in lock["package"]
            if "registry" in package.get("source", {})}


def test_pinned_runtime_dependencies_match_the_lock_and_image_wheels():
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    pins = exact_runtime_pins((ROOT / "pyproject.toml").read_text())
    resolved = resolved_versions(lock)
    assert pins, "expected exact runtime pins in pyproject.toml"
    assert {name: resolved[name] for name in pins} == pins
    staged = {package["name"]: package["version"]
              for package in _distributions().registry_runtime_packages(lock)}
    registry_pins = {name: version for name, version in pins.items()
                     if name in registry_names(lock)}
    assert staged == registry_pins


def test_image_wheelhouse_replaces_reporter_copies_with_locked_wheels(tmp_path):
    click = b"locked-click"
    packaging = b"locked-packaging"
    lock = {"package": [
        {"name": "livingproof", "dependencies": [
            {"name": "click"}, {"name": "packaging"}, {"name": "livingproof-common"}]},
        {"name": "click", "version": "8.5.0",
         "source": {"registry": "https://pypi.org/simple"},
         "wheels": [{"url": "https://example.invalid/click-8.5.0-py3-none-any.whl",
                     "hash": "sha256:" + hashlib.sha256(click).hexdigest()}]},
        {"name": "packaging", "version": "25.0",
         "source": {"registry": "https://pypi.org/simple"},
         "wheels": [{"url": "https://example.invalid/packaging-25.0-py3-none-any.whl",
                     "hash": "sha256:" + hashlib.sha256(packaging).hexdigest()}]},
        {"name": "livingproof-common", "version": "1.0.0",
         "source": {"url": "https://example.invalid/livingproof_common-1.0.0-py3-none-any.whl"},
         "wheels": [{"url": "https://example.invalid/livingproof_common-1.0.0-py3-none-any.whl",
                     "hash": "sha256:" + hashlib.sha256(b"common").hexdigest()}]},
    ]}
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    (wheels / "click-8.3.0-py3-none-any.whl").write_bytes(b"reporter-click")
    (wheels / "jsonschema-4.25.1-py3-none-any.whl").write_bytes(b"reporter-jsonschema")
    fetched = {}

    def fetch(url):
        fetched[url] = {"click-8.5.0-py3-none-any.whl": click,
                        "packaging-25.0-py3-none-any.whl": packaging}[url.rsplit("/", 1)[1]]
        return fetched[url]

    _distributions().stage_locked_runtime_wheels(lock, wheels, fetch)
    assert sorted(path.name for path in wheels.iterdir()) == [
        "click-8.5.0-py3-none-any.whl",
        "jsonschema-4.25.1-py3-none-any.whl",
        "packaging-25.0-py3-none-any.whl",
    ]
    assert (wheels / "click-8.5.0-py3-none-any.whl").read_bytes() == click
    assert (wheels / "jsonschema-4.25.1-py3-none-any.whl").read_bytes() == b"reporter-jsonschema"
    assert set(fetched) == {
        "https://example.invalid/click-8.5.0-py3-none-any.whl",
        "https://example.invalid/packaging-25.0-py3-none-any.whl",
    }
