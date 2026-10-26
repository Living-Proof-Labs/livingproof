# SPDX-License-Identifier: Apache-2.0
from click.testing import CliRunner

from livingproof.cli import main
from livingproof.completion import ACTIVATE, LOADER


def test_help_and_status_are_self_contained():
    for args in (["--help"], ["completion", "--help"], ["completion"], ["completion", "status"]):
        result = CliRunner().invoke(main, args)
        assert result.exit_code == 0, result.output
        assert ACTIVATE in result.output
        assert "README" not in result.output
    status = CliRunner().invoke(main, ["completion", "status"]).output
    assert "cannot inspect or change that shell" in status
    assert "bash --login" in status
    assert "apt install bash-completion" in status


def test_bash_emits_only_root_completion_code():
    result = CliRunner().invoke(main, ["completion", "bash"])
    assert result.exit_code == 0
    assert "_LIVINGPROOF_COMPLETE=bash_complete" in result.output
    assert "complete -o nosort" in result.output
    assert "Bash completion setup" not in result.output


def test_user_registration_is_explicit_idempotent_and_removable(tmp_path):
    env = {"XDG_DATA_HOME": str(tmp_path), "BASH_COMPLETION_USER_DIR": ""}
    target = tmp_path / "bash-completion/completions/livingproof"
    runner = CliRunner()
    assert runner.invoke(main, ["completion", "status"], env=env).exit_code == 0
    assert not target.exists()
    for _ in range(2):
        result = runner.invoke(main, ["completion", "install"], env=env)
        assert result.exit_code == 0, result.output
        assert ACTIVATE in result.output
        assert target.read_text() == LOADER
    result = runner.invoke(main, ["completion", "install", "--remove"], env=env)
    assert result.exit_code == 0
    assert not target.exists()


def test_registration_preserves_unrelated_files_and_symlinks(tmp_path):
    env = {"BASH_COMPLETION_USER_DIR": str(tmp_path)}
    target = tmp_path / "completions/livingproof"
    target.parent.mkdir()
    target.write_text("user content")
    for args in (["completion", "install"], ["completion", "install", "--remove"]):
        assert CliRunner().invoke(main, args, env=env).exit_code == 1
        assert target.read_text() == "user content"
    target.unlink()
    other = tmp_path / "other"
    other.write_text(LOADER)
    target.symlink_to(other)
    assert CliRunner().invoke(main, ["completion", "install"], env=env).exit_code == 1
    assert target.is_symlink()
    assert other.read_text() == LOADER


def test_registration_rejects_relative_or_multiple_locations():
    for location in ("relative", "/one:/two"):
        result = CliRunner().invoke(main, ["completion", "install"], env={"BASH_COMPLETION_USER_DIR": location})
        assert result.exit_code == 1
        assert "one absolute directory" in result.output


def test_completing_install_does_not_write_registration(tmp_path):
    result = CliRunner().invoke(main, [], prog_name="livingproof", env={
        "XDG_DATA_HOME": str(tmp_path), "BASH_COMPLETION_USER_DIR": "",
        "_LIVINGPROOF_COMPLETE": "bash_complete",
        "COMP_WORDS": "livingproof completion install --r", "COMP_CWORD": "3"})
    assert result.exit_code == 0
    assert result.output == "plain,--remove\n"
    assert list(tmp_path.iterdir()) == []
