"""Smoke tests: the package imports and the CLI runs without the heavy extras."""

from vine import __version__
from vine.cli import main


def test_version_set():
    assert __version__


def test_cli_version_runs(capsys):
    assert main(["version"]) == 0
    assert "vine" in capsys.readouterr().out
