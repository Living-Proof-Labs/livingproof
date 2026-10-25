<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Development and delivery

The Docker `development` target supplies Python 3.12, uv 0.12.23 and Task 3.54.0.
The devcontainer and GitHub CI reuse it. Dependency setup uses committed `uv.lock`.
No nested Docker or paid Codespace is required. On a Linux Docker/Compose host:

```sh
task dev:build
task dev:verify
```

In the prepared environment or devcontainer:

```sh
task setup
task verify
task package
task smoke
```

Task's Python commands are adapted from the Apache-2.0
[shared v3.0.0 template](https://github.com/Living-Proof-Labs/collaboration-guidelines/blob/v3.0.0/templates/python/Taskfile.yml).
A host may provide Python, uv and Task directly for the same tasks. Builds derive
versions from Git tags through hatch-vcs; untagged candidate builds use development versions, not release tags.
Consumers need only the wheel and dependencies, never Task or the source checkout.

`task smoke` installs the built wheel into a disposable virtual environment outside
the checkout, tests missing-plugin guidance, then installs a real fixture plugin
wheel to test metadata discovery. Set `REPORTER_WHEEL` and `REPORTER_BUNDLE` to a
plugin-enabled reporter wheel and portable fixture bundle to additionally validate,
grade and render with both installed commands and compare their output. This is
the required cross-repository consumption check before delivery; fixtures alone
are not proof that the real reporter integration works.

Open focused draft PRs first. Run hosted checks before routine tested merges.
CI runs the same development image and Task commands. `task integration` downloads
the exact reporter tag in `reporter-release.txt`, verifies its published wheel
checksum, obtains that tag's example bundle and runs clean installed consumption.
These downloads are development/release tooling, never runtime CLI behavior.
Update the pin deliberately through a PR after verifying the upstream release.

The shared semantic-release workflow at v3.0.0 runs after main verification and
creates a draft. A dependent job builds wheel/source assets using the returned
version, reruns installed consumption, attaches all assets and SHA256SUMS, then
publishes. Finally it anonymously downloads the public assets, verifies their
checksums and repeats installed consumption. Generated notes live on GitHub Releases;
do not commit generated version bumps or changelogs. No PyPI/container registry
publication or settings change is included. See [release operation](../.github/RELEASE.md).

Configured CI targets Linux; hosted checks and release asset consumption are
separate evidence from local checks. Other operating systems and live
editor/devcontainer launches remain unverified until exercised.
