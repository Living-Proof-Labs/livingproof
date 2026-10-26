<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Living Proof Labs

Living Proof Labs connects capability specifications to evidence and reviewable
reports. `livingproof` is the project landing home and a thin, installable Click
command. It delegates to explicitly installed plugins; it contains no reporting,
grading, robot execution or provider integration implementation.

## From a claim to a portable report

**Versioned specs → execution and evidence → evaluator assessments →
versioned policy-based grade → portable report.**

1. Author and manage capability specifications in
   [robot-capability-specs v1.2.0](https://github.com/Living-Proof-Labs/robot-capability-specs/tree/v1.2.0).
   That repository owns specs, not a general execution platform.
2. Execute a scenario and retain its context, original producer result and evidence.
   [capability-verifier v1.1.2](https://github.com/Living-Proof-Labs/capability-verifier/tree/v1.1.2)
   provides the existing fixture workflow. Real robot and simulator adapters are future work.
3. Record evaluator assessments against the exact spec and evidence. Deterministic
   checks, AI assessments and human review remain distinct. An assessment may
   propose a grade; disagreements, rationale and provenance must stay visible.
4. Apply an explicit, versioned grading policy to decide the final grade. A model's
   proposed grade is an input, not authority to silently replace that policy.
5. Produce a portable report with the existing
   [capability reporter v1.4.0](https://github.com/Living-Proof-Labs/livingproof-capability-report/tree/v1.4.0).
   It validates bundles, grades with its supported policy, and renders saved decisions
   as terminal tables, JSON, HTML or CSV. Evidence stays in the bundle. Rendering
   does not regrade. These fixture demonstrations do not establish robot safety certification.

## What exists and what is planned

| Area | Status |
| --- | --- |
| Specs, deterministic fixtures, mock AI and recorded human fixture assessments | Existing versioned ecosystem repositories linked above |
| Bundle validation, policy grading, portable reporting and standalone reporting library/CLI | Implemented by reporter v1.4.0 |
| Thin root command and installed Click plugin discovery | Implemented; wheel, source, Debian and native container distributions use the shared release workflow |
| Reporter plugin registration | Implemented by reporter v1.4.0; its standalone command and library remain independent |
| Real evaluator/provider integrations and robot/simulator adapters | Candidate designs only; no credentials, model calls or adapters delivered here |

Full MCAP recordings may be evidence inputs. A future adapter may extract signals,
frames or summaries for an evaluator while preserving links to original evidence.
Not every provider accepts MCAP directly. Input support, execution interfaces,
retention and provenance must be established separately for each integration.

### Candidate evaluator integrations

These are candidates for future evaluator implementations, not delivered plugins,
endorsements or interchangeable execution APIs. Official product descriptions
were reviewed on 2026-10-25:

| Candidate | Relevant documented capability | Proposed role |
| --- | --- | --- |
| [Roboto](https://www.roboto.ai/platform/) | Robotics data analytics, Actions and AI log analysis; MCAP support | Robotics/log evidence assessments |
| [Foxglove Agents](https://docs.foxglove.dev/docs/agents) | Agents and MCP for investigating robot data | Robotics/log evidence assessments |
| [OpenAI ChatGPT](https://help.openai.com/en/articles/8437071-data-analysis-with-chatgpt) / [Codex](https://openai.com/codex/) | File/data analysis in ChatGPT; coding agent workflows in Codex | Candidate provider/agent-assisted evaluation workflows, with separate integration designs |
| [Google Gemini](https://ai.google.dev/gemini-api/docs/document-processing) | Document understanding through its API | Assessments over supported representations of evidence |
| [Cursor](https://cursor.com/docs/agent/overview) | Coding agent with file, search and terminal tools | Agent-assisted evaluator development and execution workflows |

An adapter must record evaluator and model versions where available, inputs,
transformations, rationale and execution provenance. Preserve deterministic checks
and human reviews alongside AI assessments, including contradictions. The current
reporter's supported evaluator/policy set is deliberately narrow: recording a new
provider does not make its results compatible with an existing policy automatically.

## Get started

Download versioned assets and `SHA256SUMS` from this repository's
[Releases](https://github.com/Living-Proof-Labs/livingproof/releases).
Choose one installation route; plugins must use the same Python environment as
the root command. Nothing is downloaded or installed by the CLI at runtime.

| Route | Root command | Reporter plugin |
| --- | --- | --- |
| Debian/Ubuntu | Root `all.deb`, installed with apt | Reporter `all.deb`, installed with apt; both use `/usr/bin/python3` |
| Python virtual environment | Root wheel or source distribution | Reporter wheel installed into that same virtual environment |
| Container | Versioned root image | Explicit `-reporting` image variant includes reporter v1.4.0 |

### Debian and Ubuntu

Download the root `.deb` and checksums into `root-release`. Download the reporter
`.deb` and its checksums from
[reporter v1.4.0](https://github.com/Living-Proof-Labs/livingproof-capability-report/releases/tag/v1.4.0)
into `reporter-release`. Then:

```sh
(cd root-release && sha256sum --ignore-missing -c SHA256SUMS)
(cd reporter-release && sha256sum --ignore-missing -c SHA256SUMS)
sudo apt install ./root-release/livingproof_*_all.deb
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
.venv/bin/pip install ./root-release/livingproof-*.whl
.venv/bin/pip install ./reporter-release/livingproof_capability_report-*.whl
.venv/bin/livingproof capability report --help
```

Use Python 3.11 or newer. Separate pipx environments cannot discover each other's
plugins. The independently installed reporter command and Python library remain
available; see the
[reporter guide](https://github.com/Living-Proof-Labs/livingproof-capability-report/blob/v1.4.0/README.md).

### Containers

Two explicit variants are built from installed packages, with no source checkout,
Task, runtime network dependency or automatic plugin installation:

- `ghcr.io/living-proof-labs/livingproof:VERSION` contains the root command only.
- `ghcr.io/living-proof-labs/livingproof:VERSION-reporting` contains root plus the
  pinned reporter v1.4.0. Its standalone command and library remain installed.

Use an explicit released version, never a moving `latest` tag. Native amd64/arm64
images are also attached as `image-ARCH.tar` and `reporting-image-ARCH.tar`; saved
images remain usable if registry publication or access is unavailable. Check the
release workflow's registry checks for actual anonymous availability. Loading a
saved image uses its architecture-specific tag:

```sh
VERSION=1.1.0  # replace with the selected release version
ARCH=amd64    # use arm64 on ARM
sha256sum --ignore-missing -c SHA256SUMS
docker load -i "reporting-image-${ARCH}.tar"
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/bundle:/data:ro" \
  "ghcr.io/living-proof-labs/livingproof:${VERSION}-reporting-${ARCH}" \
  capability report validate manifest.json
```

The normal entrypoint is `livingproof`. A job container can override it with
`--entrypoint /bin/sh`; CI checks normal and shell/interpreter entrypoint use
separately. Root-only images give missing-plugin guidance. A reporting image's
plugin lives in the same `/opt/livingproof` Python environment as the root.

### Produce a report

Use an existing portable evidence bundle. For a fixture demonstration, download
the reporter v1.4.0 source archive and verify its published checksum, then extract
only its example data (no source checkout or source execution is required):

```sh
tar -xzf reporter-release/livingproof_capability_report-1.4.0.tar.gz \
  --strip-components=2 livingproof_capability_report-1.4.0/examples/bundle
livingproof capability report validate bundle/manifest.json
livingproof capability report grade bundle/manifest.json -o report.json
livingproof capability report render report.json --format html -o report.html
```

Output files must be new. Reporting errors and exit codes are preserved. Fixture
FAIL/INSUFFICIENT_EVIDENCE grades are expected evidence outcomes, not test-run failures.

### Shell completion

On Debian 12/13 and Ubuntu 24.04, the Debian package owns
`/usr/share/bash-completion/completions/livingproof` and recommends
`bash-completion`. With that package installed and enabled in your interactive
Bash shell, completion loads on demand. No installer edits shell startup files.
If needed, enable it for the current session with
`. /usr/share/bash-completion/bash_completion`.

Try `livingproof <TAB>`, `livingproof capability <TAB>`, then
`livingproof capability report <TAB>`. When the reporter is installed in the
same Python environment, completion continues into its commands, options,
choices and file arguments. Installing a plugin after the root requires no
regeneration: each completion queries installed entry points. Completion does
not install missing plugins or execute command callbacks. Listing plugins avoids
importing them; completing inside one imports its Click command, so install only
trusted plugins. An absent reporter has no report subcommands to suggest.

Wheel installs include the loader under the environment's
`share/bash-completion/completions/livingproof`. Bash-completion 2.12+ can discover
this relative to the executable. For older versions, explicitly generate a
user-owned registration with the intended environment's executable on `PATH`:

```sh
completion_dir="${BASH_COMPLETION_USER_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion}/completions"
mkdir -p "$completion_dir"
_LIVINGPROOF_COMPLETE=bash_source livingproof > "$completion_dir/livingproof"
```

Remove that user-owned file yourself when uninstalling the wheel. Package-owned
files are removed by pip or apt; a shell that already loaded a completion retains
its function until restarted (or `complete -r livingproof`).

For an explicit current-session Zsh setup, use
`eval "$(_LIVINGPROOF_COMPLETE=zsh_source livingproof)"` after `compinit`.
For Fish, use `_LIVINGPROOF_COMPLETE=fish_source livingproof | source`.
These follow Click's setup protocol; only Bash is exercised by our shell tests.
Standalone reporter registration belongs to the reporter package; this package
registers the root command, including nested installed reporter completion.

The installed tests exercise fresh Bash shells and the real reporter on the
native architectures in CI. Registration follows
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
