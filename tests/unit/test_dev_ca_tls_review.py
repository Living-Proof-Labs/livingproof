# SPDX-License-Identifier: Apache-2.0
"""Security checks for the optional development CA and proxy passthrough (Vera review of #41).

- With a supplied CA, a TLS client run under the development entrypoint trusts a server
  signed by that CA. Without one (the /dev/null default), the same server is rejected,
  so verification stays on and nothing is trusted by default.
- The defaults mount /dev/null, no repository file supplies DEV_CA_BUNDLE, and the
  published runtime and reporting stages carry no CA, proxy or secret handling.
- No file turns TLS verification off.
"""

import json
import os
import re
import shutil
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SYSTEM_BUNDLE = Path("/etc/ssl/certs/ca-certificates.crt")
CLIENT = (
    "import sys, urllib.request\n"
    "try:\n"
    "    urllib.request.urlopen(sys.argv[1], timeout=10).read()\n"
    "except Exception as error:\n"
    "    print(type(error).__name__, error)\n"
    "    sys.exit(3)\n"
    "print('TLS-OK')\n"
)


def _openssl(*args, cwd):
    subprocess.run(["openssl", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def tls_server(tmp_path):
    if not shutil.which("openssl") or not SYSTEM_BUNDLE.is_file():
        pytest.skip("needs the openssl CLI and the Debian system CA bundle")
    _openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-days",
        "1",
        "-subj",
        "/CN=Vera review test CA",
        "-keyout",
        "ca.key",
        "-out",
        "ca.pem",
        cwd=tmp_path,
    )
    (tmp_path / "san.cnf").write_text("subjectAltName=DNS:localhost,IP:127.0.0.1\n")
    _openssl(
        "req",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-subj",
        "/CN=localhost",
        "-keyout",
        "server.key",
        "-out",
        "server.csr",
        cwd=tmp_path,
    )
    _openssl(
        "x509",
        "-req",
        "-in",
        "server.csr",
        "-CA",
        "ca.pem",
        "-CAkey",
        "ca.key",
        "-CAcreateserial",
        "-days",
        "1",
        "-extfile",
        "san.cnf",
        "-out",
        "server.pem",
        cwd=tmp_path,
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tmp_path / "server.pem", tmp_path / "server.key")
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield tmp_path / "ca.pem", f"https://localhost:{httpd.server_port}/"
    httpd.shutdown()


def _client_under_entrypoint(tmp_path, extra_ca, url):
    env = {
        "PATH": os.environ["PATH"],
        "DEV_EXTRA_CA": str(extra_ca),
        "DEV_SYSTEM_CA_BUNDLE": str(SYSTEM_BUNDLE),
        "DEV_COMBINED_CA_BUNDLE": str(tmp_path / "combined.pem"),
        "NO_PROXY": "localhost,127.0.0.1",
        "no_proxy": "localhost,127.0.0.1",
    }
    return subprocess.run(
        ["sh", str(ROOT / "docker/dev-entrypoint.sh"), "python3", "-c", CLIENT, url],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )


def test_supplied_ca_is_trusted_and_default_is_not(tls_server, tmp_path):
    ca, url = tls_server
    (tmp_path / "with").mkdir()
    trusted = _client_under_entrypoint(tmp_path / "with", ca, url)
    assert trusted.returncode == 0, trusted.stdout + trusted.stderr
    assert "TLS-OK" in trusted.stdout
    (tmp_path / "without").mkdir()
    default = _client_under_entrypoint(tmp_path / "without", Path("/dev/null"), url)
    assert default.returncode == 3, default.stdout + default.stderr
    assert "CERTIFICATE_VERIFY_FAILED" in default.stdout
    assert not (tmp_path / "without" / "combined.pem").exists()


def test_defaults_mount_dev_null_and_nothing_in_the_repo_supplies_a_ca():
    compose = yaml.safe_load((ROOT / "compose.yml").read_text())
    for service in compose["services"].values():
        assert "env_file" not in service
        for volume in service.get("volumes", []):
            if "extra-ca.crt" in str(volume):
                assert str(volume).startswith("${DEV_CA_BUNDLE:-/dev/null}:")
                assert str(volume).endswith(":ro")
    devcontainer = json.loads((ROOT / ".devcontainer/devcontainer.json").read_text())
    for mount in devcontainer.get("mounts", []):
        if "extra-ca.crt" in mount:
            assert mount.startswith("source=${localEnv:DEV_CA_BUNDLE:/dev/null},")
            assert "readonly" in mount.split(",")
    # Compose reads a project .env for substitution; none may set the CA or proxies.
    for name in (".env", ".devcontainer/.env"):
        path = ROOT / name
        if path.exists():
            assert not re.search(
                r"(?m)^\s*(DEV_CA_BUNDLE|\w*_PROXY|\w*_proxy)\s*=", path.read_text()
            )
    workflows = "".join(p.read_text() for p in (ROOT / ".github/workflows").glob("*.y*ml"))
    assert "DEV_CA_BUNDLE" not in workflows
    assert "extra-ca" not in workflows


def _stage(name):
    text = (ROOT / "Dockerfile").read_text()
    start = text.index(f" AS {name}\n")
    following = text.find("\nFROM ", start)
    return text[start:] if following < 0 else text[start:following]


def test_published_stages_carry_no_ca_proxy_or_secret_handling():
    for name in ("runtime", "reporting"):
        stage = _stage(name)
        for token in (
            "--mount=type=secret",
            "extra-ca",
            "dev-ca-env",
            "SSL_CERT_FILE",
            "REQUESTS_CA_BUNDLE",
            "CURL_CA_BUNDLE",
            "PIP_CERT",
            "UV_NATIVE_TLS",
            "PROXY",
            "proxy",
            "/run/secrets",
        ):
            assert token not in stage, (name, token)


TLS_OFF = re.compile(
    r"verify\s*=\s*False|--insecure\b|GIT_SSL_NO_VERIFY|NODE_TLS_REJECT_UNAUTHORIZED|"
    r"PIP_TRUSTED_HOST|--trusted-host|_create_unverified_context|CERT_NONE|"
    r"check_hostname\s*=\s*False|UV_INSECURE_HOST|--allow-insecure-host|"
    r"--no-check-certificate|sslVerify\s*=?\s*false|Verify-Peer\s*\"?false|"
    r"\bcurl\b[^\n|;]*\s-[a-zA-Z]*k[a-zA-Z]*\b"
)
SKIP_PARTS = {".git", ".venv", "node_modules", "artifacts", "dist", "__pycache__"}


def test_no_file_turns_tls_verification_off():
    me = Path(__file__).resolve()
    hits = []
    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or path.resolve() == me
            or SKIP_PARTS & set(path.relative_to(ROOT).parts)
            or path.name == "uv.lock"
            or path.stat().st_size > 2_000_000
        ):
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        hits += [f"{path.relative_to(ROOT)}: {m.group(0)}" for m in TLS_OFF.finditer(text)]
    assert hits == []


