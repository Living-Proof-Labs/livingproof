# SPDX-License-Identifier: Apache-2.0
"""Explicit, checksum-verified installation from known release repositories."""
import email
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
import zipfile

import click
from packaging.requirements import Requirement
from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version, InvalidVersion

REPORTER = 'livingproof-capability-report'
COMMON = 'livingproof-common'
REGISTRY = {REPORTER: ('Living-Proof-Labs/livingproof-capability-report', REPORTER),
            COMMON: ('Living-Proof-Labs/livingproof-common', 'python3-livingproof-common')}


def fail(message):
    raise click.ClickException(message)


class NoAuthenticatedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fail('Authenticated release API request redirected unexpectedly; no credentials forwarded.')


def request(url):
    headers = {'User-Agent': 'livingproof-plugin-manager',
               'Accept': 'application/vnd.github+json'}
    # Optional existing CI token is scoped to the API host, never release downloads.
    token = os.environ.get('LIVINGPROOF_GITHUB_TOKEN')
    open_request = urlopen
    if token and urlparse(url).netloc == 'api.github.com':
        headers['Authorization'] = 'Bearer ' + token
        open_request = build_opener(NoAuthenticatedRedirect()).open
    try:
        with open_request(Request(url, headers=headers),
                     timeout=30) as response:
            data = response.read(128 * 1024 * 1024 + 1)
            if len(data) > 128 * 1024 * 1024:
                fail('Release response exceeds the 128 MiB safety limit.')
            return data
    except HTTPError as exc:
        if exc.code in (403, 429):
            fail('GitHub API rate limit or access restriction. Retry later; no installation performed.')
        if exc.code == 404:
            fail('Release or asset not found. Use livingproof plugins versions ' + REPORTER + '.')
        fail(f'Release request failed (HTTP {exc.code}). Retry when the service is available.')
    except (URLError, TimeoutError, OSError) as exc:
        fail(f'Cannot download release data (offline, timeout or network failure): {exc}. Retry online.')


def api(name, suffix):
    try:
        return json.loads(request(f'https://api.github.com/repos/{REGISTRY[name][0]}/releases{suffix}'))
    except (ValueError, TypeError):
        fail('GitHub returned invalid release metadata. Retry later.')


def release(name, version):
    if version:
        version = version.removeprefix('v')
        if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[a-zA-Z0-9.+-]*)', version):
            fail('Version must be a release version such as 1.6.0, not a URL or repository name.')
        result = api(name, '/tags/' + quote('v' + version, safe=''))
    else:
        result = api(name, '/latest')
    if not isinstance(result, dict) or result.get('draft') or not result.get('tag_name'):
        fail('No published release found. Select a published version explicitly.')
    return result


def asset_url(name, asset):
    url = asset.get('browser_download_url', '')
    parsed = urlparse(url)
    prefix = '/' + REGISTRY[name][0] + '/releases/download/'
    if parsed.scheme != 'https' or parsed.netloc != 'github.com' or not parsed.path.startswith(prefix):
        fail('Release asset URL is outside the trusted repository.')
    filename = asset.get('name', '')
    if not filename or Path(filename).name != filename or '\\' in filename:
        fail('Release asset has an unsafe filename.')
    return url


def verified_asset(name, rel, asset, directory):
    sums = [a for a in rel.get('assets', []) if a.get('name') == 'SHA256SUMS']
    if len(sums) != 1:
        fail(f"Release {rel['tag_name']} must publish exactly one SHA256SUMS asset.")
    try:
        lines = request(asset_url(name, sums[0])).decode('utf-8').splitlines()
    except UnicodeError:
        fail('Published SHA256SUMS is not valid UTF-8.')
    expected = [parts[0].lower() for line in lines if len(parts := line.split()) == 2
                and parts[1].lstrip('*') == asset['name']]
    if len(expected) != 1 or not re.fullmatch('[0-9a-f]{64}', expected[0]):
        fail(f"Missing or ambiguous SHA256SUMS entry for {asset['name']}.")
    content = request(asset_url(name, asset))
    if hashlib.sha256(content).hexdigest() != expected[0]:
        fail(f"Checksum mismatch for {asset['name']}; nothing installed. Retry from a trusted release.")
    path = directory / asset['name']
    path.write_bytes(content)
    path.chmod(0o644)
    return path


