# SPDX-License-Identifier: Apache-2.0
"""Exercise the shipped CLI in disposable containers, never a source import."""
import os
from pathlib import Path
import subprocess
import sys

from packaging.version import InvalidVersion, Version

NAME = 'livingproof-capability-report'
# Issue #3: the default read is the newest 20. A wider read crosses one
# releases page (100) once that many are published, without raising the default.
DEFAULT_VERSION_LIMIT = 20
WIDER_VERSION_LIMIT = 101


def command(*args, expected=0, env=None):
    result = subprocess.run(args, capture_output=True, text=True, env=env)
    print('$', ' '.join(args), '\n', result.stdout, result.stderr, flush=True)
    assert result.returncode == expected, result
    return result


def run(*args, expected=0, env=None):
    result = command(*args, expected=expected, env=env)
    return result.stdout + result.stderr


def release_rows(stdout):
    rows = []
    for line in stdout.splitlines():
        tag, separator, title = line.partition('\t')
        assert separator and title and tag.startswith('v'), line
        try:
            version = Version(tag.removeprefix('v'))
        except InvalidVersion as exc:
            raise AssertionError(f'unparseable release tag {tag}') from exc
        rows.append((tag, version))
    return rows


def assert_recent_listing(default_stdout, wider_stdout):
    # Newest first, at most the default window, which is the head of a wider read.
    default = release_rows(default_stdout)
    wider = release_rows(wider_stdout)
    assert default and len(default) <= DEFAULT_VERSION_LIMIT
    assert all(earlier[1] > later[1] for earlier, later in zip(default, default[1:]))
    assert all(earlier[1] > later[1] for earlier, later in zip(wider, wider[1:]))
    default_tags = [tag for tag, _version in default]
    wider_tags = [tag for tag, _version in wider]
    assert len(wider_tags) >= len(default_tags)
    assert wider_tags[:len(default_tags)] == default_tags
    if len(wider_tags) > DEFAULT_VERSION_LIMIT:
        assert len(default_tags) == DEFAULT_VERSION_LIMIT
        assert wider_tags[DEFAULT_VERSION_LIMIT] not in default_tags
    else:
        assert wider_tags == default_tags


def main(mode):
    # An unreachable proxy proves local status/help/completion never require network.
    offline = {**os.environ, 'https_proxy': 'http://127.0.0.1:1',
               'HTTPS_PROXY': 'http://127.0.0.1:1'}
    run('livingproof', 'plugins', 'status', NAME, expected=1, env=offline)
    run('livingproof', 'capability', 'report', expected=1, env=offline)
    run('livingproof', '--help', env=offline)
    run('livingproof', '--version', env=offline)
    default = command('livingproof', 'plugins', 'versions', NAME)
    wider = command('livingproof', 'plugins', 'versions', NAME,
                    '--limit', str(WIDER_VERSION_LIMIT))
    assert_recent_listing(default.stdout, wider.stdout)
    plan = run('livingproof', 'plugins', 'install', NAME, '--version', '1.6.0', '--dry-run')
    assert 'common' in plan and 'SHA256SUMS' in plan
    assert ('system Debian' if mode == 'deb' else 'Python environment') in plan
    run('livingproof', 'plugins', 'status', NAME, expected=1, env=offline)
    if mode == 'deb':
        denied = run('runuser', '--preserve-environment', '-u', 'nobody', '--', 'livingproof', 'plugins', 'install',
                     NAME, '--version', '1.6.0', expected=1)
        assert 'Administrator privileges required' in denied
    # Explicit historical tags exercise downgrade and upgrade without using list order.
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
    run('livingproof', 'plugins', 'install', NAME, '--version', '1.4.0')
    assert '1.4.0' in run('livingproof', 'plugins', 'status', NAME, env=offline)
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
