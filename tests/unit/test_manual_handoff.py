# SPDX-License-Identifier: Apache-2.0
"""Execute the no-checkout deployment's identity and byte-integrity gates offline."""
import hashlib
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
JOBS = yaml.safe_load((ROOT / '.github/workflows/verify.yml').read_text())['jobs']
DEPLOY = JOBS['documentation']


def execute(script, env):
    return subprocess.run(['bash', '-c', script], capture_output=True, text=True,
                          env={**os.environ, **env})


@pytest.mark.parametrize('change,success', [({}, True),
    ({'GITHUB_RUN_ATTEMPT': '2'}, True),  # deploy-only retry reuses successful builder
    ({'MANUAL_ID': ''}, False), ({'MANUAL_ID': '12,13'}, False),
    ({'MANUAL_ATTEMPT': '0'}, False), ({'MANUAL_ATTEMPT': '2'}, False),
    ({'MANUAL_NAME': 'github-pages-999-1'}, False),
    ({'MANUAL_NAME': 'github-pages-123-2'}, False),
    ({'MANUAL_DIGEST': 'invalid'}, False)])
def test_run_attempt_native_identity_gate(change, success):
    env = {'MANUAL_ID': '456', 'MANUAL_NAME': 'github-pages-123-1',
           'MANUAL_ATTEMPT': '1', 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1',
           'MANUAL_DIGEST': 'a' * 64, **change}
    result = execute(DEPLOY['steps'][0]['run'], env)
    assert (result.returncode == 0) is success, result.stderr


@pytest.mark.parametrize('id_retry,name_retry', [(False, False), (True, False),
                                                (False, True), (True, True)])
@pytest.mark.parametrize('damage', [None, 'id', 'name', 'missing-id', 'missing-name'])
def test_both_native_readbacks_require_exact_bytes(tmp_path, id_retry, name_retry, damage):
    content = b'opaque Pages tar bytes; never executed'
    env = {'RUNNER_TEMP': str(tmp_path), 'MANUAL_DIGEST': hashlib.sha256(content).hexdigest()}
    for kind, retry in [('id', id_retry), ('name', name_retry)]:
        env[f'{kind.upper()}_OUTCOME'] = 'failure' if retry else 'success'
        env[f'{kind.upper()}_RETRY_OUTCOME'] = 'success' if retry else 'skipped'
        target = tmp_path / f'released-manual-{kind}{"-retry" if retry else ""}/artifact.tar'
        target.parent.mkdir()
        if damage != f'missing-{kind}':
            target.write_bytes(b'altered bytes' if damage == kind else content)
        if retry:
            # A failed first download's valid residue cannot rescue a damaged retry.
            residue = tmp_path / f'released-manual-{kind}/artifact.tar'
            residue.parent.mkdir()
            residue.write_bytes(content)
    script = next(s['run'] for s in DEPLOY['steps'] if 'Verify both' in s.get('name', ''))
    assert (execute(script, env).returncode == 0) is (damage is None)


@pytest.mark.parametrize('kind', ['id', 'name'])
@pytest.mark.parametrize('outcome,retry_outcome', [('failure', 'failure'),
                                                ('failure', 'skipped'), ('skipped', 'success')])
def test_lookup_failure_cannot_be_hidden_by_download_residue(tmp_path, kind, outcome, retry_outcome):
    content = b'valid residue'
    env = {'RUNNER_TEMP': str(tmp_path), 'MANUAL_DIGEST': hashlib.sha256(content).hexdigest(),
           'ID_OUTCOME': 'success', 'ID_RETRY_OUTCOME': 'skipped',
           'NAME_OUTCOME': 'success', 'NAME_RETRY_OUTCOME': 'skipped',
           f'{kind.upper()}_OUTCOME': outcome, f'{kind.upper()}_RETRY_OUTCOME': retry_outcome}
    for directory in ['id', 'id-retry', 'name', 'name-retry']:
        target = tmp_path / f'released-manual-{directory}/artifact.tar'
        target.parent.mkdir()
        target.write_bytes(content)
    script = next(s['run'] for s in DEPLOY['steps'] if 'Verify both' in s.get('name', ''))
    assert execute(script, env).returncode != 0


def test_builder_has_no_write_scopes_and_deploy_has_no_checkout_or_repo_execution():
    builder = JOBS['stable-manual']
    assert builder['permissions'] == {'contents': 'read'}
    assert 'environment' not in builder and 'concurrency' not in builder
    assert DEPLOY['permissions'] == {'pages': 'write', 'id-token': 'write'}
    assert DEPLOY['concurrency'] == {'group': 'github-pages', 'cancel-in-progress': False}
    assert DEPLOY['needs'] == 'stable-manual'
    steps = DEPLOY['steps']
    actions = [s['uses'].split('@')[0] for s in steps if 'uses' in s]
    assert actions == ['actions/download-artifact'] * 4 + [
        'actions/configure-pages', 'actions/deploy-pages']
    scripts = '\n'.join(s.get('run', '') for s in steps)
    for forbidden in ('docker ', 'task ', 'python ', 'uv ', 'npm ', 'tools/', 'tar -', 'source '):
        assert forbidden not in scripts
    assert steps[-2]['id'] == 'freshness'  # last operation immediately before deployment
    assert steps[-1]['if'] == "steps.freshness.outputs.current == 'true'"


def test_native_id_name_digest_are_outputs_of_the_same_immutable_upload():
    builder = JOBS['stable-manual']
    upload = next(s for s in builder['steps'] if s.get('id') == 'pages')
    assert upload['with']['name'] == '${{ steps.package.outputs.artifact-name }}'
    assert upload['with'].get('overwrite', False) is False
    assert upload['with']['path'] == '${{ runner.temp }}/artifact.tar'
    assert builder['outputs']['artifact-id'] == '${{ steps.pages.outputs.artifact-id }}'
    assert builder['outputs']['tar-sha256'] == '${{ steps.package.outputs.tar-sha256 }}'
    downloads = [s for s in DEPLOY['steps'] if s.get('uses', '').startswith('actions/download-artifact@')]
    assert len(downloads) == 4
    assert len({s['with']['path'] for s in downloads}) == 4
    for kind, field in [('id', 'artifact-ids'), ('name', 'name')]:
        initial, retry = [s for s in downloads if s['id'].startswith(f'read_{kind}')]
        for step in [initial, retry]:
            assert step['with'][field] == '${{ needs.stable-manual.outputs.artifact-' + kind + ' }}'
            assert not {'run-id', 'github-token', 'repository', 'pattern'} & step['with'].keys()
            assert step['continue-on-error'] is True
        assert 'if' not in initial
        assert retry['if'] == f"steps.read_{kind}.outcome == 'failure'"
        assert set(initial['with']) & {'artifact-ids', 'name'} == {field}
        assert set(retry['with']) & {'artifact-ids', 'name'} == {field}
    assert DEPLOY['steps'][-1]['with']['artifact_name'] == '${{ needs.stable-manual.outputs.artifact-name }}'
