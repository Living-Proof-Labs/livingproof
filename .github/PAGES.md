<!-- SPDX-License-Identifier: Apache-2.0 -->
# Publish the verified documentation

The read-only `stable-manual` builder in `verify.yml` runs only after successful verification,
package/image finalization, immutable release publication and public consumption on
`main`. Pull requests and pre-publication package jobs build development previews;
they cannot deploy. No additional token or permission grant is introduced. The
builder uses only `contents: read` to check the release and build/test its manual.
The separate `documentation` deployment job retains only `pages: write` and
`id-token: write`. It never checks out or executes repository code, installs
dependencies, runs containers or starts a browser.

The release tag must resolve to the same commit as the verified workflow. Its
published stable release record must be immutable and match the selected version.
Inside the deployment concurrency lock, the job reads the public repository's
current `main` without credentials immediately before the deployment action. Stale runs skip delivery; missing, malformed
or unavailable refs fail closed. Release jobs are not cancelled.

The builder downloads the same run's versioned package images,
wheelhouse and scenario results. It rebuilds the manual from the checked release
tag and tested packages, checks browser behavior, and uploads
`released-manual-VERSION-amd64` for review. The root wheel hash must match the
GitHub SHA-256 digest of that wheel asset in the actual immutable release; a
same-run archive alone is insufficient. Missing release asset digests fail closed.

The builder uploads the Pages tar once as `github-pages-RUN_ID-BUILD_ATTEMPT`,
without overwrite, and emits its native artifact ID and tar SHA-256. Deployment
reads the artifact independently by exact native ID and exact attempt-qualified
name using the same-run artifact service. Each lookup permits at most one
workflow retry after failure, with a separate staging directory for every read.
Both successful readbacks must match the builder tar SHA-256 without extracting
the tar. Failure or mismatched bytes block deployment. The same verified name
is passed to the pinned Pages action. A deploy-only retry may
reuse the successful builder attempt; it cannot select an unrelated artifact. It does not regenerate
or replace scenario outcomes. All directly invoked Actions retain full commit pins.

Visible identity and `build.json` record the release tag, version, source commit,
verification run, wheel digest, reporter release and scenario source digest.
Candidate `0.0.0` output remains a preview; it cannot become a stable manual by
renaming an artifact. This is bounded verification, not an exhaustive coverage claim.
See [release operation](RELEASE.md#released-manual-delivery) for delivery-only retry
using the same existing release without creating another tag.

## One-time repository setup

Pages publication was explicitly approved. With the authorized Rivet account:

1. Open <https://github.com/Living-Proof-Labs/livingproof/settings/pages>.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Preserve the existing organization Pages domain setup; this renderer change
   requires no repository domain or DNS changes.
4. Inspect the `github-pages` environment and retain a deployment branch policy
   restricted to `main`; do not expand it to pull request branches.

The connected GitHub tools do not expose a Pages-settings or homepage write action.
The configure-pages Action requires Pages to be enabled already; automatic
`enablement` would need another token, which this workflow deliberately does not
request. No org-wide permission change is needed.

## Public URL and actual live verification

For downloaded artifacts, follow the [HTTP preview instructions](../docs/verification.md#preview-a-downloaded-manual).
Direct opening through Android `content://` providers may break sibling pages,
styles or search even after full extraction; do not treat it as a missing build.

For each independently reviewed update, use the deployment job's emitted
`page_url` as the authoritative URL. The verified canonical project URL is
`https://docs.livingprooflabs.com/livingproof/`. Verify the newly deployed revision
there after each renderer change. Then:

- Open the public URL in a browser, follow navigation to Command reference,
  Executable scenarios, and Build and verification provenance, and return home.
- Inspect root/plugin commands and their nested terminal help; confirm styles and
  scripts load under the `/livingproof/` project path.
- Use the site's search box for `plugins` and open a command-reference result.
  Repeat with `manifest` and open a scenario result. Checking a generated search index alone
  does not demonstrate working interactive search.
- Compare `build.json` and `feature-results.json` with the deployed run/commit.
- Record the URL, run, commit, browser results and any failure in the PR. Add the
  verified URL prominently at the top of README and as the repository About
  website/homepage when its verified destination changes. The current README and
  homepage already link the canonical manual.

The one-day `github-pages-RUN_ID-BUILD_ATTEMPT` artifact is deployment staging. The existing review
artifact has 14-day retention. Neither expiration removes the deployed manual:
the hosted site remains until replaced, unpublished, or Pages is disabled. This
setup is a single current manual, not permanent per-release archives or retention
of all historical test reports. A failed new build leaves the previous deployment.
