<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Working agreement

Read and apply [collaboration-guidelines v4.0.0](https://github.com/Living-Proof-Labs/collaboration-guidelines/blob/v4.0.0/AGENTS.md)
and relevant linked procedures at that version.

Local additions: use isolated checkouts and focused draft PRs. Run `task setup`
and `task verify`, then installed-package smoke checks. Keep this package thin:
no report implementation, provider credentials, automatic installation or downloads during ordinary commands. Explicit `plugins install`
and read-only `plugins versions` are authorized network operations (issue #3);
installation must remain user-initiated and checksum-verified.
Use Rivet's authenticated GitHub identity. Never substitute another account.
