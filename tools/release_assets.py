# SPDX-License-Identifier: Apache-2.0
"""Validate the public asset set without removing internal CI image archives."""
import hashlib
from pathlib import Path
import sys


def assemble(directory):
    directory = Path(directory)
    patterns = ('*.whl', 'livingproof-*.tar.gz', '*.deb', 'compatibility-*.json',
                'compatibility-*.md', 'registry-*.json', 'registry-*.md')
    assets = []
    for pattern in patterns:
        matches = sorted(directory.glob(pattern))
        if not matches:
            raise ValueError(f'Missing required release assets: {pattern}')
        assets.extend(matches)
    for arch in ('amd64', 'arm64'):
        for stem in ('compatibility', 'registry'):
            for suffix in ('json', 'md'):
                if not (directory / f'{stem}-{arch}.{suffix}').is_file():
                    raise ValueError(f'Missing {stem} evidence for {arch}')
    with (directory / 'SHA256SUMS').open('w') as stream:
        for path in sorted(set(assets)):
            with path.open('rb') as source:
                digest = hashlib.file_digest(source, 'sha256').hexdigest()
            stream.write(f'{digest}  {path.name}\n')
    return assets


if __name__ == '__main__':
    assemble(sys.argv[1])
