# SPDX-License-Identifier: Apache-2.0
"""Build the public Markdown manual from installed commands and observed scenarios."""
import hashlib
import json
import os
import posixpath
import platform
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

import yaml

from feature_results import ROOT, results, scenarios
from docs_compatibility import preserve_urls

OUTPUT = ROOT / 'artifacts/docs'
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
    'docs/decisions/zensical.md': 'maintainers/docs-decision.md',
}
NAV = [
    ('Documentation home', 'https://docs.livingprooflabs.com/'),
    ('Start here', 'index.md'),
    ('Guides: plugins', 'guides/plugins.md'), ('Guides: development', 'guides/development.md'),
    ('Reference: commands', 'commands.md'), ('Reference: installed help', 'terminal-help.md'),
    ('Reference: tasks', 'tasks.md'), ('Scenarios and results', 'scenarios.md'),
    ('Verification', 'guides/verification.md'),
    ('Contribute', 'maintainers/working-agreement.md'), ('Version and source', 'provenance.md'),
    ('Help / report an issue', 'https://github.com/Living-Proof-Labs/livingproof/issues'),
    ('License', 'license.md'), ('Pages publication', 'maintainers/pages.md'),
    ('Release operation', 'maintainers/releases.md'),
    ('Documentation decision', 'maintainers/docs-decision.md'),
]


def task_reference():
    """Describe the reviewed Taskfile through native introspection, without running tasks."""
    tasks = json.loads(run(['task', '--list', '--json'], cwd=ROOT))['tasks']
    lines = ['# Contributor tasks', '',
             'Host wrappers `dev:build`, `dev:verify` and `dev:shell` invoke Docker. Other',
             'commands run in the prepared development environment; image, installed-test',
             'and documentation tasks additionally need the host Docker daemon.',
             'Do not invoke host Docker wrappers recursively inside the container.', '']
    for task in sorted(tasks, key=lambda item: item['name']):
        summary = run(['task', '--summary', task['name']], cwd=ROOT)
        lines += [f"## {task['name']}", '', '```text', summary.rstrip(), '```', '']
    return '\n'.join(lines)



def rewrite_links(text, source):
    """Rewrite only links to allowlisted local pages/assets, retaining prose and fragments."""
    targets = {**SOURCES, 'tests/features/installed.feature': 'scenarios.md',
               **{f'LICENSES/{p.name}': f'assets/{p.name}' for p in (ROOT / 'LICENSES').glob('*.txt')}}

    def replace(match):
        target = urlsplit(match[2])
        if target.netloc in ('living-proof-labs.github.io', 'docs.livingprooflabs.com') and target.path == '/livingproof/':
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
    common = OUTPUT / 'source'
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
    (common / 'tasks.md').write_text(task_reference())
    rows = results(ROOT / 'artifacts/feature-tests.xml')
    (common / 'feature-results.json').write_text(json.dumps(rows, indent=2) + '\n')
    assert len(rows) == len(scenarios()), 'Incomplete scenario mapping'
    lines = ['# Executable scenarios', '',
             'Each scenario maps to its pytest-bdd test and recorded JUnit outcome. These examples',
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
    provenance = installed_evidence(common)
    (common / 'provenance.md').write_text(
        '# Build and verification provenance\n\n'
        'This is the current development manual. Historical manuals are not maintained; '
        '[source release tags](https://github.com/Living-Proof-Labs/livingproof/tags) preserve past revisions.\n\n'
        'Software line coverage is not measured here. Scenario outcomes are a separate, bounded measure. '
        'No private security reporting route is documented; do not post sensitive reports to public issues.\n\n'
        'This manual records the candidate artifacts and scenario result snapshot. Skipped or missing results do not establish passing behavior.\n'
        'Package version 0.0.0 identifies a CI candidate, not a published release.\n\n'
        f"[Source revision]({provenance['source_url']})\n\n"
        + (f"[Verification run]({provenance['workflow_run']})\n\n"
           if provenance['workflow_run'] else 'Local snapshot; no hosted verification run.\n\n')
        + '```json\n' + json.dumps(provenance, indent=2) + '\n```\n\n'
        + '[Build record](build.json) | [Scenario outcomes](feature-results.json)\n')
    (OUTPUT / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for page in ('commands.md', 'search.md'):
        shutil.copyfile(ROOT / 'docs/site' / page, common / page)
    return common


def run(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs)


def installed_evidence(guide):
    wheel, = (ROOT / 'dist').glob('livingproof-*.whl')
    version = wheel.name.split('-')[1]
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}[platform.machine()]
    helps = ['# Installed terminal help', '']
    for suffix, commands in [('', [[], ['capability'], ['plugins'], ['completion']]),
                             ('-reporting', [['capability', 'report'],
                                            ['capability', 'report', 'validate'],
                                            ['capability', 'report', 'grade'],
                                            ['capability', 'report', 'render']])]:
        image = f'ghcr.io/living-proof-labs/livingproof:{version}{suffix}-{arch}'
        identity = run(['docker', 'image', 'inspect', '--format', '{{.Id}}', image]).strip()
        helps += [f'Installed image: `{image}` (`{identity}`).', '']
        for command in commands:
            help_text = run(['docker', 'run', '--rm', '--network=none', '--read-only',
                             image, *command, '--help'])
            helps += ['```text', '$ livingproof ' + ' '.join([*command, '--help'])]
            helps += help_text.splitlines()
            helps += ['```', '']
    (guide / 'terminal-help.md').write_text('\n'.join(helps))
    # Preserve a small, explicit provenance record alongside the public manual.
    commit = run(['git', 'rev-parse', 'HEAD'], cwd=ROOT).strip()
    repository = 'Living-Proof-Labs/livingproof'
    provenance = {
        'source_commit': commit,
        'source_dirty': bool(run(['git', 'status', '--porcelain'], cwd=ROOT).strip()),
        'source_url': f'https://github.com/{repository}/tree/{commit}',
        'workflow_run': (f'https://github.com/{repository}/actions/runs/'
                         + os.environ['GITHUB_RUN_ID'] if 'GITHUB_RUN_ID' in os.environ else None),
        'root_wheel': wheel.name,
        'root_wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
        'reporter_release': (ROOT / 'reporter-release.txt').read_text().strip(),
        'architecture': arch,
        'scenario_source_sha256': hashlib.sha256(
            (ROOT / 'tests/features/installed.feature').read_bytes()).hexdigest(),
        'result_scope': 'Five installed-user scenarios; not exhaustive feature coverage',
    }
    (guide / 'build.json').write_text(json.dumps(provenance, indent=2) + '\n')
    return provenance


def build():
    stage()
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
    config = yaml.safe_load((ROOT / 'docs/site/mkdocs.yml').read_text())
    config.update(repo_url='https://github.com/Living-Proof-Labs/livingproof',
                  repo_name='Source', docs_dir='source', site_dir='html',
                  nav=[{label: path} for label, path in NAV])
    config_file = OUTPUT / 'mkdocs.yml'
    config_file.write_text(yaml.safe_dump(config, sort_keys=False))
    subprocess.run([sys.executable, '-m', 'zensical', 'build', '--clean', '-f', str(config_file)],
                   env=env, cwd=OUTPUT, check=True)
    preserve_urls(OUTPUT / 'html')
    print(f'Preview {OUTPUT}/html over loopback HTTP; see docs/verification.md')


if __name__ == '__main__':
    build()
