# SPDX-License-Identifier: Apache-2.0
"""Publish measured preview outcomes, keeping test failures and missing evidence explicit."""
import json
from pathlib import Path
import sys
import tomllib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts/docs-comparison'


def main():
    metrics = json.loads((OUTPUT / 'measurements.json').read_text())
    cases = ET.parse(ROOT / 'artifacts/docs-comparison-tests.xml').findall('.//testcase')
    if not cases:
        raise ValueError('No comparison test results')
    lock = tomllib.loads((ROOT / 'uv.lock').read_text())
    packages = {p['name']: p for p in lock['package']}

    def closure(names):
        seen, pending = set(), list(names)
        while pending:
            name = pending.pop()
            if name not in seen:
                seen.add(name)
                pending.extend(d['name'] for d in packages[name].get('dependencies', []))
        return sorted(seen)

    dependencies = {'sphinx': closure(['sphinx', 'sphinx-click', 'myst-parser', 'furo']),
                    'zensical': closure(['zensical', 'mkdocs-click'])}
    metrics['locked_tool_dependencies'] = dependencies
    metrics['custom_code_lines'] = {
        path: len((ROOT / path).read_text().splitlines()) for path in (
            'tools/docs_comparison.py', 'tools/docs_comparison_report.py',
            'docs/comparison/sphinx-conf.py', 'docs/comparison/commands.rst',
            'docs/comparison/mkdocs.yml', 'docs/comparison/commands.md',
            'tests/docs/conftest.py', 'tests/docs/test_comparison.py')}
    (OUTPUT / 'measurements.json').write_text(json.dumps(metrics, indent=2) + '\n')
    lines = ['## Markdown documentation comparison', '',
             '| Preview | Fresh build, seconds | Site bytes | Site files | Locked tool packages |',
             '| --- | ---: | ---: | ---: | ---: |']
    for variant, result in metrics['builds'].items():
        lines.append(f"| {variant} | {result['first_build_seconds']} | {result['site_bytes']} | "
                     f"{result['site_files']} | {len(dependencies[variant])} |")
    lines += ['', metrics['conditions'], '',
              'Dependency counts include the lock’s platform alternatives and shared dependencies;',
              'they exclude application wheels and browser testing tools. They are not quality scores.', '',
              '| Automated browser/content case | Outcome |', '| --- | --- |']
    outcomes = []
    for case in cases:
        status = ('FAIL' if case.find('failure') is not None else
                  'ERROR' if case.find('error') is not None else
                  'SKIPPED' if case.find('skipped') is not None else 'PASS')
        outcomes.append(status)
        lines.append(f"| `{case.attrib['name']}` | {status} |")
    lines += ['', 'Both previews retain the same five installed-user scenario outcomes and provenance.',
              'These comparison checks do not expand product feature coverage or establish a full',
              'accessibility audit. Chromium/mobile viewport emulation is not Android-device testing.', '',
              'See docs/comparison/README.md for measured effort, adaptations and adoption limits.']
    report = '\n'.join(lines) + '\n'
    (OUTPUT / 'report.md').write_text(report)
    print(report)
    return 0 if all(status == 'PASS' for status in outcomes) else 1


if __name__ == '__main__':
    sys.exit(main())
