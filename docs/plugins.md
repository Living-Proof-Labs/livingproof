<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Installed capability plugins

A distribution registers a Click Command (including Group) directly:

```toml
[project.entry-points."livingproof.capability.commands"]
report = "livingproof_capability_report.cli:report"
```

This maps `livingproof capability report` to the original command object, preserving
its options, nested commands, errors and exit codes. No umbrella import or dependency
is needed in the plugin. Python's installed distribution metadata is the discovery
mechanism; no separate shared-contracts package is required.

Names must match `[a-z][a-z0-9-]*`; invalid names are ignored. Names are listed in
sorted order. Duplicate providers for a name fail explicitly when selected, even
if both point to the same object; installation order never chooses a winner.
Group help reads metadata without importing plugin code. A plugin imports only
when selected (including its help/completion), and must expose a Click Command.
Load failures become concise Click errors; they do not break root/group help.
The reserved missing-plugin guidance for `report` disappears when it is installed.
Unknown names retain Click's normal usage error.

Installed plugin code runs with the user's privileges. Install trusted packages
explicitly. Discovery performs no network access, installation or arbitrary file
loading. Dependencies and upgrades remain the user's package-manager decision.
This first contract provides capability commands only; broader command namespaces
and provider orchestration should follow demonstrated needs.
