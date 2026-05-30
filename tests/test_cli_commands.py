"""End-to-end CLI wiring tests via Typer's CliRunner.

The external_tools entry points (``run_cm``/``run_node``/``build_drives``) are
monkeypatched on the ``cli`` module so nothing actually builds; the tests assert
the merged config dict each command hands off, covering the option->config wiring
and ``--config``/``--env``/``--volume``/``--machine-config``/``--drive-config`` flags.
"""
import os

import pytest
from typer.testing import CliRunner

from cartesapp import cli

runner = CliRunner()


def _absent_toml(tmp_path):
    return str(tmp_path / "none.toml")


def test_build_merges_machine_and_drive_overrides(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(cli, "run_cm", lambda **p: captured.update(p))
    result = runner.invoke(cli.app, [
        "build", "--config-file", _absent_toml(tmp_path), "--base-path", str(tmp_path),
        "--machine-config", "ram_length=128Mi", "--drive-config", "app.format=ext2",
    ])
    assert result.exit_code == 0, result.output
    assert captured["store"] is True
    assert captured["base_path"] == str(tmp_path)
    assert captured["machine"]["ram_length"] == "128Mi"
    assert captured["drives"]["app"]["format"] == "ext2"
    assert captured["drives"]["app"]["builder"] == "directory"  # default preserved


def test_build_drives_only_exits_without_snapshot(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(cli, "build_drives", lambda **p: captured.update(p) or [])
    monkeypatch.setattr(cli, "run_cm", lambda **p: pytest.fail("snapshot must not run"))
    result = runner.invoke(cli.app, [
        "build", "--drives-only", "--config-file", _absent_toml(tmp_path),
        "--base-path", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert captured["base_path"] == str(tmp_path)
    assert "drives" in captured


def test_node_wires_env_volume_and_config(monkeypatch, tmp_path):
    os.makedirs(tmp_path / "image")  # pre-existing snapshot -> skip auto-build
    captured = {}
    monkeypatch.setattr(cli, "run_node", lambda **kw: captured.update(kw))
    monkeypatch.setattr(cli, "run_cm", lambda **p: pytest.fail("should not rebuild"))
    result = runner.invoke(cli.app, [
        "node", "--config-file", _absent_toml(tmp_path), "--base-path", str(tmp_path),
        "--env", "FOO=bar", "--volume", "/h=/c", "--config", "port=9000",
    ])
    assert result.exit_code == 0, result.output
    assert captured["envs"]["FOO"] == "bar"
    assert captured["volumes"]["/h"] == "/c"
    assert captured["port"] == "9000"
    assert captured["workdir"] == str(tmp_path)


def test_deploy_sets_cmd_and_register_false(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(cli, "run_node", lambda **kw: captured.update(kw))
    result = runner.invoke(cli.app, [
        "deploy", "--config-file", _absent_toml(tmp_path),
        "--env", "FOO=bar", "--config", "APP_NAME=myapp",
    ])
    assert result.exit_code == 0, result.output
    assert captured["envs"]["EXTRA_ARGS"] == "--register=false"
    assert captured["envs"]["FOO"] == "bar"
    assert captured["cmd"] == "/deploy.sh /mnt/apps/myapp"


def test_shell_sets_interactive_and_entrypoint(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(cli, "run_cm", lambda **p: captured.update(p))
    result = runner.invoke(cli.app, [
        "shell", "--config-file", _absent_toml(tmp_path), "--base-path", str(tmp_path),
        "--entrypoint", "bash",
    ])
    assert result.exit_code == 0, result.output
    assert captured["interactive"] is True
    assert captured["machine"]["entrypoint"] == "bash"
    assert captured["machine"]["network"] == "true"  # from SHELL_CONFIGS


def test_bad_config_option_surfaces_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "run_cm", lambda **p: None)
    result = runner.invoke(cli.app, [
        "build", "--config-file", _absent_toml(tmp_path), "--base-path", str(tmp_path),
        "--machine-config", "novalue",
    ])
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