def test_bundle_is_not_written_to_a_fixed_tmp_path(tmp_path):
    """The default bundle is a private mktemp file, never /tmp/livingproof-ca-bundle.crt.

    The script does not chmod through a path, and a planted file at the old
    predictable location is left untouched when DEV_COMBINED_CA_BUNDLE is unset.
    """
    script = (ROOT / "docker/dev-ca-env.sh").read_text()
    assert "/tmp/livingproof-ca-bundle.crt" not in script
    assert "mktemp" in script
    assert "chmod" not in script

    if not shutil.which("openssl") or not SYSTEM_BUNDLE.is_file():
        pytest.skip("needs the openssl CLI and the Debian system CA bundle")

    ca = tmp_path / "ca.pem"
    _openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-days",
        "1",
        "-subj",
        "/CN=Vera review test CA",
        "-keyout",
        "ca.key",
        "-out",
        "ca.pem",
        cwd=tmp_path,
    )
    planted = Path("/tmp/livingproof-ca-bundle.crt")
    planted_existed = planted.exists() or planted.is_symlink()
    marker = "VERA-FIXED-TMP-PROBE\n"
    home = tmp_path / "home"
    runtime = tmp_path / "runtime"
    home.mkdir()
    runtime.mkdir()
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "XDG_RUNTIME_DIR": str(runtime),
        "TMPDIR": str(tmp_path / "tmpdir"),
        "DEV_EXTRA_CA": str(ca),
        "DEV_SYSTEM_CA_BUNDLE": str(SYSTEM_BUNDLE),
        "NO_PROXY": "localhost,127.0.0.1",
        "no_proxy": "localhost,127.0.0.1",
    }
    (tmp_path / "tmpdir").mkdir()
    try:
        if not planted_existed:
            planted.write_text(marker)
        else:
            before = (
                planted.read_bytes() if planted.is_file() and not planted.is_symlink() else None
            )
        result = subprocess.run(
            ["sh", str(ROOT / "docker/dev-entrypoint.sh"), "env"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=60,
        )
        if not planted_existed:
            assert planted.read_text() == marker
            assert planted.is_file() and not planted.is_symlink()
        elif before is not None:
            assert planted.read_bytes() == before
    finally:
        if not planted_existed and (planted.exists() or planted.is_symlink()):
            planted.unlink()

    assert result.returncode == 0, result.stdout + result.stderr
    values = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    bundle = Path(values["SSL_CERT_FILE"])
    assert values["GIT_SSL_CAINFO"] == str(bundle)
    assert bundle.is_file()
    assert not bundle.is_symlink()
    assert bundle != planted
    assert str(bundle) != "/tmp/livingproof-ca-bundle.crt"
    assert bundle.parent == runtime / "livingproof"
    assert bundle.stat().st_mode & 0o777 == 0o600
    assert bundle.parent.stat().st_mode & 0o777 == 0o700
    assert "BEGIN CERTIFICATE" in bundle.read_text()
