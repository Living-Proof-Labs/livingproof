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
   [capability reporter v1.3.0](https://github.com/Living-Proof-Labs/livingproof-capability-report/tree/v1.3.0).
   It validates bundles, grades with its supported policy, and renders saved decisions
   as terminal tables, JSON, HTML or CSV. Evidence stays in the bundle. Rendering
   does not regrade. These fixture demonstrations do not establish robot safety certification.

## What exists and what is planned

| Area | Status |
| --- | --- |
| Specs, deterministic fixtures, mock AI and recorded human fixture assessments | Existing versioned ecosystem repositories linked above |
| Bundle validation, policy grading, portable reporting and standalone reporting library/CLI | Implemented by reporter v1.3.0 |
| Thin root command and installed Click plugin discovery | Implemented in this source; first hosted release pending |
| Reporter plugin registration | Prepared as a focused metadata change; v1.3.0 itself has no plugin entry point |
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

For a released reporting workflow today, follow
[reporter v1.3.0 installation and usage](https://github.com/Living-Proof-Labs/livingproof-capability-report/blob/v1.3.0/README.md)
and use `livingproof-capability-report`. Its library remains independently importable.
There is no published umbrella release established by this checkout yet.

To try this candidate, build its wheel using the contributor commands below and
install it into a Python 3.11+ virtual environment:

```sh
python3 -m venv /tmp/livingproof-demo
/tmp/livingproof-demo/bin/pip install ./dist/livingproof-*.whl
/tmp/livingproof-demo/bin/livingproof
/tmp/livingproof-demo/bin/livingproof capability --help
```

Install a reporter wheel containing the new plugin metadata into **that same
virtual environment**, then run:

```sh
/tmp/livingproof-demo/bin/pip install /path/to/livingproof_capability_report-*.whl
/tmp/livingproof-demo/bin/livingproof capability report --help
/tmp/livingproof-demo/bin/livingproof capability report validate bundle/manifest.json
/tmp/livingproof-demo/bin/livingproof capability report grade bundle/manifest.json -o report.json
/tmp/livingproof-demo/bin/livingproof capability report render report.json --format html -o report.html
```

Choose reviewed, versioned release assets and verify their published checksums.
The umbrella never downloads evidence or installs plugins at runtime. Separate
pipx environments cannot discover each other's plugins; install into one environment.
An old reporter without plugin metadata continues to work standalone and is not
silently adapted by this package. Output files must be new; errors and exit codes
come from the reporting command unchanged.

### Shell completion

Click supports Bash, Zsh and Fish completion, including installed plugin commands.
Generate a script with the installed executable, then source it in your shell:

```sh
_LIVINGPROOF_COMPLETE=bash_source livingproof > livingproof-complete.bash
. ./livingproof-complete.bash
```

For Zsh/Fish use `zsh_source`/`fish_source` and the corresponding shell's sourcing
mechanism. Completion loads selected plugins as needed; install only trusted
packages. Automated protocol checks cover Bash; interactive editor/shell sessions
and other operating systems are not claimed as verified.

## Develop and contribute

Use [the contributor guide](docs/development.md) for Docker, devcontainer, Task,
installed smoke tests and release handling. The pinned shared baseline is
[collaboration-guidelines v3.0.0](https://github.com/Living-Proof-Labs/collaboration-guidelines/tree/v3.0.0).
Read [the plugin contract](docs/plugins.md) before adding a plugin. Keep the root
small and link versioned ecosystem documentation rather than copying it here.

Original tooling and reusable examples are Apache-2.0; original written content
is CC BY 4.0. See [explicit license boundaries](LICENSE.md).
