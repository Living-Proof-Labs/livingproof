# SPDX-License-Identifier: Apache-2.0
project = "Living Proof Labs command home"
extensions = ["sphinx_click"]
html_theme = "alabaster"
exclude_patterns = []
html_sidebars = {"**": ["about.html", "navigation.html", "searchbox.html"]}
html_theme_options = {
    "github_user": "Living-Proof-Labs",
    "github_repo": "livingproof",
    "github_button": True,
}

html_extra_path = ['build.json', 'feature-results.json']
