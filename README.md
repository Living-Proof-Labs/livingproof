<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# LivingProof

**[Start here: documentation](https://docs.livingprooflabs.com/livingproof/)**

LivingProof is the thin, installable umbrella command for discovering and using
explicitly installed capability plugins. It contains no reporting,
grading, robot execution or provider integration implementation.

## From a claim to a portable report

The organization owns the [vision and evidence workflow](https://docs.livingprooflabs.com/vision.html#from-a-requirement-to-the-next-improvement).
LivingProof provides the umbrella command and explicit plugin lifecycle; installed
plugins own their reporting, grading and execution behavior.

## What exists and what is planned

Use the [published manual directory](https://docs.livingprooflabs.com/#published-manuals)
to find each product's current behavior and limits. This repository implements
command discovery, plugin lifecycle and completion; it does not implement robot
execution or evaluator integrations.

### Candidate evaluator integrations

Integration direction belongs to the [organization vision](https://docs.livingprooflabs.com/vision.html).
Candidate integrations are not delivered LivingProof plugins or evidence of
robot safety certification. Product contracts remain with their implementers.

## Get started

Download versioned assets and `SHA256SUMS` from this repository's
[Releases](https://github.com/Living-Proof-Labs/livingproof/releases).
Choose one installation route; plugins must use the same Python environment as
the root command. Ordinary commands never download or install plugins automatically. Explicit
`plugins versions` and `plugins install` commands use the network as documented below.

| Route | Root command | Reporter plugin |
| --- | --- | --- |
| Debian/Ubuntu | Root `all.deb`, installed with apt | Reporter `all.deb`, installed with apt; both use `/usr/bin/python3` |
| Python virtual environment | Root wheel or source distribution | Reporter wheel installed into that same virtual environment |
| Container | Versioned root image | Explicit `-reporting` image variant includes reporter v1.6.0 |

### Debian and Ubuntu

Download the root `.deb` and checksums into `root-release`. Download the reporter
`.deb` and its checksums from
[reporter v1.6.0](https://github.com/Living-Proof-Labs/livingproof-capability-report/releases/tag/v1.6.0)
into `reporter-release`. Then:

```sh
(cd root-release && sha256sum --ignore-missing -c SHA256SUMS)
(cd reporter-release && sha256sum --ignore-missing -c SHA256SUMS)
sudo apt install ./root-release/python3-livingproof-common_1.0.0_all.deb ./root-release/livingproof_*_all.deb
livingproof --help
livingproof capability report --help  # explains that the plugin is not installed yet
sudo apt install ./reporter-release/livingproof-capability-report_*_all.deb
livingproof capability report --help
livingproof-capability-report --help
```

The root package is `Architecture: all`, contains pure Python and installed entry-point
metadata, and uses distribution-owned Python and Click. The reporter is optional,
not an apt dependency; install it explicitly. No pip installation into system Python
or private Debian virtual environment is involved. Do not install only the reporter
wheel into a separate virtual environment and expect `/usr/bin/livingproof` to discover it.
Use `command -v livingproof` to check which executable your shell selected.

Native CI tests **the same root Debian asset** with the published reporter `.deb`
on Debian 12, Debian 13 and Ubuntu 24.04, on amd64 and arm64. Consult each release's
`compatibility-amd64.json` / `compatibility-arm64.json` for actual outcomes rather
than assuming a configured target passed. Unsupported distributions are unverified.

### Python environment

```sh
python3 -m venv .venv
.venv/bin/pip install ./root-release/livingproof_common-1.0.0-py3-none-any.whl ./root-release/livingproof-*.whl
.venv/bin/pip install ./reporter-release/livingproof_capability_report-*.whl
.venv/bin/livingproof capability report --help
```

Use Python 3.11 or newer. Separate pipx environments cannot discover each other's
plugins. The independently installed reporter command and Python library remain
available; see the
[reporter guide](https://docs.livingprooflabs.com/livingproof-capability-report/).

### Containers

Two explicit variants are built from installed packages, with no source checkout,
Task, runtime network dependency or automatic plugin installation:

- `ghcr.io/living-proof-labs/livingproof:VERSION` contains the root command only.
- `ghcr.io/living-proof-labs/livingproof:VERSION-reporting` contains root plus the
  pinned reporter v1.6.0. Its standalone command and library remain installed.

Routine releases distribute native amd64/arm64 containers through the public
registry after anonymous digest-pinned checks pass on both architectures. Release
notes list the immutable registry manifest digests and tested platforms; these are
not local Docker image IDs. Copy the reporting digest from those notes:

```sh
IMAGE=ghcr.io/living-proof-labs/livingproof@sha256:REPLACE_WITH_RELEASE_MANIFEST_DIGEST
docker pull "$IMAGE"
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/bundle:/data:ro" \
  "$IMAGE" capability report validate manifest.json
```

For an explicit offline export, pull the selected digest on the target architecture
and run `docker save -o livingproof-offline.tar "$IMAGE"`. Transfer that file and
its checksum to the offline host and use `docker load`. Routine releases no longer
attach image archives; existing release assets remain available unchanged.

The normal entrypoint is `livingproof`. A job container can override it with
`--entrypoint /bin/sh`; CI checks normal and shell/interpreter entrypoint use
separately. Root-only images give missing-plugin guidance. A reporting image's
plugin lives in the same `/opt/livingproof` Python environment as the root.

### Produce a report

Use an existing portable evidence bundle. For a fixture demonstration, download
the reporter v1.6.0 source archive and verify its published checksum, then extract
only its example data (no source checkout or source execution is required):

```sh
tar -xzf reporter-release/livingproof_capability_report-1.6.0.tar.gz \
  --strip-components=2 livingproof_capability_report-1.6.0/examples/bundle
livingproof capability report validate bundle/manifest.json
livingproof capability report grade bundle/manifest.json -o report.json
livingproof capability report render report.json --format html -o report.html
```

Output files must be new. Reporting errors and exit codes are preserved. Fixture
FAIL/INSUFFICIENT_EVIDENCE grades are expected evidence outcomes, not test-run failures.

### Shell completion

The installed CLI contains setup and diagnostics; no checkout or README is needed:

```sh
livingproof completion status
```

Enable completion in the **current Bash shell**, even without bash-completion:

```sh
eval "$(livingproof completion bash)"
complete -p livingproof
```

Then try `livingproof cap<TAB>` and `livingproof capability report <TAB>`.
Completion continues into installed plugins, their options, choices and paths.
It discovers plugins installed later without regenerating the registration and
does not execute command callbacks or install plugins.

The Debian package owns
`/usr/share/bash-completion/completions/livingproof` and recommends
`bash-completion`. Those files alone do **not** enable an existing shell. Stock
Ubuntu/Debian container root startup files leave the framework disabled in plain
non-login `bash`, including a fresh shell after package installation. For a new
shell using the distribution's normal login startup:

```sh
# Run apt as an administrator if bash-completion is missing.
apt install bash-completion
bash --login
```

This lets the framework discover the package-owned registration lazily. For an
already-running shell or a non-login shell, use the current-shell activation
command above. A package installer cannot modify its parent shell. The status
command reports files and gives exact instructions; it cannot inspect whether
functions are loaded in the calling shell.

For a wheel/virtual environment, put the intended executable on `PATH` and use:

```sh
livingproof completion install
```

This explicitly writes only a user registration under
`${BASH_COMPLETION_USER_DIR}/completions`, or
`${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions` by default.
It refuses unrelated existing files and symlinks. It does not install the
framework, request administrator privileges or edit startup files. Future shells
still need the framework loaded, or the current-shell activation command.
`livingproof completion install --remove` removes only the registration it owns.
Debian/pip remove their own package files; a loaded shell function lasts until
exit or `complete -r livingproof`.

For persistent non-login activation without the framework, users may choose to
add `eval "$(livingproof completion bash)"` to their own `.bashrc` themselves.
No Living Proof command edits that file.

For explicit current-session Zsh setup, use
`eval "$(_LIVINGPROOF_COMPLETE=zsh_source livingproof)"` after `compinit`.
For Fish, use `_LIVINGPROOF_COMPLETE=fish_source livingproof | source`.
Only Bash is exercised by the shell tests; other-shell compatibility is not
claimed. Standalone reporter registration belongs to the reporter package.

Tests include actual Readline Tab in default-startup Bash pseudo-terminals,
installation during a running shell, absent/present frameworks, documented
current-shell recovery, automatic login-shell loading, nested plugin completion
and removal. The older adapter tests that explicitly source the framework remain
separate from these startup tests. See
[bash-completion's package guidance](https://sources.debian.org/src/bash-completion/1:2.16.0-7/README.md/)
and [Click's completion protocol](https://click.palletsprojects.com/en/stable/shell-completion/).

## Develop and contribute

Use [the contributor guide](docs/development.md) for Docker, devcontainer, Task,
installed smoke tests and release handling. The pinned shared baseline is
[collaboration-guidelines v4.0.0](https://github.com/Living-Proof-Labs/collaboration-guidelines/tree/v4.0.0).
Read [the plugin contract](docs/plugins.md) before adding a plugin. Keep the root
small and link versioned ecosystem documentation rather than copying it here.

Original tooling and reusable examples are Apache-2.0; original written content
is CC BY 4.0. See [explicit license boundaries](LICENSE.md).

## Identify the build being tested

Run `livingproof --version` and include both lines in problem reports. The first
line identifies this tool's source/build; the second reports installed PEP 440
package metadata and whether identity came from a live checkout or recorded build.

```sh
livingproof --version
livingproof capability report --version
livingproof-capability-report --version
```

Root uses released [livingproof-common v1.0.0](https://github.com/Living-Proof-Labs/livingproof-common/releases/tag/v1.0.0)
with its own package directory. Nested reporting retains the reporter's identity;
common's library version is never substituted for either consumer. The reporter
release pin remains explicit in `reporter-release.txt`.

A clean exact release tag displays X.Y.Z. Development output includes release
base, commit distance/hash, bounded public branch label and clean/dirty state.
Editable installs update dirty state without reinstalling. Dirty state is not a
digest of uncommitted content. Missing Git, empty, shallow and untagged history
are explicit. Only approved public-origin tracking branches are eligible for
named labels; other local branches stay `local` or `detached`. Installed artifacts
retain their own build snapshot without Git and ignore the caller's directory.

Hatch-VCS still supplies PEP 440 package metadata; the shared library supplies
source identity. Both build and runtime pin common v1.0.0. Packaging includes the
unchanged upstream common wheel and Debian library after checking their published
SHA-256 digests. Offline container installs resolve it from the wheelhouse. Install
the common `.deb` alongside root's `.deb`; no apt repository or PyPI availability
is assumed. Runtime commands never download or install dependencies.

## Explicit plugin management

```sh
livingproof plugins versions livingproof-capability-report
livingproof plugins versions livingproof-capability-report --limit 120
livingproof plugins install livingproof-capability-report --version 1.6.0 --dry-run
livingproof plugins install livingproof-capability-report --version 1.6.0
livingproof plugins status livingproof-capability-report
```

Installation defaults to GitHub's latest published stable release. Version lists
include prereleases and release titles, default to 20 entries, and automatically
page for larger limits. A pin selects an exact published `vVERSION` tag and can
upgrade or downgrade. Repeating an install reconciles the requested packages.
Existing root and reporter `--version` options still print build identity.

Only the known reporter is accepted. Assets come from the release API for
`Living-Proof-Labs/livingproof-capability-report`; its declared exact common
library dependency comes from `Living-Proof-Labs/livingproof-common`. Every
selected artifact must have one matching published `SHA256SUMS` entry. Checksums
protect integrity against the trusted release record, not a compromised publisher.
The manager checks package identity, version, wheel/Python compatibility or Debian
architecture before installation. An incompatible root/common requirement fails
before package mutation. Common is supplied even when already installed, so apt
does not need a Living Proof Labs package repository.

A root owned by the installed `livingproof` Debian package uses apt. A root in a
virtual environment uses that interpreter's pip, including on Debian. Other
contexts fail with migration instructions; there is no system pip fallback or
PEP 668 override. Create a virtual environment with `python3 -m venv ENV` and
install the root wheel there, then invoke `ENV/bin/livingproof`. That environment
must include pip. Normal Python dependencies use pip's configured package index;
Debian dependencies use the administrator's configured distribution repositories.
No repository configuration or credentials are changed. Anonymous API access needs
no credentials. Automated test environments may supply an existing read-only
`LIVINGPROOF_GITHUB_TOKEN` to avoid the anonymous API rate limit; it is sent only
to api.github.com, never to release download hosts.

The explicit install command prints all verified artifacts, target and operation
before mutation, never prompts, never invokes sudo and never handles passwords.
The Debian operation repairs missing dependencies using the supplied artifacts and
refuses package removals. For a system install an administrator must explicitly run the command from the
Debian installation with appropriate privileges. `--dry-run` downloads and verifies
but does not install. Ordinary commands, help and completion never install or
fetch anything. `status` reads local metadata and checks that the discovered plugin
loads; it reports the actual package version, not a release lookup.

Exit codes are 0 for success, 1 for absent/broken plugins or operational failures,
and 2 for invalid arguments. Network failures, rate limits, unavailable assets and
checksum failures abort before installation. Temporary downloads are removed.
Package-manager failures can leave partial dependency changes: inspect `plugins
status`, fix the reported package-manager problem, and explicitly retry. Remove a
Debian reporter with `apt-get remove livingproof-capability-report`, or a virtual
environment reporter with `ENV/bin/python -m pip uninstall livingproof-capability-report`.
Keep common while root still requires it. Restart the command after installation;
plugin discovery and completion use the newly installed entry point.

## Executable user journeys and browsable documentation

See the [verification and documentation guide](docs/verification.md) for the small
[installed-user scenario pilot](tests/features/installed.feature), generated Click
reference, actual scenario outcomes and independent-review commands. Run `task docs`
after building and exercising the candidate images to browse
`artifacts/docs/html/index.html`, or download the linked documentation artifact from
[the CI run](https://github.com/Living-Proof-Labs/livingproof/actions/workflows/verify.yml).
