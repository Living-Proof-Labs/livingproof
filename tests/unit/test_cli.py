# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import click
import pytest
from click.testing import CliRunner
from livingproof import cli


@pytest.fixture
def entries(monkeypatch):
    entries = []
    monkeypatch.setattr(cli, "entry_points", lambda *, group: entries)
    return entries


def ep(name, value):
    return SimpleNamespace(name=name, load=lambda: value)


def run(*args):
    return CliRunner().invoke(cli.main, args)


def test_empty_startup_and_missing_report(entries):
    for args in [(), ("--help",), ("capability",), ("capability", "--help")]:
        assert run(*args).exit_code == 0
    for args in [("capability", "report"), ("capability", "report", "--help")]:
        result = run(*args)
        assert result.exit_code == 1
        assert "same Python environment" in result.output
        assert "No packages are installed automatically" in result.output
    assert run("capability", "unknown").exit_code == 2


def test_delegates_command_and_error(entries):
    @click.command()
    @click.option("--fail", is_flag=True)
    def report(fail):
        if fail:
            raise click.ClickException("original error")
        click.echo("original report")
    entries.append(ep("report", report))
    assert run("capability", "report").output == "original report\n"
    assert run("capability", "report", "--help").exit_code == 0
    result = run("capability", "report", "--fail")
    assert result.exit_code == 1
    assert "original error" in result.output


def test_help_does_not_import_broken_plugin(entries):
    def broken():
        raise ImportError("missing dependency")
    entries.append(SimpleNamespace(name="report", load=broken))
    assert run("capability", "--help").exit_code == 0
    result = run("capability", "report")
    assert result.exit_code == 1
    assert "ImportError: missing dependency" in result.output


def test_duplicates_invalid_objects_and_names(entries):
    entries.extend([ep("report", object()), ep("INVALID", object())])
    assert "INVALID" not in run("capability", "--help").output
    assert "Click Command" in run("capability", "report").output
    entries.append(ep("report", object()))
    assert "Multiple installed plugins" in run("capability", "report").output


def test_arbitrary_plugin_and_bash_completion(entries):
    @click.command()
    def inspect():
        click.echo("inspect")
    entries.append(ep("inspect", inspect))
    assert run("capability", "inspect").output == "inspect\n"
    result = CliRunner().invoke(cli.main, [], prog_name="livingproof", env={
        "_LIVINGPROOF_COMPLETE": "bash_complete", "COMP_WORDS": "livingproof capability i",
        "COMP_CWORD": "2"})
    assert result.exit_code == 0
    assert "plain,inspect" in result.output


def test_plugin_explicit_exit_code(entries):
    @click.command()
    @click.pass_context
    def report(ctx):
        ctx.exit(7)
    entries.append(ep("report", report))
    assert run("capability", "report").exit_code == 7
