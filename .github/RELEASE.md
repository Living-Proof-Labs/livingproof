<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# First release dependency

Do not publish this candidate until the reporter entry-point metadata has a
verified release. Current v1.3.0 does not have it. Use that new explicit version
tag in a hosted consumption job: download its wheel and checksum, install it
alongside the umbrella wheel, and run the same real reporter smoke test with the
matching versioned example bundle. No branch or guessed future tag is a substitute.

After that job succeeds, use
`Living-Proof-Labs/collaboration-guidelines/.github/workflows/semantic-release.yml@v3.0.0`
with `draft-release: true`, dependent on verification of the same main commit.
Build the root wheel/source with the returned version (hatch-vcs supports
`SETUPTOOLS_SCM_PRETEND_VERSION`), verify the installed wheel, upload both assets
and SHA256SUMS to the draft, then publish. Follow the
[shared release procedure](https://github.com/Living-Proof-Labs/collaboration-guidelines/blob/v3.0.0/docs/releases.md).
Use only the existing repository workflow token; no permissions, token scopes,
package visibility, security settings or billing changes are authorized here.

The current workflow deliberately verifies candidates only. Hosted PR checks,
main verification, release publication and anonymous asset consumption are still
required evidence, not implied by local green tests.
