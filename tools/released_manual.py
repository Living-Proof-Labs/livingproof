# SPDX-License-Identifier: Apache-2.0
"""Fail closed on release identity; this module never creates or changes releases."""
import hashlib
import json
import os
import re
import subprocess
import sys


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def source(version, tag, commit):
    if not tag:
        if version != '0.0.0':
            raise ValueError('Versioned packages require an existing release tag')
        return
    if not re.fullmatch(r'[1-9]\d*\.\d+\.\d+|0\.[1-9]\d*\.\d+|0\.0\.[1-9]\d*', version):
        raise ValueError('A nonzero stable release version is required')
    if tag != f'v{version}' or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Release tag/version/commit mismatch')
    if git('rev-parse', 'HEAD') != commit or git('rev-parse', f'refs/tags/{tag}^{{commit}}') != commit:
        raise ValueError('Release tag must identify the exact verified checkout')


def published(record, version, tag, commit):
    source(version, tag, commit)
    if not tag or record.get('tag_name') != tag:
        raise ValueError('Missing or mismatched release')
    if record.get('draft') is not False or record.get('prerelease') is not False:
        raise ValueError('Release is not a published stable release')
    if record.get('immutable') is not True or not record.get('published_at'):
        raise ValueError('Release is not published and immutable')


def release_record(tag):
    repository = os.environ['GITHUB_REPOSITORY']
    return json.loads(subprocess.check_output(
        ['gh', 'api', f'repos/{repository}/releases/tags/{tag}'], text=True))


def released_wheel_digest(record, wheel):
    if wheel is None:
        raise ValueError('Released manual requires the actual root wheel')
    assets = [asset for asset in record.get('assets', []) if asset.get('name') == wheel.name]
    if len(assets) != 1:
        raise ValueError('Expected one root wheel asset in the immutable release')
    digest = assets[0].get('digest', '')
    actual = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if digest != f'sha256:{actual}':
        raise ValueError('Root wheel differs from its immutable release asset digest')
    return actual


def identity(version, commit, wheel=None):
    if os.environ.get('MANUAL_CHANNEL', 'preview') != 'release':
        return {'channel': 'preview', 'version': version, 'release_tag': None}
    tag = os.environ['RELEASE_TAG']
    if version != os.environ['RELEASE_VERSION'] or commit != os.environ['GITHUB_SHA']:
        raise ValueError('Manual package and verified release identity differ')
    record = release_record(tag)
    published(record, version, tag, commit)
    if git('status', '--porcelain'):
        raise ValueError('Released manual requires a clean source checkout')
    digest = released_wheel_digest(record, wheel)
    return {'channel': 'release', 'version': version, 'release_tag': tag,
            'release_wheel_sha256': digest}


if __name__ == '__main__':
    version = os.environ['RELEASE_VERSION']
    tag = os.environ.get('RELEASE_TAG', '')
    commit = os.environ.get('GITHUB_SHA', '')
    source(version, tag, commit)
    if sys.argv[1] == 'published':
        published(release_record(tag), version, tag, commit)
    elif sys.argv[1] != 'source':
        raise ValueError('Expected source or published')
