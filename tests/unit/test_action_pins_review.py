# SPDX-License-Identifier: Apache-2.0
"""Workflow Action SHA pins agree with their release tag comments (Vera review of #38).

Offline: every ``uses: owner/repo@<sha>`` is a full 40-hex SHA, and a tag comment, when
present, is ``vN`` or ``vN.N.N``. LIVINGPROOF_NETWORK=1: each SHA with a full ``vX.Y.Z``
comment is that tag's peeled commit. No SHA or tag is frozen, so later bumps still pass
when the comment and the commit agree.
"""

import json
import os
import re
import urllib.request
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
USES = re.compile(
    r"^\s*-?\s*uses:\s*(?P<action>[\w.-]+/[\w./-]+)@(?P<ref>\S+)(?:\s+#\s*(?P<tag>\S+))?\s*$",
    re.MULTILINE,
)
FULL_TAG = re.compile(r"v\d+\.\d+\.\d+")


def _pins():
    pins = []
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        for match in USES.finditer(path.read_text()):
            if "/.github/workflows/" in match["action"]:
                continue  # reusable workflows are pinned by release tag
            pins.append((path.name, match["action"], match["ref"], match["tag"]))
    return pins


def test_third_party_actions_are_sha_pinned_with_valid_tag_comments():
    pins = _pins()
    assert pins
    for name, action, ref, tag in pins:
        assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{name}: {action}@{ref}"
        if tag is not None:
            assert re.fullmatch(r"v\d+(?:\.\d+\.\d+)?", tag), f"{name}: {action} # {tag}"


@pytest.mark.skipif(not os.environ.get("LIVINGPROOF_NETWORK"), reason="set LIVINGPROOF_NETWORK=1")
def test_full_tag_comments_name_the_peeled_commit():
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    cache = {}
    for name, action, ref, tag in _pins():
        if tag is None or not FULL_TAG.fullmatch(tag):
            continue
        repo = "/".join(action.split("/")[:2])
        if (repo, tag) not in cache:
            request = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/commits/{tag}", headers=headers
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                cache[repo, tag] = json.load(response)["sha"]
        assert ref == cache[repo, tag], f"{name}: {action}@{ref} is not {tag} ({cache[repo, tag]})"
