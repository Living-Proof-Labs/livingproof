# SPDX-License-Identifier: Apache-2.0
project = 'Living Proof Labs — Sphinx comparison'
extensions = ['myst_parser', 'sphinx_click']
html_theme = 'furo'
source_suffix = {'.md': 'markdown', '.rst': 'restructuredtext'}
root_doc = 'index'
myst_heading_anchors = 6
html_extra_path = ['build.json', 'feature-results.json']
exclude_patterns = []
html_static_path = []
# Default native dark syntax colors failed the sampled normal-text contrast check.
pygments_style = 'a11y-light'
pygments_dark_style = 'a11y-dark'