def run(args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        fail(f"Cannot run {shlex.join(args)}: {getattr(exc, 'stderr', '') or exc}")


def context():
    """Inspect the running root distribution, never infer installation from OS alone."""
    root = metadata.distribution('livingproof')
    if sys.prefix != sys.base_prefix:
        return 'wheel'
    origin = Path(root.locate_file('livingproof/cli.py')).resolve()
    if shutil.which('dpkg-query'):
        owned = subprocess.run(['dpkg-query', '-S', str(origin)], capture_output=True, text=True)
        state = subprocess.run(['dpkg-query', '-W', '-f=${Status}', 'livingproof'],
                               capture_output=True, text=True)
        if (owned.returncode == 0 and owned.stdout.startswith('livingproof: ')
                and state.stdout == 'install ok installed'):
            return 'deb'
    if Path(sysconfig.get_path('stdlib'), 'EXTERNALLY-MANAGED').exists():
        fail('This Python is externally managed (PEP 668). Install livingproof in a virtual '
             'environment, or use its Debian package. System pip overrides are not supported.')
    # A non-venv wheel install can be ambiguous (user site, prefix, multiple interpreters).
    fail('Unsupported root installation context. Install livingproof in a virtual environment '
         'with python3 -m venv ENV and use ENV/bin/livingproof, or use the official Debian package.')


def select(name, rel, mode):
    candidates = []
    architecture = run(['dpkg', '--print-architecture']) if mode == 'deb' else None
    for asset in rel.get('assets', []):
        filename = asset.get('name', '')
        if mode == 'wheel' and filename.endswith('.whl'):
            try:
                dist, _, _, tags = parse_wheel_filename(filename)
            except ValueError:
                continue
            if dist == canonicalize_name(name) and tags.intersection(sys_tags()):
                candidates.append(asset)
        elif (mode == 'deb' and filename.startswith(REGISTRY[name][1] + '_')
              and filename.endswith('.deb')
              and filename.rsplit('_', 1)[-1][:-4] in ('all', architecture)):
            candidates.append(asset)
    if len(candidates) != 1:
        fail(f'{name} {rel["tag_name"]}: expected one compatible {mode} asset; found '
             f'{len(candidates)}. Choose another published version or supported environment.')
    return candidates[0]


def inspect(path, name, rel, mode):
    if mode == 'wheel':
        try:
            with zipfile.ZipFile(path) as archive:
                files = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
                if len(files) != 1:
                    fail('Wheel must contain one distribution metadata record.')
                info = email.message_from_bytes(archive.read(files[0]))
            if canonicalize_name(info['Name']) != canonicalize_name(name):
                fail('Wheel distribution does not match the requested plugin.')
            version = info['Version']
            from packaging.specifiers import SpecifierSet
            if info['Requires-Python'] and Version('.'.join(map(str, sys.version_info[:3]))) not in SpecifierSet(info['Requires-Python']):
                fail('Release does not support this Python version. Select a compatible release.')
            dependencies = [Requirement(r) for r in info.get_all('Requires-Dist', [])]
            common = [r for r in dependencies if r.name == COMMON and
                      (r.marker is None or r.marker.evaluate())]
            pin = None
            if common:
                specs = list(common[0].specifier)
                if len(common) != 1 or common[0].url or len(specs) != 1 or specs[0].operator != '==':
                    fail('Common dependency must declare one exact version.')
                pin = specs[0].version
        except (zipfile.BadZipFile, ValueError, TypeError, KeyError) as exc:
            fail(f'Invalid wheel metadata: {exc}')
    else:
        if run(['dpkg-deb', '-f', str(path), 'Package']) != REGISTRY[name][1]:
            fail('Debian package identity does not match the requested plugin.')
        arch = run(['dpkg-deb', '-f', str(path), 'Architecture'])
        if arch not in ('all', run(['dpkg', '--print-architecture'])):
            fail(f'Incompatible Debian architecture: {arch}.')
        version = run(['dpkg-deb', '-f', str(path), 'Version'])
        dependencies = run(['dpkg-deb', '-f', str(path), 'Depends'])
        pins = re.findall(r'python3-livingproof-common\s*\(=\s*([^ )]+)\)', dependencies)
        if 'python3-livingproof-common' in dependencies and len(pins) != 1:
            fail('Common dependency must declare one exact version.')
        pin = pins[0] if pins else None
    try:
        if Version(version) != Version(rel['tag_name'].removeprefix('v')):
            fail('Artifact version differs from its published release tag.')
    except InvalidVersion:
        fail('Release has an unsupported version format.')
    return version, pin


def installed(name):
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        fail(f'{name} is not installed. Run: livingproof plugins install {name}')
    entries = [e for e in metadata.entry_points(group='livingproof.capability.commands')
               if e.name == 'report']
    if len(entries) != 1 or not entries[0].dist or canonicalize_name(entries[0].dist.name) != name:
        fail(f'{name} package {dist.version} exists but its report entry point is missing or ambiguous.')
    try:
        if not isinstance(entries[0].load(), click.Command):
            raise TypeError('entry point is not a Click command')
    except Exception as exc:
        fail(f'{name} package {dist.version} is installed but unusable: {exc}')
    return dist.version


def install(name, version, dry_run=False):
    mode = context()
    with tempfile.TemporaryDirectory(prefix='livingproof-plugin-') as temporary:
        directory = Path(temporary)
        rel = release(name, version)
        plugin = verified_asset(name, rel, select(name, rel, mode), directory)
        selected, pin = inspect(plugin, name, rel, mode)
        paths = []
        if pin:
            # Do not let a plugin downgrade/replace common incompatibly with the root.
            for requirement in metadata.requires('livingproof') or []:
                req = Requirement(requirement)
                if req.name == COMMON and Version(pin) not in req.specifier:
                    fail(f'Plugin needs common {pin}, incompatible with root requirement {req}. '
                         'Choose a compatible plugin or upgrade livingproof first.')
            common_release = release(COMMON, pin)
            common = verified_asset(COMMON, common_release,
                                    select(COMMON, common_release, mode), directory)
            inspect(common, COMMON, common_release, mode)
            paths.append(common)
        paths.append(plugin)
        if mode == 'deb':
            command = ['apt-get', 'install', '--yes', '--allow-downgrades',
                       '--fix-broken', '--no-remove', *map(str, paths)]
            target = 'system Debian packages (requires an already privileged process)'
        else:
            command = [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                       '--no-input', '--only-binary=:all:', *map(str, paths)]
            target = f'Python environment {sys.prefix} (current user; no elevation)'
        click.echo(f'Install {name} {selected} into {target}.')
        for path in paths:
            click.echo(f'  Verified SHA256SUMS: {path.name}')
        click.echo('Operation: ' + shlex.join(command))
        if dry_run:
            click.echo('Dry run: verified plan only; no packages installed.')
            return
        if mode == 'deb':
            if os.geteuid() != 0:
                fail('Administrator privileges required. Ask an administrator to run '
                     f'livingproof plugins install {name} --version {selected} from the Debian '
                     'installation. This command never invokes sudo or handles passwords.')
            # apt's unprivileged downloader needs access to verified temporary files.
            directory.chmod(0o755)
        else:
            run([sys.executable, '-m', 'pip', '--version'])
        try:
            subprocess.run(command, check=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, **({"DEBIAN_FRONTEND": "noninteractive"}
                                               if mode == "deb" else {})})
        except (OSError, subprocess.CalledProcessError) as exc:
            fail(f'Package installation failed: {exc}. Package manager may have made partial '
                 'changes; inspect livingproof plugins status and retry the explicit install.')
        # Probe in a fresh interpreter so metadata/import caches cannot claim stale success.
        result = run([sys.executable, '-c',
                      'from livingproof.plugin_management import installed; '
                      f'print(installed({name!r}))'])
        if result != selected:
            fail(f'Installed version {result} differs from requested {selected}. Check environment paths.')
        click.echo(f'Installed {name} {result}. Try: livingproof capability report --help')


