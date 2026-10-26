# SPDX-License-Identifier: Apache-2.0
"""Discover installed Click commands without importing plugins during group help."""
from importlib.metadata import entry_points
import re

import click
from click.shell_completion import CompletionItem

PLUGIN_GROUP = "livingproof.capability.commands"
INSTALL_REPORT = (
    "Install the livingproof-capability-report v1.4.0 wheel into the same Python environment "
    "as livingproof. For a Debian-installed root, install the reporter all.deb with apt instead. "
    "Download it and verify SHA256SUMS from https://github.com/"
    "Living-Proof-Labs/livingproof-capability-report/releases/tag/v1.4.0. "
    "No packages are installed automatically."
)


class Unavailable(click.Command):
    def __init__(self, name, reason):
        super().__init__(name, help=reason)
        self.reason = reason

    def get_help(self, ctx):
        raise click.ClickException(self.reason)

    def invoke(self, ctx):
        raise click.ClickException(self.reason)


class Plugins(click.Group):
    """One small entry-point contract: names map directly to Click commands."""

    def candidates(self):
        found = {}
        for entry in entry_points(group=PLUGIN_GROUP):
            if re.fullmatch(r"[a-z][a-z0-9-]*", entry.name):
                found.setdefault(entry.name, []).append(entry)
        return found

    def list_commands(self, ctx):
        return sorted({"report", *self.candidates()})

    def shell_complete(self, ctx, incomplete):
        # Listing plugins must not import them. Click resolves the selected entry
        # through get_command during resilient parsing for deeper completions.
        commands = [] if incomplete.startswith("-") else [
            CompletionItem(name) for name in self.list_commands(ctx)
            if name.startswith(incomplete)
        ]
        return commands + click.Command.shell_complete(self, ctx, incomplete)

    def format_commands(self, ctx, formatter):
        found = self.candidates()
        rows = [(name, "Installed plugin" if name in found else "Optional reporting plugin (install required)")
                for name in self.list_commands(ctx)]
        with formatter.section("Commands"):
            formatter.write_dl(rows)

    def get_command(self, ctx, name):
        entries = self.candidates().get(name, [])
        if not entries:
            return Unavailable(name, INSTALL_REPORT) if name == "report" else None
        if len(entries) != 1:
            return Unavailable(name, f"Multiple installed plugins provide '{name}'. "
                               "Remove the conflicting distribution from this environment.")
        entry = entries[0]
        try:
            command = entry.load()
            if not isinstance(command, click.Command):
                raise TypeError("entry point must expose a Click Command")
        except Exception as exc:
            return Unavailable(name, f"Cannot load plugin '{name}': {type(exc).__name__}: {exc}")
        return command


@click.group(invoke_without_command=True)
@click.version_option(package_name="livingproof")
@click.pass_context
def main(ctx):
    """Living Proof Labs: specs, evidence, assessments and portable reports.

    Plugins come from packages explicitly installed in this Python environment.

    Bash completion is registered by the Debian package with bash-completion.
    For wheel installs and other shells, see the README shell completion section.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.group(cls=Plugins, invoke_without_command=True)
@click.pass_context
def capability(ctx):
    """Work with capability evidence through installed plugins."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
