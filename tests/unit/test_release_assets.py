# SPDX-License-Identifier: Apache-2.0
"""Routine releases keep packages/evidence and gate archive removal on registry tests."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location('release_assets', ROOT / 'tools/release_assets.py')
module = module_from_spec(spec)
spec.loader.exec_module(module)


def test_asset_checksums_preserve_packages_and_exclude_image_exports(tmp_path):
    expected = ['livingproof-1.0.0-py3-none-any.whl', 'livingproof-1.0.0.tar.gz',
                'livingproof_1.0.0_all.deb', 'livingproof_common-1.0.0-py3-none-any.whl',
                'python3-livingproof-common_1.0.0_all.deb']
    expected += [f'{stem}-{arch}.{suffix}' for stem in ('compatibility', 'registry')
                 for arch in ('amd64', 'arm64') for suffix in ('json', 'md')]
    for name in [*expected, 'image-amd64.tar', 'reporting-image-arm64.tar']:
        (tmp_path / name).write_text(name)
    assert {p.name for p in module.assemble(tmp_path)} == set(expected)
    checksums = (tmp_path / 'SHA256SUMS').read_text()
    assert all(f'  {name}\n' in checksums for name in expected)
    assert 'image-' not in checksums
    assert (tmp_path / 'image-amd64.tar').exists()  # internal archives are untouched
    (tmp_path / 'registry-arm64.md').unlink()
    with pytest.raises(ValueError, match='Missing registry evidence for arm64'):
        module.assemble(tmp_path)


def test_registry_verification_gates_publication_without_permission_expansion():
    jobs = yaml.safe_load((ROOT / '.github/workflows/verify.yml').read_text())['jobs']
    assert jobs['registry']['needs'] == ['release', 'assets']
    assert jobs['manifest']['needs'] == ['release', 'registry']
    assert jobs['registry-consumption']['needs'] == ['release', 'manifest']
    assert 'registry-consumption' in jobs['publish']['needs']
    steps = jobs['publish']['steps']
    upload, = [step['run'] for step in steps if 'gh release upload' in step.get('run', '')]
    assert 'release-assets/*.tar ' not in upload
    for asset in ('*.whl', '*.tar.gz', '*.deb', 'compatibility-*.json',
                  'compatibility-*.md', 'registry-*.json', 'registry-*.md', 'SHA256SUMS'):
        assert f'release-assets/{asset}' in upload
    for name, job in jobs.items():
        if name not in ('registry', 'manifest'):
            assert job.get('permissions', {}).get('packages') != 'write'
    packages = (ROOT / '.github/workflows/packages.yml').read_text()
    assert 'path: dist/' in packages
    assert 'retention-days: 14' in packages


@pytest.mark.parametrize("missing", ["livingproof_common-1.0.0-py3-none-any.whl",
                                     "python3-livingproof-common_1.0.0_all.deb"])
def test_common_packages_are_required_individually(tmp_path, missing):
    for name in ('livingproof-1.0.0-py3-none-any.whl', 'livingproof-1.0.0.tar.gz',
                 'livingproof_1.0.0_all.deb', 'livingproof_common-1.0.0-py3-none-any.whl',
                 'python3-livingproof-common_1.0.0_all.deb'):
        if name != missing:
            (tmp_path / name).touch()
    with pytest.raises(ValueError, match='required package'):
        module.assemble(tmp_path)
