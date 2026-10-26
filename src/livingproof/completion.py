# SPDX-License-Identifier: Apache-2.0
"""Explicit Bash setup; never modify startup files or claim parent-shell state."""
import os
from pathlib import Path
import sys

import click
from click.shell_completion import BashComplete

ACTIVATE = 'eval "$(livingproof completion bash)"'
LOADER = ('# Installed by livingproof completion install; safe to remove.\n'
          'eval "$(_LIVINGPROOF_COMPLETE=bash_source livingproof)"\n')


def user_directory():
    configured = os.environ.get("BASH_COMPLETION_USER_DIR")
    if configured:
        directory = Path(configured)
        if ":" in configured or not directory.is_absolute():
            raise click.ClickException("BASH_COMPLETION_USER_DIR must be one absolute directory.")
    else:
        data = os.environ.get("XDG_DATA_HOME")
        if data and not Path(data).is_absolute():
            raise click.ClickException("XDG_DATA_HOME must be an absolute directory.")
        directory = (Path(data) if data else Path.home() / ".local/share") / "bash-completion"
    return directory / "completions"


def guidance():
    click.echo("Bash completion setup (Bash 4.4 or newer)")
    package_file = Path(sys.prefix) / "share/bash-completion/completions/livingproof"
    framework = Path("/usr/share/bash-completion/bash_completion")
    user_file = user_directory() / "livingproof"
    for label, path in (("Package registration", package_file),
                        ("User registration", user_file), ("Bash-completion framework", framework)):
        click.echo(f"{label}: {'installed' if path.is_file() else 'not found'} ({path})")
    click.echo(f"""
Installed files do not mean completion is loaded in your current shell.
This command runs in a child process and cannot inspect or change that shell.

Enable completion in your CURRENT Bash shell (also works without bash-completion):
  {ACTIVATE}
Check the registration in that same shell:
  complete -p livingproof
Try typing: livingproof capability <TAB>

For automatic loading in NEW shells on Debian/Ubuntu:
  apt install bash-completion
Run apt as an administrator; this tool never elevates privileges or installs packages.
Then start a login shell, which reads the distribution's framework startup script:
  bash --login
A new non-login shell (plain bash, including Docker's default bash) may still
leave the framework disabled. In that shell, use the CURRENT-shell command above.
Installing a Debian package cannot activate completion in an already-running shell.

Wheel/virtual-environment users: put the intended livingproof executable on PATH,
then register it in your user's standard bash-completion directory:
  livingproof completion install
This still needs the framework loaded in new shells, or CURRENT-shell activation.
To remove that user-owned registration:
  livingproof completion install --remove
Debian/pip remove package-owned registration files when uninstalling the package.
Already-loaded shell functions remain until the shell exits; remove one now with:
  complete -r livingproof

No command here edits .bashrc or other startup files. For persistent non-login
shell activation without the framework, you may add the CURRENT-shell command
above to your own .bashrc yourself. Installed plugins are discovered dynamically;
Tab does not install plugins or run their command callbacks.""")


@click.group(invoke_without_command=True)
@click.pass_context
def completion(ctx):
    """Show Bash setup/status and exact activation commands; no startup-file edits.

    \b
    Enable in the CURRENT Bash shell:
      eval "$(livingproof completion bash)"
    Show installed files and NEW-shell setup:
      livingproof completion status
    """
    if ctx.invoked_subcommand is None:
        guidance()


@completion.command()
def status():
    """Show installed registration files and explain current/new-shell setup."""
    guidance()


@completion.command()
@click.pass_context
def bash(ctx):
    """Print Bash code. Activate with: eval "$(livingproof completion bash)"."""
    click.echo(BashComplete(ctx.find_root().command, {}, "livingproof",
                           "_LIVINGPROOF_COMPLETE").source())


@completion.command()
@click.option("--remove", is_flag=True, help="Remove only the user registration created here.")
def install(remove):
    """Register for this user in the standard directory; never edit startup files.

    Requires bash-completion to be loaded in future shells. Existing unrelated
    files are never overwritten. No administrator privileges are requested.
    """
    target = user_directory() / "livingproof"
    try:
        if target.is_symlink():
            raise click.ClickException(f"Refusing to change a symlink: {target}")
        if target.exists():
            if target.read_text() != LOADER:
                raise click.ClickException(f"Existing file was not created by this command: {target}")
            if remove:
                target.unlink()
        elif not remove:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x") as output:
                output.write(LOADER)
    except OSError as exc:
        raise click.ClickException(f"Cannot update {target}: {exc}") from exc
    click.echo(f"{'Removed' if remove else 'Registered'} user completion: {target}")
    if not remove:
        click.echo(f"Enable in this Bash shell now:\n  {ACTIVATE}\n"
                   "Future shells need bash-completion loaded; run livingproof completion status.")
    else:
        click.echo("In a shell that already loaded it, run: complete -r livingproof")
