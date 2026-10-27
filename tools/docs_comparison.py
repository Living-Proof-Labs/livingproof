# SPDX-License-Identifier: Apache-2.0
"""Stage one Markdown corpus and installed evidence for two non-deployed previews."""
import hashlib
from importlib import metadata
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit, urlunsplit

from docutils import nodes
from docutils.core import publish_doctree
import yaml

from feature_results import ROOT, scenarios

OUTPUT = ROOT / 'artifacts/docs-comparison'
# Explicit source allowlist: no source checkout is exposed as a web root.
SOURCES = {
    'README.md': 'index.md',
    'docs/plugins.md': 'guides/plugins.md',
    'docs/development.md': 'guides/development.md',
    'docs/verification.md': 'guides/verification.md',
    '.github/PAGES.md': 'maintainers/pages.md',
    '.github/RELEASE.md': 'maintainers/releases.md',
    'AGENTS.md': 'maintainers/working-agreement.md',
    'LICENSE.md': 'license.md',
}
NAV = [
    ('Home', 'index.md'), ('Command reference', 'commands.md'),
    ('Installed terminal help', 'terminal-help.md'), ('Executable scenarios', 'scenarios.md'),
    ('Build provenance', 'provenance.md'),
    ('Plugin contract', 'guides/plugins.md'), ('Development', 'guides/development.md'),
    ('Verification and previews', 'guides/verification.md'),
    ('Pages publication', 'maintainers/pages.md'), ('Release operation', 'maintainers/releases.md'),
    ('Working agreement', 'maintainers/working-agreement.md'), ('Licensing', 'license.md'),
]


def rewrite_links(text, source):
    """Rewrite only links to allowlisted local pages/assets, retaining prose and fragments."""
    targets = {**SOURCES, 'tests/features/installed.feature': 'scenarios.md',
               **{f'LICENSES/{p.name}': f'assets/{p.name}' for p in (ROOT / 'LICENSES').glob('*.txt')}}

    def replace(match):
        target = urlsplit(match[2])
        if target.netloc == 'living-proof-labs.github.io' and target.path == '/livingproof/':
            repo_path = 'README.md'
        elif target.netloc == 'github.com' and target.path.startswith(
                '/Living-Proof-Labs/livingproof/blob/main/'):
            repo_path = target.path.split('/blob/main/', 1)[1]
        elif target.scheme or target.netloc or not target.path:
            return match[0]
        else:
            repo_path = posixpath.normpath(posixpath.join(posixpath.dirname(source), target.path))
        if repo_path not in targets:
            return match[0]
        relative = posixpath.relpath(targets[repo_path], posixpath.dirname(SOURCES[source]) or '.')
        return f'[{match[1]}]({urlunsplit(("", "", relative, target.query, target.fragment))})'

    return re.sub(r'\[([^\]]+)\]\(([^\s)]+)\)', replace, text)


