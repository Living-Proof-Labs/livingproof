<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Publish the verified documentation

The `documentation` job in `verify.yml` publishes only after the existing package
verification (both native builds and installed consumers) and development checks
succeed on a push to `main`. Pull requests build documentation for review but
cannot deploy. No `pull_request_target`, privileged `workflow_run` handler, domain change, or additional token is used. The deployment job has only `pages: write`
and `id-token: write`; it does not check out or execute repository code.

Inside its deployment concurrency lock, the job reads the public repository's
current `main` ref without credentials. A stale run skips every artifact and
publication step, including when an older run is rerun after a newer deployment.
A missing, malformed or unavailable ref fails closed. No extra token permission
is needed. The job does not cancel release jobs.

For a current run, it downloads `documentation-0.0.0-amd64` from the same workflow run, packages its
existing HTML, and deploys it to the `github-pages` environment. All directly
invoked Actions are pinned to commit hashes. Native tar plus the pinned artifact
uploader follows the Pages artifact format without a composite uploader's floating
nested Action. Publication does not rebuild or replace measured scenario outcomes.

The manual's provenance page links the source commit and verification run and
records the root wheel digest, pinned reporter release and scenario source digest.
`feature-results.json` preserves the five scenario outcomes. Candidate package
version `0.0.0` is not a released package version. The hosted snapshot is not an
exhaustive coverage claim or a live verification service.

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

After the independently reviewed change merges, use the deployment job's emitted
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
  website/homepage. These final updates wait for actual URL verification.

The one-day `github-pages` artifact is deployment staging. The existing review
artifact has 14-day retention. Neither expiration removes the deployed manual:
the hosted site remains until replaced, unpublished, or Pages is disabled. This
setup is a single current manual, not permanent per-release archives or retention
of all historical test reports. A failed new build leaves the previous deployment.
