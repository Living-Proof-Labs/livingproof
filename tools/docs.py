# SPDX-License-Identifier: Apache-2.0
"""Build navigable Sphinx HTML from installed Click definitions and real scenarios."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from feature_results import ROOT, results, scenarios


def run(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs)


def build():
    output = ROOT / 'artifacts/docs'
    # This directory contains generated material only; prevent stale pages/results.
    shutil.rmtree(output, ignore_errors=True)
    guide = output / 'source'
    shutil.copytree(ROOT / 'docs/guide', guide)
    rows = results(ROOT / 'artifacts/feature-tests.xml')
    lines = ['Executable user journeys', '========================', '',
             'Each scenario maps to a pytest-bdd test and its most recent local JUnit outcome.',
             'NOT_RUN means no result was recorded; SKIPPED does not establish behavior.',
             'These examples are not exhaustive feature coverage. Independent manual review',
             'and existing regression suites are separate evidence.', '']
    for scenario, row in zip(scenarios(), rows, strict=True):
        name = scenario['name']
        lines += [name, '-' * len(name), '', f"Result: **{row['status']}**", '',
                  f"Automated test: ``{row['test']}``", '', '.. code-block:: gherkin', '',
                  f'   Scenario: {name}']
        lines += [f"     {s['keyword']}{s['text']}" for s in scenario['steps']]
        lines += ['']
    lines += ['Outside this pilot', '------------------', '',
              'Network installation and version discovery, completion lifecycle, grading and',
              'rendering parity remain in existing regression suites. Windows/macOS, all',
              'possible errors and independent manual review are not established by this report.', '']
    (guide / 'scenarios.rst').write_text('\n'.join(lines))
    wheel, = (ROOT / 'dist').glob('livingproof-*.whl')
    version = wheel.name.split('-')[1]
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}[platform.machine()]
    helps = []
    for suffix, commands in [('', [[], ['capability'], ['plugins'], ['completion']]),
                             ('-reporting', [['capability', 'report'],
                                            ['capability', 'report', 'validate'],
                                            ['capability', 'report', 'grade'],
                                            ['capability', 'report', 'render']])]:
        image = f'ghcr.io/living-proof-labs/livingproof:{version}{suffix}-{arch}'
        identity = run(['docker', 'image', 'inspect', '--format', '{{.Id}}', image]).strip()
        helps += [f'Installed image: ``{image}`` (``{identity}``).', '']
        for command in commands:
            help_text = run(['docker', 'run', '--rm', '--network=none', '--read-only',
                             image, *command, '--help'])
            helps += ['.. code-block:: text', '',
                      '   $ livingproof ' + ' '.join([*command, '--help'])]
            helps += ['   ' + line for line in help_text.splitlines()]
            helps += ['']
    (guide / 'generated-help.rst').write_text(':orphan:\n\n' + '\n'.join(helps))
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
    (guide / 'feature-results.json').write_text(json.dumps(rows, indent=2) + '\n')
    (guide / 'provenance.rst').write_text(
        'Build and verification provenance\n=================================\n\n'
        'This manual describes a verified candidate at the recorded source revision.\n'
        'Package version 0.0.0 is the CI candidate version, not a published release.\n'
        'Scenario results are a snapshot from that build, not a live service monitor.\n\n'
        f"`Source revision <{provenance['source_url']}>`_\n\n"
        + (f"`Verification run <{provenance['workflow_run']}>`_\n\n"
           if provenance['workflow_run'] else 'Local build; no hosted verification run recorded.\n\n')
        + '.. literalinclude:: build.json\n   :language: json\n\n'
        + '`Build record <build.json>`_ | `Scenario outcomes <feature-results.json>`_\n')
    # Install only the packaged command and runtime dependencies into an isolated
    # import directory; Sphinx uses the locked development tools, never src/.
    packages = output / 'packages'
    runtime_wheels = [wheel]
    for name in ('livingproof_common', 'click', 'packaging'):
        match, = (ROOT / 'dist/wheels').glob(name + '-*.whl')
        runtime_wheels.append(match)
    subprocess.run(['uv', 'pip', 'install', '--no-deps', '--no-index', '--target', str(packages),
                    *map(str, runtime_wheels)], check=True)
    env = {**os.environ, 'PYTHONPATH': str(packages)}
    origin = run([sys.executable, '-c', 'import livingproof; print(livingproof.__file__)'],
                 cwd=output, env=env).strip()
    assert Path(origin).is_relative_to(packages), origin
    subprocess.run([sys.executable, '-m', 'sphinx', '-W', '--keep-going', '-b', 'html',
                    str(guide), str(output / 'html')], cwd=output, env=env, check=True)
    print(f'Open {output}/html/index.html')


if __name__ == '__main__':
    build()
