<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Release operation

The verification workflow tests the same triggering commit using the shared Docker
and Task environment, including a real installed reporter from the published tag
in `reporter-release.txt`. The reporter wheel must match its published SHA256SUMS.

On main only, verification gates
`Living-Proof-Labs/collaboration-guidelines/.github/workflows/semantic-release.yml@v3.0.0`
with `draft-release: true`. The dependent publication job builds the returned version,
tests wheel/source and reporter consumption, attaches all assets/checksums, then
publishes the draft. An anonymous download and repeated installed smoke verify
what consumers receive. Release notes live in GitHub Releases.

A failed build leaves a draft: inspect it and its assets before recovery, reuse
that draft, and never retarget tags or overwrite immutable public assets. A failure
after publication leaves a real release with incomplete verification; report that
state explicitly. Follow the
[shared release procedure](https://github.com/Living-Proof-Labs/collaboration-guidelines/blob/v3.0.0/docs/releases.md).

Only the existing repository workflow token is used for release writes. No token
grants, repository security settings, package visibility or billing changes belong
in this workflow. There is no PyPI or container registry publication.