@click.group()
def plugins():
    """Explicitly manage known plugins. Help/status never install packages.

    Exit codes: 0 success; 1 absent/broken plugin, download or installation failure;
    2 invalid command/options. Install never prompts or elevates privileges.
    """


@plugins.command('install')
@click.argument('name', type=click.Choice([REPORTER]))
@click.option('--version', help='Exact published version (optional v prefix); default: latest stable.')
@click.option('--dry-run', is_flag=True, help='Download and verify the full plan without installing.')
def install_command(name, version, dry_run):
    """Install verified official release artifacts and their exact common dependency.

    Debian-owned root uses apt; virtual-environment root uses that Python's pip.
    Requires network access. An explicit version may upgrade or downgrade a plugin.
    Repeating an installed version lets the package manager reconcile dependencies.
    No automatic sudo, passwords, system pip override, or interactive prompt.
    """
    install(name, version, dry_run)


@plugins.command()
@click.argument('name', type=click.Choice([REPORTER]))
def status(name):
    """Print the usable installed package version locally; exit 1 when absent/broken."""
    click.echo(f'{name} {installed(name)}')


@plugins.command()
@click.argument('name', type=click.Choice([REPORTER]))
@click.option('--limit', default=20, show_default=True, type=click.IntRange(min=1),
              help='Maximum releases; automatically traverse API pages.')
def versions(name, limit):
    """List published tags and titles, including prereleases, newest API entries first.

    Read-only; requires network. Installation defaults to GitHub's latest stable
    release. Pin a listed version explicitly to select an older release/prerelease.
    """
    count, page = 0, 1
    while count < limit:
        records = api(name, f'?per_page=100&page={page}')
        if not isinstance(records, list):
            fail('GitHub returned invalid release-list metadata.')
        for record in records:
            if record.get('draft'):
                continue
            click.echo(f"{record['tag_name']}\t{record.get('name') or '(untitled)'}")
            count += 1
            if count == limit:
                return
        if len(records) < 100:
            return
        page += 1
