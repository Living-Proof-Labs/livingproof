# SPDX-License-Identifier: Apache-2.0
"""Observable production-manual checks; HTTP availability alone is not browser acceptance."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links, self.ids, self.text = [], set(), []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        self.links.extend(attrs[key] for key in ('href', 'src') if key in attrs)

    def handle_data(self, data):
        self.text.append(data)


def test_repository_markdown_is_single_source(output):
    manifest = json.loads((output / 'source-manifest.json').read_text())
    for item in manifest:
        original = (ROOT / item['source']).read_text()
        assert hashlib.sha256(original.encode()).hexdigest() == item['sha256']
        common = (output / 'source' / item['page']).read_text()
        # Body is unchanged: only link targets are rewritten for local rendering.
        def strip_targets(s):
            return re.sub(r'\[([^\]]+)\]\([^\s)]+\)', r'[\1]', s)
        assert strip_targets(common) == strip_targets(original)


def test_recorded_outcomes_and_provenance(output):
    import sys
    sys.path.insert(0, str(ROOT / 'tools'))
    from feature_results import results
    rows = json.loads((output / 'html/feature-results.json').read_text())
    assert rows == results(ROOT / 'artifacts/feature-tests.xml')
    build = json.loads((output / 'html/build.json').read_text())
    wheel = ROOT / 'dist' / build['root_wheel']
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == build['root_wheel_sha256']
    assert build['scenario_source_sha256'] == hashlib.sha256(
        (ROOT / 'tests/features/installed.feature').read_bytes()).hexdigest()
    assert build['reporter_release'] == (ROOT / 'reporter-release.txt').read_text().strip()


def test_internal_pages_assets_and_fragments(output):
    root = output / 'html'
    docs = {p.resolve(): Document(p.read_text()) for p in root.rglob('*.html')}
    problems = []
    for path, doc in docs.items():
        for link in doc.links:
            parts = urlsplit(link)
            if parts.scheme or parts.netloc:
                continue
            if parts.path.startswith('/'):
                prefix = '/livingproof/'
                assert parts.path.startswith(prefix), link
                target = (root / unquote(parts.path.removeprefix(prefix))).resolve()
            else:
                target = (path.parent / unquote(parts.path)).resolve() if parts.path else path
            if target.is_dir():
                target /= 'index.html'
            if not target.exists():
                problems.append(f'{path.relative_to(root)}: missing {link}')
            elif parts.fragment and target in docs and unquote(parts.fragment) not in docs[target].ids:
                problems.append(f'{path.relative_to(root)}: missing anchor {link}')
    assert not problems, '\n'.join(problems)


def test_installed_command_contract_rendered(output):
    document = Document((output / 'html/commands.html').read_text())
    html = (output / 'html/commands.html').read_text()
    headings = list(re.finditer(r'<h([2-6]) id="([^"]+)">([^<]+)', html))
    hierarchy, sections, anchors = {}, {}, {}
    for index, heading in enumerate(headings):
        level = int(heading[1])
        hierarchy = {depth: name for depth, name in hierarchy.items() if depth < level}
        hierarchy[level] = heading[3]
        name = ' '.join(hierarchy[depth] for depth in sorted(hierarchy))
        end = headings[index + 1].start() if index + 1 < len(headings) else len(html)
        sections[name] = ' '.join(Document(html[heading.end():end]).text)
        anchors[name] = heading[2]
    contract = json.loads((output / 'installed-commands.json').read_text())
    assert set(sections) == {row['command'] for row in contract}
    assert len(set(anchors.values())) == len(anchors)
    for command in contract:
        text = sections[command['command']]
        assert command['command'] in text, command
        for option in command['options']:
            assert re.search(r'(?<![\w-])' + re.escape(option) + r'(?![\w-])', text), command
    text = ' '.join(document.text)
    assert '::: mkdocs-click' not in text
    help_doc = Document((output / 'html/terminal-help.html').read_text())
    assert 'Installed terminal help' in ' '.join(help_doc.text)
    assert ':orphan:' not in ' '.join(help_doc.text)
    assert not (output / 'html/generated-help.html').exists()


def article(page):
    return page.locator('.md-content__inner')


def contrast(foreground, background):
    def luminance(color):
        rgb = [float(n) / 255 for n in re.findall(r'[\d.]+', color)[:3]]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
                  for v in rgb]
        return sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722)))
    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def surface(page):
    return page.evaluate('''() => {
        const e = document.body;
        const s = getComputedStyle(e);
        return {background: s.backgroundColor, color: s.color};
    }''')


@pytest.mark.parametrize('width', [1280, 390], ids=['desktop', 'mobile'])
def test_navigation_and_internal_guide_links(browser, server, output, width):
    context = browser.new_context(viewport={'width': width, 'height': 844})
    context.set_default_timeout(5000)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(f'{server}/')
    if width == 390:
        page.locator('label.md-header__button[for="__drawer"]:visible').first.click()
    page.get_by_role('link', name='Command reference', exact=True).first.click()
    expect(article(page)).to_contain_text('livingproof capability report')
    expect(article(page)).to_contain_text('validate')
    page.goto(f'{server}/guides/development.html')
    article(page).get_by_role('link', name='installed-user pilot and generated documentation').click()
    expect(page).to_have_url(re.compile('/guides/verification.html$'))
    article(page).get_by_role('link', name='Pages publication and live verification').click()
    expect(page).to_have_url(re.compile('/maintainers/pages.html$'))
    article(page).get_by_role('link', name='HTTP preview instructions').click()
    expect(page).to_have_url(re.compile('/guides/verification.html#preview-a-downloaded-manual$'))
    assert page.locator('#preview-a-downloaded-manual').count() == 1
    screenshot = output / 'screenshots' / f'{width}-navigation.png'
    screenshot.parent.mkdir(exist_ok=True)
    page.screenshot(path=str(screenshot), full_page=False)
    assert not errors, errors
    context.close()


@pytest.mark.parametrize('width', [1280, 390], ids=['desktop', 'mobile'])
@pytest.mark.parametrize('term,expected_path', [('plugins', 'commands.html'),
                                               ('manifest', 'scenarios.html')])
def test_interactive_search_and_result_navigation(browser, server, term, expected_path, width):
    context = browser.new_context(viewport={"width": width, "height": 844})
    context.set_default_timeout(5000)
    page = context.new_page()
    page.goto(f'{server}/')
    if width == 390:
        page.locator('label[for="__search"]:visible').first.click()
    else:
        page.get_by_role('button', name='Search', exact=False).first.click()
    page.get_by_placeholder('Search', exact=True).fill(term)
    result = page.locator(f'dialog a[href*="{expected_path}"]').first
    expect(result).to_be_visible(timeout=15000)
    result.click()
    expect(page).to_have_url(re.compile(re.escape(expected_path)))
    expect(article(page)).to_contain_text(term, ignore_case=True)
    context.close()


def readable_code(page):
    # Code must be visible and stay inside a horizontal scroll container on mobile.
    code = article(page).locator('pre').first
    expect(code).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    metrics = code.evaluate('''e => {
        let node=e, background;
        while(node) {
            const c=getComputedStyle(node).backgroundColor;
            if(c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') {background=c;break;}
            node=node.parentElement;
        }
        return {color:getComputedStyle(e).color, background, font:getComputedStyle(e).fontSize,
                tokens: [...e.querySelectorAll('span')].map(x=>getComputedStyle(x).color)};
    }''')
    assert float(metrics['font'].removesuffix('px')) >= 12
    ratio = min(contrast(color, metrics['background'])
                for color in [metrics['color'], *metrics['tokens']])
    assert ratio >= 4.5, (ratio, metrics)
    assert contrast(surface(page)['color'], surface(page)['background']) >= 4.5
    return ratio, metrics


@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_system_manual_theme_and_mobile_code(browser, server, output, mode):
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme=mode)
    context.set_default_timeout(5000)
    page = context.new_page()
    page.goto(f'{server}/commands.html')
    page.wait_for_timeout(300)  # Allow the initial media-query theme listener to run.
    original = surface(page)
    readable_code(page)
    rgb = [int(n) for n in re.findall(r'\d+', original['background'])[:3]]
    assert bool(sum(rgb) < 384) == (mode == 'dark'), original
    other = 'dark' if mode == 'light' else 'light'
    page.emulate_media(color_scheme=other)
    page.wait_for_function('(old) => getComputedStyle(document.body).backgroundColor !== old',
                           arg=original['background'])
    changed = surface(page)
    # Cycle the exposed theme control until explicit light and dark are both observed.
    seen = set()
    for _ in range(3):
        page.locator('[data-md-component="palette"] label:visible').first.click()
        page.wait_for_timeout(150)
        seen.add(surface(page)['background'])
        readable_code(page)
    assert len(seen) >= 2, (original, changed, seen)
    ratio, metrics = readable_code(page)
    screenshot = output / 'screenshots' / f'{mode}-mobile-code.png'
    screenshot.parent.mkdir(exist_ok=True)
    page.screenshot(path=str(screenshot))
    print(f'system={mode}; surfaces={original, changed}; code={metrics}; sampled contrast={ratio:.2f}:1')
    context.close()


def test_command_fragments_and_assets_in_browser(browser, server):
    page = browser.new_page()
    failures = []
    page.on('response', lambda response: failures.append(response.url) if response.status >= 400 else None)
    page.on('requestfailed', lambda request: failures.append(request.url))
    for anchor, heading, usage in [
            ('install', 'install', 'livingproof completion install'),
            ('install_1', 'install', 'livingproof plugins install'),
            ('status', 'status', 'livingproof completion status'),
            ('status_1', 'status', 'livingproof plugins status'),
            ('validate', 'validate', 'livingproof capability report validate')]:
        page.goto(f'{server}/commands.html#{anchor}')
        expect(page.locator(f'#{anchor}')).to_contain_text(heading)
        expect(article(page)).to_contain_text(usage)
        assert page.locator(f'#{anchor}').evaluate('e => Math.abs(e.getBoundingClientRect().top) < innerHeight')
    assert not failures, failures
    page.close()


def test_canonical_url_and_internal_home_link(output):
    html = (output / 'html/index.html').read_text()
    assert '<link rel="canonical" href="https://docs.livingprooflabs.com/livingproof/index.html">' in html
    match = re.search(r'<a href="([^"]+)">Documentation: command reference', html)
    assert match and match[1] in ('.', './', 'index.html'), match
