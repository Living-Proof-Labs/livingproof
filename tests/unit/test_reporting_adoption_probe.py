# SPDX-License-Identifier: Apache-2.0
"""Temporary adoption fixture; removed after hosted failure ingestion is verified."""


def test_intentional_failure_is_visible_in_github_checks():
    assert False, "Intentional reporting adoption probe: this failure must remain visible and block release"
