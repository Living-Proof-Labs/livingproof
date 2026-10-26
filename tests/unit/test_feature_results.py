# SPDX-License-Identifier: Apache-2.0
"""Report completeness is separate from whether a publisher/build succeeds."""
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

spec = importlib.util.spec_from_file_location(
    'feature_results', Path(__file__).resolve().parents[2] / 'tools/feature_results.py')
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


def test_missing_results_are_not_passes(tmp_path):
    assert {r['status'] for r in reporter.results(tmp_path / 'missing.xml')} == {'NOT_RUN'}


def test_failed_skipped_and_incomplete_results_remain_visible(tmp_path):
    suite = ET.Element('testsuite')
    rows = reporter.results(tmp_path / 'missing.xml')
    for row, status in zip(rows, (None, 'failure', 'error', 'skipped')):
        case = ET.SubElement(suite, 'testcase', name=row['test'].split('::')[1])
        if status:
            ET.SubElement(case, status)
    path = tmp_path / 'results.xml'
    ET.ElementTree(suite).write(path)
    actual = reporter.results(path)
    assert [r['status'] for r in actual] == ['PASS', 'FAIL', 'ERROR', 'SKIPPED', 'NOT_RUN']
    assert '| FAIL |' in reporter.markdown(actual)


@pytest.mark.parametrize('content', ['not XML', '<testsuite><testcase name="other"/></testsuite>'])
def test_invalid_reports_fail(tmp_path, content):
    path = tmp_path / 'results.xml'
    path.write_text(content)
    with pytest.raises((ValueError, ET.ParseError)):
        reporter.results(path)
