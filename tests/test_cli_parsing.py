"""Unit tests for the CLI option-parsing / config-loading helpers in cartesapp.utils.

These back the de-duplicated ``key=value`` / ``drive.key=value`` / config-merge logic
that the ``create``/``deploy``/``node``/``build``/``shell``/``test`` commands share.
"""
import copy

import pytest

from cartesapp.utils import (
    parse_key_value, parse_drive_config, load_machine_drive_config,
    DEFAULT_CONFIGS, SHELL_CONFIGS,
)


class TestParseKeyValue:
    def test_basic(self):
        assert parse_key_value(["a=1", "b=2"]) == {"a": "1", "b": "2"}

    def test_none_returns_empty(self):
        assert parse_key_value(None) == {}

    def test_value_may_contain_equals(self):
        assert parse_key_value(["url=http://x?a=b"]) == {"url": "http://x?a=b"}

    def test_empty_value(self):
        assert parse_key_value(["k="]) == {"k": ""}

    def test_missing_equals_raises_clear_error(self):
        with pytest.raises(ValueError, match="key=value"):
            parse_key_value(["novalue"])

    def test_last_wins_on_duplicate(self):
        assert parse_key_value(["a=1", "a=2"]) == {"a": "2"}


class TestParseDriveConfig:
    def test_basic(self):
        assert parse_drive_config(["app.size=128Mb"]) == {"app": {"size": "128Mb"}}

    def test_none_returns_empty(self):
        assert parse_drive_config(None) == {}

    def test_groups_keys_per_drive(self):
        parsed = parse_drive_config(["app.size=1", "app.format=ext2", "data.size=2"])
        assert parsed == {"app": {"size": "1", "format": "ext2"}, "data": {"size": "2"}}

    def test_missing_dot_raises(self):
        with pytest.raises(ValueError, match="drive.key=value"):
            parse_drive_config(["size=1"])

    def test_missing_equals_raises(self):
        with pytest.raises(ValueError, match="drive.key=value"):
            parse_drive_config(["app.size"])


class TestLoadMachineDriveConfig:
    def test_no_file_uses_defaults(self, tmp_path):
        cfg = load_machine_drive_config(str(tmp_path / "absent.toml"), DEFAULT_CONFIGS)
        assert cfg["machine"]["entrypoint"] == DEFAULT_CONFIGS["machine"]["entrypoint"]
        assert cfg["drives"]["app"]["builder"] == "directory"

    def test_does_not_mutate_or_alias_defaults(self, tmp_path):
        before = copy.deepcopy(DEFAULT_CONFIGS)
        cfg = load_machine_drive_config(str(tmp_path / "absent.toml"), DEFAULT_CONFIGS)
        cfg["drives"]["app"]["directory"] = "/somewhere/else"
        cfg["machine"]["entrypoint"] = "changed"
        assert DEFAULT_CONFIGS == before  # the shared default dict is untouched

    def test_base_path_applied(self, tmp_path):
        cfg = load_machine_drive_config(None, SHELL_CONFIGS, base_path="/custom")
        assert cfg["base_path"] == "/custom"

    def test_overrides_merge_into_machine_and_drives(self, tmp_path):
        cfg = load_machine_drive_config(
            str(tmp_path / "absent.toml"), DEFAULT_CONFIGS,
            machine_overrides={"ram_length": "128Mi"},
            drive_overrides={"app": {"format": "ext2"}},
        )
        assert cfg["machine"]["ram_length"] == "128Mi"
        # override merges into, does not replace, the default app drive
        assert cfg["drives"]["app"]["format"] == "ext2"
        assert cfg["drives"]["app"]["builder"] == "directory"

    def test_file_drives_without_use_default_are_kept_standalone(self, tmp_path):
        toml = tmp_path / "cartesi.toml"
        toml.write_text(
            '[drives.custom]\nbuilder = "directory"\ndirectory = "./x"\nformat = "ext2"\n'
        )
        cfg = load_machine_drive_config(str(toml), DEFAULT_CONFIGS)
        # no use_default_drives -> file drives are used as-is (no default 'app'/'root' merged)
        assert "custom" in cfg["drives"]
        assert "app" not in cfg["drives"]
        # machine still defaulted since file had no [machine]
        assert cfg["machine"]["entrypoint"] == DEFAULT_CONFIGS["machine"]["entrypoint"]

    def test_use_default_drives_merges_defaults_with_file(self, tmp_path):
        toml = tmp_path / "cartesi.toml"
        toml.write_text(
            'use_default_drives = "true"\n\n'
            '[drives.data]\nbuilder = "empty"\nformat = "ext2"\nsize = "32Mb"\n'
        )
        cfg = load_machine_drive_config(str(toml), DEFAULT_CONFIGS)
        # defaults present AND the file's extra drive merged in
        assert cfg["drives"]["app"]["builder"] == "directory"
        assert cfg["drives"]["root"]["builder"] == "none"
        assert cfg["drives"]["data"]["builder"] == "empty"
