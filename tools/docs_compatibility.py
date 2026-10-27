# SPDX-License-Identifier: Apache-2.0
"""Keep public Sphinx command bookmarks usable after the Zensical migration."""
import re

# Old option bookmarks land in the owning command section, where mkdocs-click
# renders options in a single code block rather than individually anchored rows.
COMMAND_ALIASES = {
    'root-command': 'livingproof',
    'capability-discovery': 'capability',
    'plugin-management': 'plugins',
    'livingproof-capability': 'capability',
    'livingproof-plugins': 'plugins',
    'livingproof-plugins-install': 'install_1',
    'livingproof-plugins-status': 'status_1',
    'livingproof-plugins-versions': 'versions',
    'livingproof-completion': 'completion',
    'livingproof-completion-bash': 'bash',
    'livingproof-completion-install': 'install',
    'livingproof-completion-status': 'status',
    'cmdoption-livingproof-version': 'livingproof',
    'cmdoption-livingproof-plugins-install-version': 'install_1',
    'cmdoption-livingproof-plugins-install-dry-run': 'install_1',
    'cmdoption-livingproof-plugins-install-arg-NAME': 'install_1',
    'cmdoption-livingproof-plugins-status-arg-NAME': 'status_1',
    'cmdoption-livingproof-plugins-versions-limit': 'versions',
    'cmdoption-livingproof-plugins-versions-arg-NAME': 'versions',
    'cmdoption-livingproof-completion-install-remove': 'install',
}


def preserve_urls(site):
    page = site / 'commands.html'
    html = page.read_text()
    for old, new in COMMAND_ALIASES.items():
        pattern = rf'(<h[2-6] id="{re.escape(new)}">)'
        html, count = re.subn(pattern, f'<span id="{old}"></span>\\1', html)
        if count != 1:
            raise ValueError(f'Expected one command heading for legacy anchor {old}: {new}')
    # This formerly included all captured help inline; retain a useful landing
    # and explicit link without duplicating help or adding it to search twice.
    end = '</article>'
    assert html.count(end) == 1
    html = html.replace(end, '<p id="installed-terminal-help">'
                        '<a href="terminal-help.html">Installed terminal help</a></p>' + end)
    page.write_text(html)
    for filename, old, current in (
            ('index.html', 'living-proof-labs-command-home', 'living-proof-labs'),
            ('scenarios.html', 'executable-user-journeys', 'executable-scenarios')):
        page = site / filename
        html, count = re.subn(rf'(<h1 id="{current}">)',
                              f'<span id="{old}"></span>\\1', page.read_text())
        assert count == 1, (filename, current)
        page.write_text(html)
    page = site / 'scenarios.html'
    html = page.read_text()
    scope = '<p>Network installation/version flows'
    assert html.count(scope) == 1
    page.write_text(html.replace(scope, '<p id="outside-this-pilot">Network installation/version flows'))
    # Static, same-directory redirect with an ordinary link for no-refresh clients.
    # Created after indexing so the obsolete URL is not a duplicate search result.
    (site / 'generated-help.html').write_text('''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Installed terminal help — moved</title>
<meta http-equiv="refresh" content="0; url=terminal-help.html">
<link rel="canonical" href="terminal-help.html">
<meta name="robots" content="noindex">
</head><body><p>Installed terminal help moved to
<a href="terminal-help.html">Installed terminal help</a>.</p></body></html>
''')
