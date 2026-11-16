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
    'UV_NATIVE_TLS', 'UV_SYSTEM_CERTS',
)
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
    assert '${DEV_CA_BUNDLE:-/dev/null}:/etc/ssl/certs/extra-ca.crt:ro' in text
    volumes = service['volumes']
    assert any('/etc/ssl/certs/extra-ca.crt' in str(item) for item in volumes)


def test_devcontainer_passes_proxy_vars_and_optional_ca():
    config = json.loads((ROOT / '.devcontainer/devcontainer.json').read_text())
    assert config['build']['args']['APT_MIRROR'] == '${localEnv:APT_MIRROR}'
    environment = config['containerEnv']
    for name in PROXY_VARS:
        assert environment[name] == '${localEnv:%s}' % name
    assert config['mounts'] == [
        'source=${localEnv:DEV_CA_BUNDLE:/dev/null},target=/etc/ssl/certs/extra-ca.crt,'
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
    assert values['NO_PROXY'] == 'localhost'
    assert values['no_proxy'] == 'localhost'
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
