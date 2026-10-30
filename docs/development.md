<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Development and installed-consumer verification

The Docker development target supplies Python 3.12, uv 0.12.23, Task 3.54.0 and
native Debian tooling. The devcontainer and CI reuse it; project dependencies
come from committed `uv.lock`. No paid Codespace, nested Docker or mounted Docker
socket is needed to edit, test or run the CLI inside the development container.

## Start a development environment

Open the repository in its devcontainer. The standard workspace mount is used,
matching Codespaces' `/workspaces` layout. `postCreateCommand` runs `task setup`
and `livingproof --help`. The development environment is on PATH, so the command
works directly in an interactive terminal. It is separate from system Python.

```sh
livingproof --help
task verify
livingproof capability report --help  # useful missing-plugin guidance
```

Reporter installation is an explicit opt-in:

```sh
task plugin:install
livingproof capability report --help
livingproof capability report validate artifacts/reporter/source/examples/bundle/manifest.json
```

This contributor task downloads and checksum-verifies the reporter release pinned
in `reporter-release.txt`, then installs its wheel into the same development
environment. It never runs implicitly when the CLI starts. `task setup` locks
root/tool dependencies while retaining
explicitly installed plugins (`uv sync --inexact`); rebuilding a fresh container
requires opting into the plugin again. These are development instructions;
Debian consumers install both `.deb` files with apt as described in the README.

Completion is optional. Generate and source the Bash script explicitly:

```sh
_LIVINGPROOF_COMPLETE=bash_source livingproof > /tmp/livingproof-completion.bash
. /tmp/livingproof-completion.bash
```

The previous v1.0.0 configuration installed into `/tmp/livingproof-venv` without
adding its bin directory to PATH. The current configuration uses a dedicated
`/opt/livingproof-dev/venv` on PATH and verifies direct command access in the
lifecycle. No browser screenshot by itself establishes a container build failure;
inspect the actual creation log and `command -v livingproof` when diagnosing startup.

## Common commands

On a Linux Docker/Compose host, `task dev:build` and `task dev:verify` use the same
Docker target. Inside a prepared environment use `task setup` and `task verify`
directly. Unit tests collect only `tests/unit`, never tests in downloaded plugin sources.

`task package` builds wheel/source and an `Architecture: all` Debian package using
PyPA installer and native `dpkg-deb`; no custom wheel installer or vendored virtual
environment is shipped. `task images` is a host/CI command requiring Docker: it
reuses the reporter's checksum-verified, versioned native wheelhouse to build
root-only and reporting variants without network access during image installation.
Version selection comes from Git tags or `SETUPTOOLS_SCM_PRETEND_VERSION` in release CI.

```sh
task setup
task verify
task package
task images
task test:installed
```

The installed suite exercises native distribution containers with only package
assets, fixture data and a test harness mounted. Application checkouts are absent.
It tests root-alone guidance, explicit reporter installation, policy grades,
terminal/JSON/HTML/CSV parity, errors, completion, uninstall independence and
package metadata. CI repeats consumption using the **same amd64-built all.deb**
on both native CPU architectures, then repeats against public release downloads.

## Actual devcontainer lifecycle

Install the reference `@devcontainers/cli@0.89.0` in the host tool environment, then:

```sh
task test:devcontainer
```

The test calls `devcontainer up`, runs the configured creation hook, executes
interactive commands, opts into the reporter, produces a report, restarts the
container and checks commands/completion again. It removes its own test container.
This verifies the actual configuration lifecycle, not a live browser editor session.
Host proxy/CA overrides, if needed locally, stay outside the committed config.
For a Debian mirror override, export `APT_MIRROR` (an origin such as
`https://cloudfront.debian.net`) before `task dev:build` or `devcontainer up`.
`DEVCONTAINER_CONFIG` selects such a local override; it must not change project
commands or silently skip lifecycle hooks. No paid Codespaces are started by CI.

## Visible CI results and release evidence

`pytest` emits individual JUnit cases for unit, installed-package, devcontainer
and registry suites. The pinned report publisher parses them into GitHub Checks
with expanded cases/failure annotations and into the run summary. Summaries link
to check views and raw reports, retained for 14 days. Report publication/upload
is attempted after failure; failing tests retain their nonzero exit status and
block release. Missing/malformed reports and publisher failures are errors.
Forks retain summaries/artifacts; a read-only fork token cannot publish Checks.

A deliberate test-only failure is used during adoption to verify that a failed
case and the failing workflow remain visible; its historical run is linked in
the PR. It is removed before the green merge. Historical trend dashboards are not
claimed. Compatibility JSON/Markdown is generated from actual runtime probes;
missing probes are NOT_COMPLETED and failed cases remain FAIL.

The adopted shared baseline is
[collaboration-guidelines v6.0.0](https://github.com/Living-Proof-Labs/collaboration-guidelines/tree/v6.0.0).
The release engine remains pinned independently to v4.0.0; documentation adoption
does not upgrade executable release workflows.
The host orchestration suite uses the same locked Python tools because it must
control native Docker; app setup/tests/builds also run in the shared development
image. Release details are in [release operation](../.github/RELEASE.md).

The [installed-user pilot and generated documentation](verification.md) adds
executable feature scenarios and a browsable command/scenario reference alongside
these existing regression suites. Its scope and untested areas are explicit.
