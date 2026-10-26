# SPDX-License-Identifier: Apache-2.0
"""Map executable feature scenarios to actual JUnit outcomes, never inferred coverage."""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from gherkin.parser import Parser
from pytest_bdd.scenario import make_python_name

ROOT = Path(__file__).resolve().parents[1]


def scenarios():
    feature = Parser().parse((ROOT / 'tests/features/installed.feature').read_text())['feature']
    return [child['scenario'] for child in feature['children']]


def results(report):
    cases = ET.parse(report).findall('.//testcase') if report.exists() else []
    expected = {'test_' + make_python_name(item['name']): item for item in scenarios()}
    if len(expected) != len(scenarios()):
        raise ValueError('Scenario names must produce unique pytest identities')
    observed = {}
    for case in cases:
        name = case.attrib['name']
        if name not in expected or name in observed:
            raise ValueError(f'Unexpected or duplicate scenario result: {name}')
        observed[name] = ('FAIL' if case.find('failure') is not None else
                          'ERROR' if case.find('error') is not None else
                          'SKIPPED' if case.find('skipped') is not None else 'PASS')
    return [{'scenario': item['name'], 'test': f'tests/features/test_journeys.py::{name}',
             'status': observed.get(name, 'NOT_RUN')} for name, item in expected.items()]


def markdown(rows):
    lines = ['## Installed-user scenario evidence', '',
             'Bounded examples; no percentage of total product feature coverage is claimed.', '',
             '| Scenario | Automated test | Result |', '| --- | --- | --- |']
    lines += [f"| {r['scenario']} | `{r['test']}` | {r['status']} |" for r in rows]
    lines += ['', 'Outside this pilot: installation/version network flows, grading/rendering parity,',
              'completion lifecycle, other operating systems and manual independent review.',
              'Existing regression suites cover some of these separately; see docs/verification.md.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, default=ROOT / 'artifacts/feature-tests.xml')
    args = parser.parse_args()
    rows = results(args.report)
    output = ROOT / 'artifacts/features'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
    (output / 'summary.md').write_text(markdown(rows))
    print(markdown(rows))
    return 0 if all(r['status'] == 'PASS' for r in rows) else 1


if __name__ == '__main__':
    sys.exit(main())
