# SPDX-License-Identifier: Apache-2.0
"""Development container proxy passthrough and optional extra certificate."""
import json
import os
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROXY_VARS = ('HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'no_proxy')
CA_ENV = (
    'SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'PIP_CERT',
    'GIT_SSL_CAINFO', 'UV_NATIVE_TLS', 'UV_SYSTEM_CERTS',
)
LOOPBACK = ('localhost', '127.0.0.1', '::1')
PEM = '-----BEGIN CERTIFICATE-----\nEXTRA-CA\n-----END CERTIFICATE-----\n'


def _stage(name):
    text = (ROOT / 'Dockerfile').read_text()
    marker = f'FROM python-base AS {name}\n'
    start = text.index(marker) + len(marker)
    rest = text[start:]
    following = rest.find('\nFROM ')
    return rest if following < 0 else rest[:following]


def test_compose_passes_proxy_vars_and_optional_ca():
    text = (ROOT / 'compose.yml').read_text()
    config = yaml.safe_load(text)
    service = config['services']['development']
    assert service['build']['args']['APT_MIRROR'] == '${APT_MIRROR:-}'
    assert service['environment'] == list(PROXY_VARS)
    assert '${DEV_CA_BUNDLE:-/dev/null}:/run/livingproof/extra-ca.crt:ro' in text
    assert '/etc/ssl/certs' not in text
    volumes = service['volumes']
    assert any('/run/livingproof/extra-ca.crt' in str(item) for item in volumes)


def test_devcontainer_passes_proxy_vars_and_optional_ca():
    config = json.loads((ROOT / '.devcontainer/devcontainer.json').read_text())
    assert config['build']['args']['APT_MIRROR'] == '${localEnv:APT_MIRROR}'
    environment = config['containerEnv']
    for name in PROXY_VARS:
        assert environment[name] == '${localEnv:%s}' % name
    assert config['mounts'] == [
        'source=${localEnv:DEV_CA_BUNDLE:/dev/null},target=/run/livingproof/extra-ca.crt,'
        'type=bind,readonly',
    ]
    assert config['postCreateCommand'] == (
        '. /usr/local/bin/dev-ca-env.sh && task setup && livingproof --help'
    )


def test_development_entrypoint_sets_ca_only_in_that_stage():
    development = _stage('development')
    runtime = _stage('runtime')
    assert 'COPY docker/dev-ca-env.sh docker/dev-entrypoint.sh /usr/local/bin/' in development
    assert 'COPY docker/livingproof-ca.sh /etc/profile.d/livingproof-ca.sh' in development
    script = (ROOT / 'docker/dev-ca-env.sh').read_text()
    assert '/run/livingproof/extra-ca.crt' in script
    assert '/tmp/livingproof-ca-bundle.crt' not in script
    assert 'mktemp' in script
    assert 'GIT_SSL_CAINFO' in script
    assert 'chmod' not in script
    assert 'ENTRYPOINT ["/usr/local/bin/dev-entrypoint.sh"]' in development
    assert 'ENTRYPOINT ["livingproof"]' in runtime
    assert 'dev-ca-env.sh' not in runtime
    profile = (ROOT / 'docker/livingproof-ca.sh').read_text()
    assert '. /usr/local/bin/dev-ca-env.sh' in profile


def _run_entrypoint(tmp_path, extra, system, proxy=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    env = {
        'PATH': os.environ['PATH'],
        'DEV_EXTRA_CA': str(extra),
        'DEV_SYSTEM_CA_BUNDLE': str(system),
        'DEV_COMBINED_CA_BUNDLE': str(tmp_path / 'combined.pem'),
    }
    if proxy:
        env.update(proxy)
    result = subprocess.run(
        ['sh', str(ROOT / 'docker/dev-entrypoint.sh'), 'env'],
        cwd=tmp_path, capture_output=True, text=True, env=env, check=False,
    )
    values = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition('=')
        if separator:
            values[key] = value
    return result, values


def test_ca_env_is_set_only_when_a_pem_is_supplied(tmp_path):
    system = tmp_path / 'system.pem'
    system.write_text('SYSTEM-CA-MARKER\n')
    cases = {
        'missing': None,
        'empty': '',
        'comment': '# not a certificate\n',
    }
    for name, content in cases.items():
        extra = tmp_path / f'{name}.crt'
        if content is not None:
            extra.write_text(content)
        result, values = _run_entrypoint(tmp_path / name, extra, system)
        assert result.returncode == 0, result.stderr
        for variable in CA_ENV:
            assert variable not in values, name
        assert not (tmp_path / name / 'combined.pem').exists()

    extra = tmp_path / 'extra.crt'
    extra.write_text(PEM)
    result, values = _run_entrypoint(tmp_path / 'pem', extra, system)
    assert result.returncode == 0, result.stderr
    bundle = Path(values['SSL_CERT_FILE'])
    assert bundle.is_file()
    for variable in ('REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'PIP_CERT'):
        assert values[variable] == str(bundle)
    assert values['UV_NATIVE_TLS'] == 'true'
    assert values['UV_SYSTEM_CERTS'] == 'true'
    text = bundle.read_text()
    assert 'SYSTEM-CA-MARKER' in text
    assert 'BEGIN CERTIFICATE' in text and 'EXTRA-CA' in text
    for variable in CA_ENV:
        assert variable in values


def test_entrypoint_drops_empty_proxies_and_keeps_set_ones(tmp_path):
    system = tmp_path / 'system.pem'
    system.write_text('SYSTEM-CA-MARKER\n')
    result, values = _run_entrypoint(
        tmp_path, tmp_path / 'missing.crt', system,
        proxy={'HTTP_PROXY': '', 'http_proxy': '', 'HTTPS_PROXY': 'http://proxy.example:8080',
               'NO_PROXY': 'localhost', 'https_proxy': 'http://proxy.example:8080',
               'no_proxy': 'localhost'},
    )
    assert result.returncode == 0, result.stderr
    assert 'HTTP_PROXY' not in values
    assert 'http_proxy' not in values
    assert values['HTTPS_PROXY'] == 'http://proxy.example:8080'
    assert values['https_proxy'] == 'http://proxy.example:8080'
    assert values['NO_PROXY'] == 'localhost,127.0.0.1,::1'
    assert values['no_proxy'] == 'localhost,127.0.0.1,::1'
    for variable in CA_ENV:
        assert variable not in values


def test_supplied_ca_fails_when_the_system_bundle_cannot_be_read(tmp_path):
    extra = tmp_path / 'extra.crt'
    extra.write_text(PEM)
    result, values = _run_entrypoint(tmp_path, extra, tmp_path / 'missing-system.pem')
    assert result.returncode != 0
    assert 'SSL_CERT_FILE' not in values
    assert not (tmp_path / 'combined.pem').exists()
    assert 'cannot build a certificate bundle' in result.stderr


def _proxy_names(value):
    return [item for item in value.split(',') if item]


def test_loopback_is_added_only_when_a_proxy_is_set(tmp_path):
    system = tmp_path / 'system.pem'
    system.write_text('SYSTEM-CA-MARKER\n')
    result, values = _run_entrypoint(
        tmp_path / 'proxy', tmp_path / 'missing.crt', system,
        proxy={'HTTPS_PROXY': 'http://proxy.example:8080'},
    )
    assert result.returncode == 0, result.stderr
    assert _proxy_names(values['NO_PROXY']) == list(LOOPBACK)
    assert values['no_proxy'] == values['NO_PROXY']
    result, values = _run_entrypoint(tmp_path / 'direct', tmp_path / 'missing.crt', system)
    assert result.returncode == 0, result.stderr
    assert 'NO_PROXY' not in values
    assert 'no_proxy' not in values


def test_bundle_is_private_and_does_not_follow_a_symlink(tmp_path):
    system = tmp_path / 'system.pem'
    system.write_text('SYSTEM-CA-MARKER\n')
    extra = tmp_path / 'extra.crt'
    extra.write_text(PEM)
    victim = tmp_path / 'victim.pem'
    victim.write_text('VICTIM-SECRET\n')
    planted = Path('/tmp/livingproof-ca-bundle.crt')
    planted_existed = planted.exists() or planted.is_symlink()
    home = tmp_path / 'home'
    home.mkdir()
    link = tmp_path / 'link.pem'
    link.symlink_to(victim)
    env = {
        'PATH': os.environ['PATH'],
        'HOME': str(home),
        'TMPDIR': str(tmp_path),
        'DEV_EXTRA_CA': str(extra),
        'DEV_SYSTEM_CA_BUNDLE': str(system),
        'DEV_COMBINED_CA_BUNDLE': str(link),
    }
    try:
        if not planted_existed:
            if planted.exists() or planted.is_symlink():
                planted.unlink()
            planted.symlink_to(victim)
        result = subprocess.run(
            ['sh', str(ROOT / 'docker/dev-entrypoint.sh'), 'env'],
            cwd=tmp_path, capture_output=True, text=True, env=env, check=False,
        )
    finally:
        if not planted_existed and (planted.is_symlink() or planted.exists()):
            planted.unlink()
    assert result.returncode == 0, result.stderr
    assert victim.read_text() == 'VICTIM-SECRET\n'
    values = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition('=')
        if separator:
            values[key] = value
    bundle = Path(values['SSL_CERT_FILE'])
    assert bundle != link and bundle != planted
    assert not bundle.is_symlink()
    assert bundle.stat().st_mode & 0o777 == 0o600
    assert bundle.parent.stat().st_mode & 0o777 == 0o700
    assert 'SYSTEM-CA-MARKER' in bundle.read_text()
    assert 'EXTRA-CA' in bundle.read_text()
    assert values['GIT_SSL_CAINFO'] == str(bundle)
