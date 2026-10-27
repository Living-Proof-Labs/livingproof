# SPDX-License-Identifier: Apache-2.0
"""Execute the workflow's real freshness gate with an isolated remote-ref stub."""
import os
from pathlib import Path
import re
import subprocess
import textwrap

import pytest

WORKFLOW = Path(__file__).resolve().parents[2] / '.github/workflows/verify.yml'
CURRENT = 'a' * 40
OLD = 'b' * 40


def documentation_job():
    return WORKFLOW.read_text().split('  documentation:\n', 1)[1].split('  release:\n', 1)[0]


@pytest.mark.parametrize('remote,exit_code,expected', [
    (CURRENT + '\trefs/heads/main', 0, 'true'),
    (OLD + '\trefs/heads/main', 0, 'false'),
    ('', 2, None),
    ('', 0, None),
    ('not-a-sha\trefs/heads/main', 0, None),
    (CURRENT + '\trefs/heads/other', 0, None),
    (CURRENT + '\trefs/heads/main', 128, None),
])
def test_current_stale_and_unavailable_main(tmp_path, remote, exit_code, expected):
    script = re.search(r'        run: \|\n(.*?)      # Same run',
                       documentation_job(), re.S).group(1)
    git = tmp_path / 'git'
    git.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$GIT_ARGS"\n'
                   'printf "%s\\n" "$REMOTE_REF"\nexit "$REMOTE_EXIT"\n')
    git.chmod(0o755)
    output = tmp_path / 'output'
    summary = tmp_path / 'summary'
    args = tmp_path / 'git-args'
    result = subprocess.run(['bash', '-c', textwrap.dedent(script)],
                            capture_output=True, text=True, env={**os.environ,
        'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'],
        'GITHUB_SHA': CURRENT, 'GITHUB_REPOSITORY': 'Living-Proof-Labs/livingproof',
        'GITHUB_OUTPUT': str(output), 'GITHUB_STEP_SUMMARY': str(summary),
        'GIT_ARGS': str(args), 'REMOTE_REF': remote, 'REMOTE_EXIT': str(exit_code)})
    assert args.read_text().splitlines() == [
        '-c', 'credential.helper=', 'ls-remote', '--exit-code',
        'https://github.com/Living-Proof-Labs/livingproof.git', 'refs/heads/main']
    if expected is None:
        assert result.returncode != 0
        assert not output.exists()  # Never authorizes publication on lookup failure.
    else:
        assert result.returncode == 0, result.stderr
        assert output.read_text() == f'current={expected}\n'
        if expected == 'false':
            assert 'Skipping stale documentation' in summary.read_text()
        else:
            assert not summary.exists()


def test_every_publication_step_requires_current_main():
    job = documentation_job()
    assert '    concurrency:\n      group: github-pages\n' in job
    steps = re.split(r'^      - ', job.split('    steps:\n', 1)[1], flags=re.M)[1:]
    assert 'id: freshness' in steps[0]
    assert len(steps[1:]) == 5
    for step in steps[1:]:
        assert "if: steps.freshness.outputs.current == 'true'" in step
