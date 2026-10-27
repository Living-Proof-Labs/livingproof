# SPDX-License-Identifier: Apache-2.0
"""Generate contributor reference and plain revision-aware manual navigation."""
import hashlib
from html import escape
import json
import posixpath
import subprocess


def task_reference(root, source):
    # Only this reviewed repository Taskfile; listing can evaluate dynamic variables.
    tasks = json.loads(subprocess.check_output(
        ['task', '--list', '--json'], cwd=root, text=True))['tasks']
    digest = hashlib.sha256((root / 'Taskfile.yml').read_bytes()).hexdigest()
    lines = ['# Contributor tasks', '',
             'Generated from the reviewed Taskfile using Task --list --json and --summary.', '',
             'Run ordinary tasks in the prepared development environment. Image, installed',
             'container and lifecycle tasks require a Linux Docker host. The dev:* tasks',
             'delegate to Docker Compose; do not recurse into them inside that container.', '',
             f'Taskfile SHA-256: `{digest}`', '']
    for task in tasks:
        name = task['name']
        summary = subprocess.check_output(['task', '--summary', name], cwd=root, text=True)
        lines += [f'## {name}', '', '```text', summary.rstrip(), '```', '']
    (source / 'tasks.md').write_text('\n'.join(lines))
    (source / 'task-reference.json').write_text(json.dumps(
        {'taskfile_sha256': digest, 'tasks': [t['name'] for t in tasks]}, indent=2) + '\n')


def add_identity(site):
    provenance = json.loads((site / 'build.json').read_text())
    revision = provenance['source_commit']
    label = f'Docs: development · {revision[:7]}'
    if provenance['source_dirty']:
        label += ' · local changes'
    for page in site.rglob('*.html'):
        html = page.read_text()
        if '</article>' not in html:
            continue
        prefix = posixpath.relpath('.', page.relative_to(site).parent.as_posix())
        footer = (f'<nav aria-label="Manual identity"><hr><p>'
                  '<a href="https://docs.livingprooflabs.com/">Documentation home</a> · '
                  f'<a href="{escape(provenance["source_url"])}">{escape(label)}</a> · '
                  '<a href="https://github.com/Living-Proof-Labs/livingproof">Source</a> · '
                  '<a href="https://github.com/Living-Proof-Labs/livingproof/issues">Help / report an issue</a> · '
                  f'<a href="{prefix}/license.html">License</a> · '
                  f'<a href="{prefix}/provenance.html">Version and source</a>'
                  '</p></nav>')
        page.write_text(html.replace('</article>', footer + '</article>'))
