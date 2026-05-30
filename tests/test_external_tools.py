"""Unit tests for cartesapp.external_tools argument assembly and drive builders.

No Docker / cartesi-machine: the host-vs-docker dispatch is bypassed and the
subprocess calls are monkeypatched, so these assert the *exact argv* the bridge
would hand off (which is where the workdir-quote and cm-version bugs lived).
"""
import os
from types import SimpleNamespace

import pytest

import cartesapp.external_tools as et


class TestCmCliVersionBoundary:
    @pytest.mark.parametrize("ver,expected", [
        ("0.19.0", False),
        ("0.19.99", False),
        ("0.20.0", True),
        ("0.21.3", True),
    ])
    def test_data_filename_boundary(self, ver, expected):
        assert et.cm_cli_from_v020(ver) is expected


class TestParseSize:
    @pytest.mark.parametrize("inp,expected", [
        ("1kb", 1024),
        ("10mb", 10 * 2**20),
        ("2 gb", 2 * 2**30),
        ("", 0),
    ])
    def test_known_units(self, inp, expected):
        assert et.parse_size(inp) == expected

    def test_unknown_unit_raises(self):
        # documents current behavior: unrecognized units surface as KeyError
        with pytest.raises(KeyError):
            et.parse_size("10mib")


class TestBuildDriveFlashConfig:
    def test_none_builder_filename_form_pre_v020(self, tmp_path):
        src = tmp_path / "src.ext2"
        src.write_bytes(b"hello")
        fc = et.build_drive("mydrive", str(tmp_path), builder="none", filename=str(src),
                            mount="/mnt/x", shared="true", user="dapp")
        assert fc.startswith("--flash-drive=label:mydrive,filename:")
        assert ",mount:/mnt/x" in fc
        assert ",shared" in fc
        assert ",user:dapp" in fc

    def test_none_builder_data_filename_form_v020(self, tmp_path):
        src = tmp_path / "src.ext2"
        src.write_bytes(b"hello")
        fc = et.build_drive("mydrive", str(tmp_path), cm_version="0.20.0",
                            builder="none", filename=str(src))
        assert ",data_filename:" in fc
        assert ",filename:" not in fc

    def test_raw_builder_length(self, tmp_path):
        fc = et.build_drive("d", str(tmp_path), builder="raw", length="1kb")
        assert fc == "--flash-drive=label:d,length:1024"

    def test_volume_builder_returns_none(self, tmp_path):
        assert et.build_drive("d", str(tmp_path), builder="volume") is None


class TestBuildDriveEmptyRaw:
    def test_raw_returns_path_and_writes_file(self, tmp_path):
        # regression lock for bug #1: the raw branch used to fall through and raise
        path = et.build_drive_empty("data", str(tmp_path), format="raw", size="2kb")
        assert path == os.path.join(str(tmp_path), "data.raw")
        assert os.path.getsize(path) == 2048


class TestDockerRunArgs:
    def test_shape(self, monkeypatch):
        monkeypatch.setattr(et, "_current_user_name", lambda: "tester")
        monkeypatch.setattr(et, "get_sdk_image", lambda *a, **k: "sdk:test")
        args = et._docker_run_args(["echo", "hi"], datadirs=["/data"], interactive_flag="-it")
        assert args[:3] == ["docker", "run", "--rm"]
        assert "--user" in args
        assert "USER=tester" in args
        assert "-it" in args
        assert "/data:/data" in args
        i = args.index("sdk:test")
        assert args[i - 2:i] == ["--entrypoint", ""]
        assert args[i + 1:] == ["echo", "hi"]

    def test_no_interactive_flag_omitted(self, monkeypatch):
        monkeypatch.setattr(et, "_current_user_name", lambda: "tester")
        monkeypatch.setattr(et, "get_sdk_image", lambda *a, **k: "sdk:test")
        args = et._docker_run_args(["x"], datadirs=None, interactive_flag=None)
        assert "-it" not in args and "-i" not in args


class TestRunCmArgAssembly:
    def _patch(self, monkeypatch, captured):
        def fake_build_drives(base_path, cm_version=None, **config):
            captured["cm_version"] = cm_version
            return ["--flash-drive=label:app,filename:x"]
        def fake_run_cmd(args, **kwargs):
            captured["args"] = args
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        monkeypatch.setattr(et, "build_drives", fake_build_drives)
        monkeypatch.setattr(et, "get_volume_configs", lambda **c: [])
        monkeypatch.setattr(et, "run_cmd", fake_run_cmd)

    def test_workdir_unquoted_and_version_threaded(self, monkeypatch, tmp_path):
        captured = {}
        self._patch(monkeypatch, captured)
        config = {"machine": {"entrypoint": "/run", "workdir": "/myapp", "version": "0.20.0"}, "drives": {}}
        et.run_cm(base_path=str(tmp_path), **config)
        # bug #2: no literal quotes around the workdir value
        assert "--workdir=/myapp" in captured["args"]
        assert all('"' not in a for a in captured["args"])
        # bug #4: per-call version is threaded, not read from a mutated global
        assert captured["cm_version"] == "0.20.0"

    def test_cm_version_defaults_when_unset(self, monkeypatch, tmp_path):
        captured = {}
        self._patch(monkeypatch, captured)
        config = {"machine": {"entrypoint": "/run"}, "drives": {}}
        et.run_cm(base_path=str(tmp_path), **config)
        assert captured["cm_version"] == et.CARTESI_MACHINE_VERSION
