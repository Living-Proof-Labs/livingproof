<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Markdown manual comparison (preview only)

Both candidates render the same existing repository guides inside the manual:
README, plugin contract, development, verification, Pages operation, release
operation, working agreement and licensing. `tools/docs_comparison.py` stages
these files, rewrites their local link targets, and records original SHA-256
hashes. There is no second maintained copy of their prose. The explicit
allowlist and simple inline-link rewriter cover this corpus, not arbitrary
Markdown syntax. New guides or link syntax need corresponding validation.

Both candidates also render the same five installed-user scenario outcomes,
build provenance and terminal help captured by the existing packaged-container
verification. Native `sphinx-click` and the **working, unmodified `mkdocs-click`
Markdown extension** render the installed root and reporter command trees.
The builder installs the actual wheels offline into an isolated directory and
checks module origins; it does not import the product from the checkout.
The preview-only terminal-help conversion supplies a title and removes the old
orphan field. The existing live Sphinx artifact and Pages deployment are unchanged.

## Reproduce and browse

On the supported Linux build host with Docker, uv and Task:

```sh
task setup
task package
task images
task test:features
task docs
task docs:comparison:setup
uv run --locked --no-sync --group docs-comparison playwright install --with-deps chromium
task docs:compare
task test:docs:comparison
task docs:comparison:results
python3 -m http.server 8000 --bind 127.0.0.1 --directory artifacts/docs-comparison
```

Open <http://127.0.0.1:8000/sphinx/site/> and
<http://127.0.0.1:8000/zensical/site/>. An existing compatible Chromium can be
selected with `DOCS_BROWSER_EXECUTABLE=/path/to/chromium` for the test command.
The invalid preview canonical host is intentionally not a deployed address.

PR CI builds both previews on amd64, publishes individual test results and the
measured report in the job summary, and uploads
`markdown-comparison-0.0.0-amd64` with **14-day retention**. Extract its entire
tree, serve that directory over loopback HTTP, and use the same two URL paths.
The artifact includes both sites, source hashes, shared inputs, installed-command
contract, measurements, report and browser screenshots. Package regression
continues on both existing architectures; these preview browser tests cover only
Linux Chromium. Artifact expiry says nothing about the lifetime of the live manual.
Android `content://` file providers may not resolve sibling pages, assets or search;
double-click/offline multi-file browsing is not guaranteed.

## Measured results and effort

One local fresh-output build per candidate, Python 3.12.14, dependencies already
installed, on the same Linux amd64 worker. Shared staging and package preparation
are excluded. These are observations, not a benchmark or quality score:

| Candidate | Build seconds | Site bytes / files | Locked tool dependency closure |
| --- | ---: | ---: | ---: |
| Sphinx 8.2.3 + MyST 5.1.0 + Furo 2025.12.19 | 0.998 | 1,040,683 / 69 | 37 |
| Zensical 0.0.73 + mkdocs-click 0.9.0 | 0.420 | 923,548 / 28 | 12 |

Closure counts include platform alternatives and shared dependencies; exclude
application and browser-test dependencies. `measurements.json` records exact
versions, dependency names, current build times and source-line counts on every
run. Zensical installs a native binary wheel; Sphinx uses Python tooling. The
comparison dependency group is separate from runtime and the existing docs group.
Playwright and its browser are common validation costs, not site requirements.

Implementation added 192 lines of shared staging/build code and 68 lines of
reporting, plus 263 lines of browser/content fixtures and tests. Candidate-specific
configuration/reference templates total 21 lines for Sphinx and 38 for Zensical.
This is a bounded prototype with shared infrastructure, not a measured migration
estimate. No wall-clock installation benchmark was collected.

Concrete integration effort and maintenance differences:

- MyST renders existing Markdown directly. A generated hidden toctree supplies
  Furo navigation; native Sphinx Click needs an eight-line RST reference template.
- Zensical accepts `mkdocs-click` directly: no command generation adapter or
  arbitrary MkDocs plugin was needed. Absolute output/source paths caused a
  Zensical path invariant failure; relative paths in its generated YAML fixed it.
- Furo's default dark syntax colors failed the sampled code contrast check
  (2.84:1). Two supported configuration lines select `a11y-light`/`a11y-dark`.
  Zensical's sampled defaults passed. This is not a full accessibility audit.
- Both need the same local-link/provenance staging. Browser selectors differ:
  Furo uses a search results page, Zensical an interactive search dialog. These
  integration tests and pinned tools need maintenance as themes evolve.

## Observed usability and acceptance

All **24 comparison cases passed** locally with Playwright 1.64.1 and Chromium
154.0.8037.57. Existing 63 unit tests and five packaged-container scenarios also
passed. CI supplies independent, revision-linked results rather than treating
this recorded local snapshot as current CI evidence.

Actual browser interactions cover desktop and 390-pixel mobile navigation;
`plugins` and `manifest` search and result navigation; guide-to-guide links and
fragments; system light/dark preference changes and a three-step manual theme
cycle. Content checks resolve all generated local HTML links/assets/fragments,
compare all installed command paths/options, and check unchanged guide prose,
titled help and identical scenario/provenance data. Code samples are checked for
minimum 12-pixel font, 4.5:1 sampled text contrast and no page-width overflow.
Screenshots show the final state after manual cycling; filenames identify the
initial emulated system preference, not necessarily the final palette.

Both candidates meet this bounded acceptance. Furo exposes a conventional sidebar
and separate search page; Zensical uses a compact mobile header and search dialog.
Long code lines scroll inside their blocks. Command options are presented as
prose sections by Sphinx and compact code blocks by mkdocs-click. Those presentation
differences remain review choices, despite matching command content.

No actual Android-device, Firefox/Safari, keyboard/screen-reader audit, offline
search, or full documentation migration is claimed. The five scenario outcomes
retain their original scope; comparison tests do not increase product feature
coverage. Independent review and owner preference should decide adoption in a
later change. No runtime behavior, deployment target, permissions or domain changes
are part of this comparison.

## Upstream references

- [Zensical Markdown compatibility](https://zensical.org/docs/compatibility/markdown/)
  and [mkdocs-click](https://github.com/mkdocs/mkdocs-click)
- [Zensical system/manual color palettes](https://zensical.org/docs/setup/colors/)
- [MyST cross references](https://myst-parser.readthedocs.io/en/latest/syntax/cross-referencing.html)
- [Furo syntax colors](https://pradyunsg.me/furo/customisation/colors/)
- [WCAG text contrast criterion](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
