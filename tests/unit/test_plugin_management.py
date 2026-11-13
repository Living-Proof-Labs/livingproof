# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import socket
from urllib.error import HTTPError, URLError

from click.testing import CliRunner
import pytest

from livingproof.cli import main
from livingproof import plugin_management as pm


def test_management_help_is_offline(monkeypatch):
    monkeypatch.setattr(pm, 'request', lambda url: pytest.fail('unexpected network'))
    for args in [('plugins', '--help'), ('plugins', 'install', '--help'),
                 ('plugins', 'versions', '--help'), ('--help',)]:
        assert CliRunner().invoke(main, args).exit_code == 0


def test_absent_status_offline(monkeypatch):
    def absent(name):
        raise pm.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(pm.metadata, 'distribution', absent)
    monkeypatch.setattr(pm, 'request', lambda url: pytest.fail('unexpected network'))
    result = CliRunner().invoke(main, ['plugins', 'status', pm.REPORTER])
    assert result.exit_code == 1
    assert 'not installed' in result.output


def published_releases(count):
    """Newest first. The release at index 20 is absent from the default window."""
    return [{'tag_name': f'v{count - index}.0.0', 'name': f'Release {count - index}'}
            for index in range(count)]


def listing_text(records):
    return ''.join(f"{record['tag_name']}\t{record['name']}\n" for record in records)


def page_body(records, url):
    page = int(url.rsplit('page=', 1)[-1])
    start = (page - 1) * 100
    return BytesIO(json.dumps(records[start:start + 100]).encode())


@pytest.fixture
def release_listing(monkeypatch):
    """Feed versions with more than 20 releases, or an absent, empty, or error page."""
    state = {'urls': []}

    def urlopen(request, timeout):
        state['urls'].append(request.full_url)
        return state['handler'](request)

    monkeypatch.setattr(pm, 'urlopen', urlopen)

    def configure(handler):
        state['handler'] = handler
        state['urls'] = []
        return state

    return configure


def test_recent_listing_keeps_only_the_newest_window(release_listing):
    records = published_releases(130)
    state = release_listing(lambda request: page_body(records, request.full_url))
    runner = CliRunner()
    result = runner.invoke(main, ['plugins', 'versions', pm.REPORTER])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines == [f'v{number}.0.0\tRelease {number}' for number in range(130, 110, -1)]
    assert 'v110.0.0' not in result.output
    assert [url.rsplit('page=', 1)[-1] for url in state['urls']] == ['1']
    state['urls'].clear()
    wider = runner.invoke(main, ['plugins', 'versions', pm.REPORTER, '--limit', '121'])
    assert wider.exit_code == 0
    wider_lines = wider.output.splitlines()
    assert len(wider_lines) == 121
    assert wider_lines[:20] == lines
    assert wider_lines[20] == 'v110.0.0\tRelease 110'
    assert [url.rsplit('page=', 1)[-1] for url in state['urls']] == ['1', '2']


def test_absent_release_listing(release_listing):
    def handler(request):
        raise HTTPError(request.full_url, 404, 'absent', {}, None)
    release_listing(handler)
    result = CliRunner().invoke(main, ['plugins', 'versions', pm.REPORTER])
    assert result.exit_code == 1
    assert 'not found' in result.output


def test_empty_release_listing(release_listing):
    release_listing(lambda request: BytesIO(b'[]'))
    result = CliRunner().invoke(main, ['plugins', 'versions', pm.REPORTER])
    assert result.exit_code == 0
    assert result.output == ''


@pytest.mark.parametrize('payload,text', [
    (b'not-json', 'invalid release metadata'),
    (b'{"message": "bad"}', 'invalid release-list metadata'),
])
def test_error_release_listing(release_listing, payload, text):
    release_listing(lambda request: BytesIO(payload))
    result = CliRunner().invoke(main, ['plugins', 'versions', pm.REPORTER])
    assert result.exit_code == 1
    assert text in result.output


def test_release_listing_request_error(release_listing):
    def handler(request):
        raise HTTPError(request.full_url, 500, 'down', {}, None)
    release_listing(handler)
    result = CliRunner().invoke(main, ['plugins', 'versions', pm.REPORTER])
    assert result.exit_code == 1
    assert 'HTTP 500' in result.output