def stage():
    shutil.rmtree(OUTPUT, ignore_errors=True)
    common = OUTPUT / 'common'
    common.mkdir(parents=True)
    manifest = []
    for source, destination in SOURCES.items():
        content = (ROOT / source).read_text()
        target = common / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rewrite_links(content, source))
        manifest.append({'source': source, 'page': destination,
                         'sha256': hashlib.sha256(content.encode()).hexdigest()})
    assets = common / 'assets'
    assets.mkdir()
    for license_file in (ROOT / 'LICENSES').glob('*.txt'):
        shutil.copyfile(license_file, assets / license_file.name)
    shutil.copyfile(ROOT / 'tests/features/installed.feature', assets / 'installed.feature')
    for name in ('build.json', 'feature-results.json'):
        shutil.copyfile(ROOT / 'artifacts/docs/html' / name, common / name)
    rows = json.loads((common / 'feature-results.json').read_text())
    assert len(rows) == len(scenarios()), 'Incomplete scenario mapping'
    lines = ['# Executable scenarios', '',
             'The same installed-user snapshot is rendered in both previews. These examples',
             'are not exhaustive feature coverage; skipped/untested behavior is not a pass.', '',
             '[Raw feature source](assets/installed.feature) | [Outcome data](feature-results.json)', '']
    for scenario, row in zip(scenarios(), rows, strict=True):
        assert scenario['name'] == row['scenario']
        lines += [f"## {scenario['name']}", '', f"Result: **{row['status']}**", '',
                  f"Automated test: `{row['test']}`", '', '```gherkin',
                  f"Scenario: {scenario['name']}"]
        lines += [f"  {s['keyword']}{s['text']}" for s in scenario['steps']]
        lines += ['```', '']
    lines += ['Network installation/version flows, completion lifecycle, other platforms and',
              'independent manual review remain outside these five acceptance examples.', '']
    (common / 'scenarios.md').write_text('\n'.join(lines))
    provenance = json.loads((common / 'build.json').read_text())
    (common / 'provenance.md').write_text(
        '# Build and verification provenance\n\n'
        'Both previews use the same candidate artifacts and scenario result snapshot.\n'
        'Package version 0.0.0 identifies a CI candidate, not a published release.\n\n'
        f"[Source revision]({provenance['source_url']})\n\n"
        + (f"[Verification run]({provenance['workflow_run']})\n\n"
           if provenance['workflow_run'] else 'Local snapshot; no hosted verification run.\n\n')
        + '```json\n' + json.dumps(provenance, indent=2) + '\n```\n\n'
        + '[Build record](build.json) | [Scenario outcomes](feature-results.json)\n')
    # Reuse captured installed-container help without the orphan field or untitled page.
    tree = publish_doctree((ROOT / 'artifacts/docs/source/generated-help.rst').read_text())
    help_lines = ['# Installed terminal help', '']
    for node in tree.children:
        if isinstance(node, nodes.literal_block):
            help_lines += ['```text', node.astext(), '```', '']
        elif isinstance(node, nodes.paragraph):
            help_lines += [node.astext(), '']
    (common / 'terminal-help.md').write_text('\n'.join(help_lines))
    (OUTPUT / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return common


def build():
    common = stage()
    packages = OUTPUT / 'packages'
    wheel, = (ROOT / 'dist').glob('livingproof-*.whl')
    reporter = (ROOT / 'reporter-release.txt').read_text().strip()[1:]
    subprocess.run(['uv', 'pip', 'install', '--no-index', '--target', str(packages),
                    '--find-links', str(ROOT / 'dist/wheels'), str(wheel),
                    f'livingproof-capability-report=={reporter}'], check=True)
    env = {**os.environ, 'PYTHONPATH': str(packages)}
    probe = """import json
from pathlib import Path
import livingproof, livingproof_capability_report
from livingproof.cli import main
import click
root = Path.cwd() / 'packages'
for module in (livingproof, livingproof_capability_report):
    assert Path(module.__file__).is_relative_to(root), module.__file__
def walk(command, name):
    result = [{'command': name, 'options': [opt for p in command.params if isinstance(p, click.Option) for opt in p.opts]}]
    if isinstance(command, click.Group):
        ctx = click.Context(command)
        for child in command.list_commands(ctx):
            result += walk(command.get_command(ctx, child), name + ' ' + child)
    return result
print(json.dumps(walk(main, 'livingproof')))
"""
    commands = subprocess.check_output([sys.executable, '-c', probe], cwd=OUTPUT,
                                       env=env, text=True)
    (OUTPUT / 'installed-commands.json').write_text(commands)
    timings = {}
    for variant in ('sphinx', 'zensical'):
        source = OUTPUT / variant / 'source'
        shutil.copytree(common, source)
        site = OUTPUT / variant / 'site'
        if variant == 'sphinx':
            shutil.copyfile(ROOT / 'docs/comparison/sphinx-conf.py', source / 'conf.py')
            shutil.copyfile(ROOT / 'docs/comparison/commands.rst', source / 'commands.rst')
            with (source / 'index.md').open('a') as index:
                index.write('\n```{toctree}\n:hidden:\n\n')
                index.writelines(path.removesuffix('.md') + '\n' for _, path in NAV[1:])
                index.write('```\n')
            args = [sys.executable, '-m', 'sphinx', '-W', '--keep-going', '-E', '-a',
                    '-b', 'html', str(source), str(site)]
        else:
            shutil.copyfile(ROOT / 'docs/comparison/commands.md', source / 'commands.md')
            config = yaml.safe_load((ROOT / 'docs/comparison/mkdocs.yml').read_text())
            config.update(docs_dir="source", site_dir="site",
                          nav=[{label: path} for label, path in NAV])
            config_file = OUTPUT / variant / 'mkdocs.yml'
            config_file.write_text(yaml.safe_dump(config, sort_keys=False))
            args = [sys.executable, '-m', 'zensical', 'build', '--clean', '-f', str(config_file)]
        start = time.perf_counter()
        subprocess.run(args, env=env, cwd=OUTPUT / variant, check=True)
        timings[variant] = {'first_build_seconds': round(time.perf_counter() - start, 3),
                           'site_bytes': sum(p.stat().st_size for p in site.rglob('*') if p.is_file()),
                           'site_files': sum(p.is_file() for p in site.rglob('*'))}
    versions = {name: metadata.version(name) for name in (
        'sphinx', 'myst-parser', 'furo', 'zensical', 'mkdocs-click', 'sphinx-click', 'playwright')}
    (OUTPUT / 'measurements.json').write_text(json.dumps(
        {'builds': timings, 'versions': versions, 'python': sys.version,
         'conditions': 'One fresh output build per tool; installed dependencies cached; '
                       'shared staging/installed evidence preparation excluded.'}, indent=2) + '\n')
    print(json.dumps(timings, indent=2))


if __name__ == '__main__':
    build()
