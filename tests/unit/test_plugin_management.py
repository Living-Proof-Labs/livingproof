# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from types import SimpleNamespace
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


def test_pagination_and_default_limit(monkeypatch):
    pages = []
    def api(name, suffix):
        pages.append(suffix)
        page = int(suffix.split('page=')[-1])
        return [{'tag_name': f'v{page}.{i}.0', 'name': f'Title {page}/{i}'} for i in range(100)]
    monkeypatch.setattr(pm, 'api', api)
    runner = CliRunner()
    result = runner.invoke(main, ['plugins', 'versions', pm.REPORTER])
    assert result.exit_code == 0
    assert len(result.output.splitlines()) == 20
    assert 'Title 1/0' in result.output
    pages.clear()
    result = runner.invoke(main, ['plugins', 'versions', pm.REPORTER, '--limit', '121'])
    assert len(result.output.splitlines()) == 121
    assert pages == ['?per_page=100&page=1', '?per_page=100&page=2']


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
    pm.request('https://api.github.com/repos/Living-Proof-Labs/livingproof/releases')
    pm.request('https://github.com/Living-Proof-Labs/livingproof/releases/download/v1/SHA256SUMS')
    assert headers[0]['Authorization'] == 'Bearer test-only-token'
    assert 'Authorization' not in headers[1]
