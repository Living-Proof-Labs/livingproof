<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Release operation

Native amd64 and arm64 CI builds wheel/source, pure-Python `all.deb`, and root-only
and explicit reporting container variants. The reporter stays independently
versioned at `reporter-release.txt`; builds verify its published wheel, Debian
package and native wheelhouse checksums before use. No reporting implementation
is copied into the umbrella.

The same candidate Debian asset built on amd64 is consumed on both CPUs with the
published reporter `.deb` in Debian 12, Debian 13 and Ubuntu 24.04. Pytest cases
are ingested into GitHub Checks; the actual devcontainer lifecycle is a separate
gate. Verification must pass before the shared semantic-release workflow at
v4.0.0 creates a draft. Release-version packages are rebuilt and tested, all assets
and generated compatibility evidence are attached, and then the draft is published.

Fresh native runners anonymously download the published package and image assets,
verify checksums, load saved images, and repeat installed-consumer tests. Only then
are the same saved images pushed to the version-specific registry tags and combined
into root/reporting multi-architecture manifests. Separate fresh native tests
verify anonymous registry pulls. Saved images provide a release distribution even
if registry access is blocked; do not call an unverified registry tag available.

Use only the existing workflow token. Do not change package visibility, Actions
access, security settings or grants to recover a failed registry step without
exact approval. Report the exact package/repository and failed operation. Successful
asset publication is a real release even if a subsequent registry step fails;
report that distinction and retry only the failed jobs after the blocker is resolved.

A failed prepublication build leaves a draft. Inspect it before recovery, reuse it,
and never retarget published tags or overwrite public assets. Generated release
notes stay on GitHub. Follow the
[shared release procedure](https://github.com/Living-Proof-Labs/collaboration-guidelines/blob/v4.0.0/docs/releases.md).
Old wheel/source-only releases remain unchanged. No PyPI publication is configured.