def load_probe():
    path = Path(__file__).resolve().parents[2] / 'tools/plugin_management_probe.py'
    spec = importlib.util.spec_from_file_location('plugin_management_probe', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_listing_does_not_require_an_aged_out_release():
    probe = load_probe()
    records = published_releases(25)
    probe.assert_recent_listing(listing_text(records[:20]), listing_text(records))
    short = published_releases(5)
    probe.assert_recent_listing(listing_text(short), listing_text(short))
    with pytest.raises(AssertionError):
        probe.assert_recent_listing(listing_text(records), listing_text(records))


def test_unknown_name_rejected_before_network(monkeypatch):
    monkeypatch.setattr(pm, 'request', lambda url: pytest.fail('unexpected network'))
    for action in ('install', 'versions', 'status'):
        assert CliRunner().invoke(main, ['plugins', action, 'https://evil/test']).exit_code == 2


@pytest.mark.parametrize('error,text', [
    (URLError('offline'), 'offline'),
    (HTTPError('https://api.github.com', 429, 'limited', {}, None), 'rate limit'),
    (HTTPError('https://api.github.com', 404, 'absent', {}, None), 'not found'),
])
def test_network_errors(monkeypatch, error, text):
    def broken(req, timeout):
        raise error
    monkeypatch.setattr(pm, 'urlopen', broken)
    with pytest.raises(Exception, match=text):
        pm.request('https://api.github.com')


def release_transport(monkeypatch, respond):
    """Script the release opener. respond(attempt, request) returns a body or raises."""
    calls = []
    sleeps = []

    def urlopen(request, timeout):
        calls.append(request.full_url)
        return respond(len(calls), request)

    monkeypatch.setattr(pm, 'urlopen', urlopen)
    monkeypatch.setattr(pm, 'pause', sleeps.append)
    return calls, sleeps


@pytest.mark.parametrize('status', [502, 503, 504])
def test_transient_status_then_success(monkeypatch, status):
    def respond(attempt, request):
        if attempt == 1:
            raise HTTPError(request.full_url, status, 'unavailable', {}, None)
        return BytesIO(b'ok')
    calls, sleeps = release_transport(monkeypatch, respond)
    assert pm.request('https://api.github.com/repos/example/releases/tags/v1.6.0') == b'ok'
    assert len(calls) == 2
    assert sleeps == [pm.RELEASE_RETRY_BASE_SECONDS]


def test_repeated_502_fails_after_every_attempt(monkeypatch):
    def respond(attempt, request):
        raise HTTPError(request.full_url, 502, 'bad gateway', {}, None)
    calls, sleeps = release_transport(monkeypatch, respond)
    result = CliRunner().invoke(main, ['plugins', 'versions', pm.REPORTER])
    assert result.exit_code == 1
    assert result.output == (
        'Error: Release request failed (HTTP 502). Retry when the service is available.\n')
    assert len(calls) == pm.RELEASE_ATTEMPTS
    assert len(sleeps) == pm.RELEASE_ATTEMPTS - 1


@pytest.mark.parametrize('error', [
    ConnectionResetError('Connection reset by peer'),
    URLError(ConnectionResetError('Connection reset by peer')),
], ids=['reset', 'wrapped reset'])
def test_connection_reset_is_retried(monkeypatch, error):
    def respond(attempt, request):
        if attempt == 1:
            raise error
        return BytesIO(b'ok')
    calls, sleeps = release_transport(monkeypatch, respond)
    assert pm.request('https://api.github.com/repos/example/releases/tags/v1.6.0') == b'ok'
    assert len(calls) == 2
    assert sleeps == [pm.RELEASE_RETRY_BASE_SECONDS]


@pytest.mark.parametrize('error,text', [
    (HTTPError('https://api.github.com', 404, 'absent', {}, None), 'not found'),
    (HTTPError('https://api.github.com', 403, 'denied', {}, None), 'rate limit'),
    (HTTPError('https://api.github.com', 429, 'limited', {}, None), 'rate limit'),
    (HTTPError('https://api.github.com', 500, 'down', {}, None), 'HTTP 500'),
    (URLError('offline'), 'offline'),
    (URLError(socket.gaierror(socket.EAI_NONAME, 'Name or service not known')), 'offline'),
])
def test_non_transient_release_errors_fail_immediately(monkeypatch, error, text):
    def respond(attempt, request):
        raise error
    calls, sleeps = release_transport(monkeypatch, respond)
    with pytest.raises(Exception, match=text):
        pm.request('https://api.github.com')
    assert len(calls) == 1
    assert sleeps == []


@pytest.mark.parametrize('error', [
    TimeoutError('timed out'),
    URLError(TimeoutError('timed out')),
    URLError(socket.timeout('timed out')),
], ids=['timeout', 'wrapped timeout', 'wrapped socket.timeout'])
def test_timeout_is_retried(monkeypatch, error):
    def respond(attempt, request):
        if attempt == 1:
            raise error
        return BytesIO(b'ok')
    calls, sleeps = release_transport(monkeypatch, respond)
    assert pm.request('https://api.github.com/repos/example/releases/tags/v1.6.0') == b'ok'
    assert len(calls) == 2
    assert sleeps == [pm.RELEASE_RETRY_BASE_SECONDS]


def test_fourth_attempt_can_succeed(monkeypatch):
    def respond(attempt, request):
        if attempt < pm.RELEASE_ATTEMPTS:
            raise HTTPError(request.full_url, 502, 'bad gateway', {}, None)
        return BytesIO(b'ok')
    calls, sleeps = release_transport(monkeypatch, respond)
    assert pm.request('https://api.github.com/repos/example/releases/tags/v1.6.0') == b'ok'
    assert len(calls) == pm.RELEASE_ATTEMPTS
    assert sleeps == [pm.RELEASE_RETRY_BASE_SECONDS, pm.RELEASE_RETRY_MAX_DELAY_SECONDS,
                      pm.RELEASE_RETRY_MAX_DELAY_SECONDS]


def test_release_backoff_stays_under_the_cap(monkeypatch):
    def respond(attempt, request):
        raise HTTPError(request.full_url, 502, 'bad gateway', {}, None)
    calls, sleeps = release_transport(monkeypatch, respond)
    with pytest.raises(Exception, match='HTTP 502'):
        pm.request('https://api.github.com/repos/example/releases/tags/v1.6.0')
    assert len(calls) == pm.RELEASE_ATTEMPTS
    uncapped = sum(pm.RELEASE_RETRY_BASE_SECONDS * (2 ** index) for index in range(len(sleeps)))
    assert uncapped > pm.RELEASE_RETRY_TOTAL_CAP_SECONDS
    assert sleeps == [pm.RELEASE_RETRY_BASE_SECONDS, pm.RELEASE_RETRY_MAX_DELAY_SECONDS,
                      pm.RELEASE_RETRY_MAX_DELAY_SECONDS]
    assert all(delay <= pm.RELEASE_RETRY_MAX_DELAY_SECONDS for delay in sleeps)
    assert sum(sleeps) < pm.RELEASE_RETRY_TOTAL_CAP_SECONDS


@pytest.mark.parametrize('checksum', ['0' * 64, None])
def test_checksum_failure_no_file(tmp_path, monkeypatch, checksum):
    asset = {'name': 'test.whl', 'browser_download_url':
             f'https://github.com/{pm.REGISTRY[pm.REPORTER][0]}/releases/download/v1/test.whl'}
    sums = {**asset, 'name': 'SHA256SUMS', 'browser_download_url':
            asset['browser_download_url'].replace('test.whl', 'SHA256SUMS')}
    monkeypatch.setattr(pm, 'request', lambda url: (
        f'{checksum}  test.whl\n'.encode() if url.endswith('SHA256SUMS') else b'wheel'))
    with pytest.raises(Exception, match='Checksum mismatch|SHA256SUMS entry'):
        pm.verified_asset(pm.REPORTER, {'tag_name': 'v1', 'assets': [sums]}, asset, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_asset_registry_boundary():
    with pytest.raises(Exception, match='trusted repository'):
        pm.asset_url(pm.REPORTER, {'name': 'a.whl', 'browser_download_url': 'https://evil/a.whl'})


def test_verified_download(tmp_path, monkeypatch):
    base = f'https://github.com/{pm.REGISTRY[pm.REPORTER][0]}/releases/download/v1/'
    asset = {'name': 'a.whl', 'browser_download_url': base + 'a.whl'}
    sums = {'name': 'SHA256SUMS', 'browser_download_url': base + 'SHA256SUMS'}
    monkeypatch.setattr(pm, 'request', lambda url: (
        (hashlib.sha256(b'wheel').hexdigest() + '  a.whl').encode()
        if url.endswith('SHA256SUMS') else b'wheel'))
    assert pm.verified_asset(pm.REPORTER, {'assets': [sums]}, asset, tmp_path).read_bytes() == b'wheel'


def test_venv_precedes_dpkg(monkeypatch):
    monkeypatch.setattr(pm.metadata, 'distribution', lambda name: object())
    monkeypatch.setattr(pm.sys, 'prefix', '/venv')
    monkeypatch.setattr(pm.sys, 'base_prefix', '/usr')
    assert pm.context() == 'wheel'


def test_broken_status_is_not_success(monkeypatch):
    dist = SimpleNamespace(version='1.6.0', name=pm.REPORTER)
    monkeypatch.setattr(pm.metadata, 'distribution', lambda name: dist)
    monkeypatch.setattr(pm.metadata, 'entry_points', lambda **kw: [])
    with pytest.raises(Exception, match='missing or ambiguous'):
        pm.installed(pm.REPORTER)


def test_release_selection(monkeypatch):
    calls = []
    monkeypatch.setattr(pm, 'api', lambda name, suffix:
                        calls.append(suffix) or {'tag_name': 'v1.6.0'})
    pm.release(pm.REPORTER, None)
    pm.release(pm.REPORTER, '1.6.0')
    assert calls == ['/latest', '/tags/v1.6.0']
    with pytest.raises(Exception, match='Version must'):
        pm.release(pm.REPORTER, 'https://evil')


def test_invalid_api_response(monkeypatch):
    monkeypatch.setattr(pm, 'request', lambda url: b'not json')
    with pytest.raises(Exception, match='invalid release metadata'):
        pm.api(pm.REPORTER, '/latest')
    monkeypatch.setattr(pm, 'request', lambda url: json.dumps({}).encode())
    assert pm.api(pm.REPORTER, '/latest') == {}


def test_common_conflict_fails_before_install(monkeypatch, tmp_path):
    monkeypatch.setattr(pm, 'context', lambda: 'wheel')
    monkeypatch.setattr(pm, 'release', lambda *args: {'tag_name': 'v1.6.0'})
    monkeypatch.setattr(pm, 'select', lambda *args: {})
    monkeypatch.setattr(pm, 'verified_asset', lambda *args: tmp_path / 'report.whl')
    monkeypatch.setattr(pm, 'inspect', lambda *args: ('1.6.0', '2.0.0'))
    monkeypatch.setattr(pm.metadata, 'requires', lambda name: ['livingproof-common==1.0.0'])
    monkeypatch.setattr(pm.subprocess, 'run', lambda *args, **kw: pytest.fail('mutation'))
    with pytest.raises(Exception, match='incompatible with root'):
        pm.install(pm.REPORTER, '1.6.0')


def test_common_unavailable_fails_before_install(monkeypatch, tmp_path):
    monkeypatch.setattr(pm, 'context', lambda: 'wheel')
    def release(name, version):
        if name == pm.COMMON:
            pm.fail('Common release not found')
        return {'tag_name': 'v1.6.0'}
    monkeypatch.setattr(pm, 'release', release)
    monkeypatch.setattr(pm, 'select', lambda *args: {})
    monkeypatch.setattr(pm, 'verified_asset', lambda *args: tmp_path / 'report.whl')
    monkeypatch.setattr(pm, 'inspect', lambda *args: ('1.6.0', '1.0.0'))
    monkeypatch.setattr(pm.metadata, 'requires', lambda name: ['livingproof-common==1.0.0'])
    monkeypatch.setattr(pm.subprocess, 'run', lambda *args, **kw: pytest.fail('mutation'))
    with pytest.raises(Exception, match='Common release not found'):
        pm.install(pm.REPORTER, '1.6.0')


def test_missing_asset():
    with pytest.raises(Exception, match='compatible wheel asset'):
        pm.select(pm.REPORTER, {'tag_name': 'v1', 'assets': []}, 'wheel')


def test_externally_managed_context(monkeypatch, tmp_path):
    monkeypatch.setattr(pm.sys, 'prefix', '/usr')
    monkeypatch.setattr(pm.sys, 'base_prefix', '/usr')
    monkeypatch.setattr(pm.metadata, 'distribution', lambda name:
                        SimpleNamespace(locate_file=lambda name: tmp_path / name))
    monkeypatch.setattr(pm.shutil, 'which', lambda name: None)
    monkeypatch.setattr(pm.sysconfig, 'get_path', lambda name: str(tmp_path))
    (tmp_path / 'EXTERNALLY-MANAGED').touch()
    with pytest.raises(Exception, match='PEP 668'):
        pm.context()
    (tmp_path / 'EXTERNALLY-MANAGED').unlink()
    with pytest.raises(Exception, match='Unsupported root installation context'):
        pm.context()


def test_optional_api_token_never_sent_to_assets(monkeypatch):
    from io import BytesIO
    headers = []
    monkeypatch.setenv('LIVINGPROOF_GITHUB_TOKEN', 'test-only-token')
    def opened(req, timeout):
        headers.append(dict(req.header_items()))
        return BytesIO(b'{}')
    monkeypatch.setattr(pm, 'urlopen', opened)
    monkeypatch.setattr(pm, 'build_opener', lambda handler: SimpleNamespace(open=opened))
    pm.request('https://api.github.com/repos/Living-Proof-Labs/livingproof/releases')
    pm.request('https://github.com/Living-Proof-Labs/livingproof/releases/download/v1/SHA256SUMS')
    assert headers[0]['Authorization'] == 'Bearer test-only-token'
    assert 'Authorization' not in headers[1]


def test_debian_asset_architecture_selection(monkeypatch):
    monkeypatch.setattr(pm, 'run', lambda args: 'arm64')
    assets = [{'name': f'{pm.REPORTER}_1.6.0_{arch}.deb'} for arch in ('amd64', 'arm64')]
    selected = pm.select(pm.REPORTER, {'tag_name': 'v1.6.0', 'assets': assets}, 'deb')
    assert selected['name'].endswith('_arm64.deb')


def test_authenticated_redirect_refuses_credential_forwarding():
    with pytest.raises(Exception, match='no credentials forwarded'):
        pm.NoAuthenticatedRedirect().redirect_request(None, None, 302, '', {}, 'https://evil')


@pytest.mark.parametrize('url', [
    'http://api.github.com/repos/Living-Proof-Labs/livingproof/releases',
    'https://api.github.com.evil.invalid/releases',
    'https://api.github.com@evil.invalid/releases',
    'https://release-assets.githubusercontent.com/example',
    'https://github.com/Living-Proof-Labs/livingproof/releases/download/v1/SHA256SUMS',
])
def test_token_requires_exact_https_api_origin(monkeypatch, url):
    from io import BytesIO
    monkeypatch.setenv('LIVINGPROOF_GITHUB_TOKEN', 'test-only-token')
    def opened(req, timeout):
        assert req.get_header('Authorization') is None
        return BytesIO(b'{}')
    monkeypatch.setattr(pm, 'urlopen', opened)
    monkeypatch.setattr(pm, 'build_opener', lambda handler: pytest.fail('authenticated opener'))
    assert pm.request(url) == b'{}'


def test_api_error_does_not_log_token_or_response_details(monkeypatch):
    token = 'test-only-token-never-log'
    monkeypatch.setenv('LIVINGPROOF_GITHUB_TOKEN', token)
    def denied(req, timeout):
        assert req.get_header('Authorization') == 'Bearer ' + token
        raise HTTPError(req.full_url, 403, token, {'Authorization': token}, None)
    monkeypatch.setattr(pm, 'build_opener', lambda handler: SimpleNamespace(open=denied))
    result = CliRunner().invoke(main, ['plugins', 'versions', pm.REPORTER])
    assert result.exit_code == 1
    assert 'rate limit or access restriction' in result.output
    assert token not in result.output
    assert 'Authorization' not in result.output
