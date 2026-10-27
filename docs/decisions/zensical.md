<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Use Zensical for the Markdown manual

On 2026-10-27 the owner preferred Zensical's modern Material-style experience
and delegated the final choice. After independent comparison, the project chose
Zensical over Sphinx + MyST + Furo. Both met the bounded acceptance; the decision
reflects the preferred navigation and presentation, not a claim that Sphinx
cannot provide dark mode or render Markdown.

The [comparison PR #14](https://github.com/Living-Proof-Labs/livingproof/pull/14)
retains the implementation, review and hosted evidence. Its immutable
[comparison report](https://github.com/Living-Proof-Labs/livingproof/blob/c84cfdfb8180cd874987255885eb6bf917e33d71/docs/comparison/README.md)
records methods, versions, adaptations and limitations. The dual builders are
not carried into production; this repository maintains one generator.

Both candidates rendered the same eight existing Markdown documents, installed
Click command tree, five scenario outcomes and provenance. All 24 local
comparison cases passed. A fresh-output local build with dependencies cached
measured Sphinx at 0.998 seconds / 1,040,683 bytes / 69 files, and Zensical at
0.420 seconds / 923,548 bytes / 28 files. Locked tool dependency closures were
37 and 12 respectively, including platform alternatives and shared dependencies,
excluding application/browser tools. These are single-run observations, not a
benchmark or quality score. Shared staging and package preparation were excluded.

`mkdocs-click` worked directly as a Markdown extension; no command-generation
adapter was necessary. Relative build/source paths avoided a Zensical path
invariant error. Furo needed accessible Pygments palettes after a sampled dark
code contrast failure. Both provided system preference, manual theme controls,
mobile navigation and working interactive search. Neither result establishes a
full accessibility audit or actual Android-device compatibility.

Production keeps canonical repository Markdown as the only guide prose source,
installed wheels as command truth, and packaged-container help and feature
outcomes as observable evidence. The link rewriter handles the explicitly listed
pages and current inline-link syntax; additions need corresponding checks.
Sphinx and the comparison harness are removed from normal dependencies and CI.

The existing main-only Pages publication, freshness check inside the deployment
lock, scoped permissions and 14-day review artifacts remain. Artifact expiration
does not remove the hosted manual. Independent adoption review and passing CI
precede merge; navigation/search must be verified through a normal browser at
[the canonical manual](https://docs.livingprooflabs.com/livingproof/) after deployment.
