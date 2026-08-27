from importlib.metadata import version

import pytest
from typer.testing import CliRunner

from smpmgr.main import app

runner = CliRunner()


def test_root_help_builds_complete_command_tree() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "Simple Management Protocol" in result.output
    for command in ("upgrade", "os", "image", "file", "enum"):
        assert command in result.output


def test_nested_help_builds_commands() -> None:
    result = runner.invoke(app, ["os", "--help"])

    assert result.exit_code == 0, result.output
    assert "echo" in result.output
    assert "reset" in result.output


def test_version_reports_installed_package_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == version("smpmgr")


def test_root_without_command_requests_command() -> None:
    result = runner.invoke(app, [])

    assert result.exit_code == 0, result.output
    assert "A command is required" in result.output


@pytest.mark.parametrize(
    "transport",
    [("--port", "/dev/ttyACM0"), ("--ip", "127.0.0.1")],
)
def test_global_options_parse_without_running_command(transport: tuple[str, str]) -> None:
    result = runner.invoke(
        app,
        [*transport, "--timeout", "3.5", "--loglevel", "INFO"],
    )

    assert result.exit_code == 0, result.output
