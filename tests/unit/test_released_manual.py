# SPDX-License-Identifier: Apache-2.0
"""Exercise exact-release gates using real disposable Git tags, without publishing."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('released_manual', ROOT / 'tools/released_manual.py')
manual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manual)


@pytest.fixture
def release(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def git(*args):
        return subprocess.check_output(['git', *args], text=True).strip()
    git('init', '-q')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
        'commit', '--allow-empty', '-qm', 'fixture')
    commit = git('rev-parse', 'HEAD')
    git('tag', 'v1.2.3')
    return commit, {'tag_name': 'v1.2.3', 'draft': False, 'prerelease': False,
                    'immutable': True, 'published_at': '2026-11-22T00:00:00Z'}


def test_release_and_delivery_retry_never_change_tag(release):
    commit, record = release
    before = manual.git('show-ref', '--tags')
    for _ in range(2):
        manual.published(record, '1.2.3', 'v1.2.3', commit)
    assert manual.git('show-ref', '--tags') == before


@pytest.mark.parametrize('change', [{}, {'draft': True}, {'prerelease': True},
    {'immutable': False}, {'published_at': None}, {'tag_name': 'v1.2.4'}])
def test_missing_failed_unpublished_or_mismatched_release(release, change):
    commit, record = release
    with pytest.raises(ValueError):
        manual.published({**record, **change} if change else {}, '1.2.3', 'v1.2.3', commit)


@pytest.mark.parametrize('version,tag,commit', [
    ('1.2.4', 'v1.2.3', None), ('0.0.0', 'v0.0.0', None),
    ('1.2.3', '', None), ('1.2.3', 'v1.2.3', 'a' * 40),
    ('1.2.4', 'v1.2.4', None)])
def test_tag_version_source_mismatch(release, version, tag, commit):
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        manual.source(version, tag, commit or release[0])


def test_candidate_remains_preview(release, monkeypatch):
    monkeypatch.delenv('MANUAL_CHANNEL', raising=False)
    manual.source('0.0.0', '', release[0])
    assert manual.identity('1.2.3', release[0])['channel'] == 'preview'


def test_failed_release_lookup_cannot_authorize_manual(release, monkeypatch):
    commit, _ = release
    for key, value in {'MANUAL_CHANNEL': 'release', 'RELEASE_VERSION': '1.2.3',
                       'RELEASE_TAG': 'v1.2.3', 'GITHUB_SHA': commit}.items():
        monkeypatch.setenv(key, value)
    def fail(_):
        raise subprocess.CalledProcessError(1, 'gh')
    monkeypatch.setattr(manual, 'release_record', fail)
    with pytest.raises(subprocess.CalledProcessError):
        manual.identity('1.2.3', commit)


def test_workflow_preserves_finalizers_and_separates_manual():
    jobs = yaml.safe_load((ROOT / '.github/workflows/verify.yml').read_text())['jobs']
    assert jobs['verify']['with'] == {'version': '0.0.0'}
    assert jobs['release']['needs'] == ['verify', 'development']
    assert jobs['publish']['needs'] == ['release', 'assets', 'registry-consumption']
    assert jobs['stable-manual']['needs'] == ['release', 'assets', 'publish', 'consume-public']
    assert 'always()' not in jobs['stable-manual']['if']
    assert jobs['assets']['with']['release-tag'] == '${{ needs.release.outputs.git-tag }}'
    steps = jobs['stable-manual']['steps']
    uploads = [s for s in steps if s.get('uses', '').startswith('actions/upload-artifact@')]
    pages = next(s for s in uploads if s.get('id') == 'pages')
    assert pages['with'].get('overwrite', False) is False
    commands = '\n'.join(s.get('run', '') for s in steps)
    assert 'task docs' in commands and 'task test:docs' in commands
    assert 'tools/released_manual.py published' in commands
    assert 'release edit' not in commands and 'git tag' not in commands


def test_visible_identity_for_preview_and_release(tmp_path):
    spec = importlib.util.spec_from_file_location('portal', ROOT / 'tools/docs_portal.py')
    portal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(portal)
    for channel, tag, expected in [('preview', None, 'development preview'),
                                    ('release', 'v1.2.3', 'v1.2.3')]:
        (tmp_path / 'build.json').write_text(json.dumps({
            'source_commit': 'a' * 40, 'source_dirty': False, 'source_url': 'https://example.org',
            'channel': channel, 'release_tag': tag}))
        (tmp_path / 'index.html').write_text('<article></article>')
        portal.add_identity(tmp_path)
        assert f'Docs: {expected}' in (tmp_path / 'index.html').read_text()


def test_released_identity_requires_matching_package_and_clean_tree(release, monkeypatch):
    commit, record = release
    for key, value in {'MANUAL_CHANNEL': 'release', 'RELEASE_VERSION': '1.2.3',
                       'RELEASE_TAG': 'v1.2.3', 'GITHUB_SHA': commit}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(manual, 'release_record', lambda _: record)
    wheel = Path('.git/livingproof-1.2.3-py3-none-any.whl')
    wheel.write_bytes(b'released-wheel')
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    record['assets'] = [{'name': wheel.name, 'digest': f'sha256:{digest}'}]
    assert manual.identity('1.2.3', commit, wheel) == {
        'channel': 'release', 'version': '1.2.3', 'release_tag': 'v1.2.3',
        'release_wheel_sha256': digest}
    with pytest.raises(ValueError, match='package'):
        manual.identity('0.0.0', commit)
    Path('unexpected-source').write_text('dirty')
    with pytest.raises(ValueError, match='clean'):
        manual.identity('1.2.3', commit)


@pytest.mark.parametrize('assets', [[], [{'name': 'other.whl', 'digest': 'sha256:wrong'}],
    [{'name': 'root.whl'}], [{'name': 'root.whl', 'digest': 'sha256:' + 'a' * 64}],
    [{'name': 'root.whl'}, {'name': 'root.whl'}]])
def test_missing_mismatched_duplicate_release_wheel_rejected(tmp_path, assets):
    wheel = tmp_path / 'root.whl'
    wheel.write_bytes(b'candidate')
    with pytest.raises(ValueError):
        manual.released_wheel_digest({'assets': assets}, wheel)


def test_modified_archive_wheel_is_not_a_release_asset(tmp_path):
    wheel = tmp_path / 'root.whl'
    wheel.write_bytes(b'published bytes')
    record = {'assets': [{'name': wheel.name,
                         'digest': 'sha256:' + hashlib.sha256(wheel.read_bytes()).hexdigest()}]}
    assert manual.released_wheel_digest(record, wheel)
    wheel.write_bytes(b'same filename but different archive bytes')
    with pytest.raises(ValueError):
        manual.released_wheel_digest(record, wheel)
