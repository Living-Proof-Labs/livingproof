# SPDX-License-Identifier: Apache-2.0
"""Exercise the shipped CLI in disposable containers, never a source import."""
import os
from pathlib import Path
import subprocess
import sys

NAME = 'livingproof-capability-report'


def run(*args, expected=0, env=None):
    result = subprocess.run(args, capture_output=True, text=True, env=env)
    print('$', ' '.join(args), '\n', result.stdout, result.stderr, flush=True)
    assert result.returncode == expected, result
    return result.stdout + result.stderr


def main(mode):
    # An unreachable proxy proves local status/help/completion never require network.
    offline = {**os.environ, 'https_proxy': 'http://127.0.0.1:1',
               'HTTPS_PROXY': 'http://127.0.0.1:1'}
    run('livingproof', 'plugins', 'status', NAME, expected=1, env=offline)
    run('livingproof', 'capability', 'report', expected=1, env=offline)
    run('livingproof', '--help', env=offline)
    run('livingproof', '--version', env=offline)
    listed = run('livingproof', 'plugins', 'versions', NAME)
    assert 'v1.6.0' in listed
    plan = run('livingproof', 'plugins', 'install', NAME, '--version', '1.6.0', '--dry-run')
    assert 'common' in plan and 'SHA256SUMS' in plan
    assert ('system Debian' if mode == 'deb' else 'Python environment') in plan
    run('livingproof', 'plugins', 'status', NAME, expected=1, env=offline)
    if mode == 'deb':
        denied = run('runuser', '-u', 'nobody', '--', 'livingproof', 'plugins', 'install',
                     NAME, '--version', '1.6.0', expected=1)
        assert 'Administrator privileges required' in denied
    # Historical pin then upgrade exercises package-manager downgrade/upgrade selection.
    run('livingproof', 'plugins', 'install', NAME, '--version', '1.4.0')
    assert '1.4.0' in run('livingproof', 'plugins', 'status', NAME, env=offline)
    # Force a missing common dependency only inside this throwaway container.
    if mode == 'deb':
        run('dpkg', '--remove', '--force-depends', 'python3-livingproof-common')
    else:
        run(sys.executable, '-m', 'pip', 'uninstall', '-y', 'livingproof-common')
    run('livingproof', 'plugins', 'install', NAME, '--version', '1.6.0')
    assert '1.6.0' in run('livingproof', 'plugins', 'status', NAME, env=offline)
    standalone = run(NAME, '--version', env=offline)
    nested = run('livingproof', 'capability', 'report', '--version', env=offline)
    assert standalone == nested
    assert 'recorded-build' in nested
    run('livingproof', 'capability', 'report', '--help', env=offline)
    completion = run('livingproof', env={**offline, '_LIVINGPROOF_COMPLETE': 'bash_complete',
                      'COMP_WORDS': 'livingproof capability report re', 'COMP_CWORD': '3'})
    assert 'render' in completion
    # Repeating the default release must preserve discovery and common dependency.
    run('livingproof', 'plugins', 'install', NAME)
    run('livingproof', 'plugins', 'status', NAME, env=offline)
    if mode == 'deb':
        run('apt-get', 'remove', '-y', NAME)
    else:
        run(sys.executable, '-m', 'pip', 'uninstall', '-y', NAME)
    run('livingproof', 'plugins', 'status', NAME, expected=1, env=offline)
    run('livingproof', 'capability', 'report', expected=1, env=offline)
    run('livingproof', '--version', env=offline)
    print('Installed plugin-management lifecycle passed:', mode, flush=True)


if __name__ == '__main__':
    assert not Path('/workspace/livingproof/src').exists(), 'Do not run in source environment'
    main(sys.argv[1])
