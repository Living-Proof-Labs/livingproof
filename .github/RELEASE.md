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
v4.0.0 creates a draft. Release-version packages are rebuilt and tested. The same
saved images are transferred through 14-day CI artifacts, pushed with the existing
workflow token, and combined into version-specific root/reporting manifests.
Fresh native amd64 and arm64 runners use empty Docker credential configurations
to pull immutable registry digests and exercise installed packages and entrypoints.
Publication depends on both registry-consumption jobs succeeding.

Only wheels, source archives, Debian packages, compatibility reports, registry
identity/run instructions and their checksums are attached to routine releases.
Release notes include the verified digests, platforms and copy/paste commands.
Public package consumption subsequently repeats the installed tests, fetching
containers through those digest references instead of public archive attachments.
Internal CI image archives remain available for exact build/test/publish transfers.
Offline image exports are an explicit consumer operation, not routine duplication.

Use only the existing workflow token. Do not change package visibility, Actions
access, security settings or grants to recover a failed registry step without
exact approval. Report the exact package/repository and failed operation. Registry
failure leaves the release draft unpublished; inspect the failed jobs and existing
registry tags before recovery. Do not delete existing releases, assets, manifests
or layers. Candidate artifact expiry does not authorize registry cleanup.

A failed prepublication build leaves a draft. Inspect it before recovery, reuse it,
and never retarget published tags or overwrite public assets. Generated release
notes stay on GitHub. Follow the
[shared release procedure](https://github.com/Living-Proof-Labs/collaboration-guidelines/blob/v4.0.0/docs/releases.md).
Old wheel/source-only releases remain unchanged. No PyPI publication is configured.
