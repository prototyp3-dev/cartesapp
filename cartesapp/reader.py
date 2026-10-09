"""Snapshot-watching *reader* mode for the cartesapp query-server.

Goal: replace the slow/expensive Cartesi machine *inspect* path. The node
advances state only (``snapshot_policy: EVERY_INPUT``) and writes a fresh
machine snapshot per advance to a directory, each named
``{app}_epoch{N}_input{M}`` and containing ``config.json`` plus one ``.bin`` per
flash drive. This reader watches that directory and, on each new snapshot,
extracts the configured drive(s) (where the app's committed state lives) and
(re)starts the in-process :mod:`cartesapp.query_server` bound to the extracted
data -- serving queries with no machine.

Drive handling (per ``[drives.<name>].format``):
- ``ext2``  -> ``debugfs rdump`` the filesystem out (no mount/privileges)
- ``sqfs``  -> ``unsquashfs``
- ``raw``   -> copy the ``.bin`` verbatim as the single file the app reads
              (e.g. the cartesapplib ledger state)

All external tools run through :func:`cartesapp.external_tools.run_cmd`, which
falls back to the SDK Docker image when a tool is missing on the host.
"""

import os
import re
import glob
import json
import time
import shutil
import logging
from multiprocessing import Process

from cartesapp.external_tools import run_cmd

LOGGER = logging.getLogger(__name__)

# First flash-drive nibble: root=0x80.., app=0x90.., then user drives in
# [drives.*] order (matches dev_node.py drive_file_name_patterns counter).
FIRST_DRIVE_NIBBLE = 8
DRIVE_ADDR_STEP = 1 << 52

_SNAPSHOT_RE = re.compile(r".*_epoch(\d+)_input(\d+)$")


def drive_start_address(drive_name, drives_cfg):
    """Physical start address of ``drive_name`` given the ordered drives config."""
    names = list(drives_cfg.keys())
    if drive_name not in names:
        raise Exception(f"Drive '{drive_name}' not found in drives config {names}")
    return (FIRST_DRIVE_NIBBLE + names.index(drive_name)) * DRIVE_ADDR_STEP


def drive_format(drive_cfg):
    """Normalize a drive's filesystem format to one of: ext2, sqfs, raw."""
    fmt = (drive_cfg.get("format") or "").lower()
    if fmt in ("raw",) or drive_cfg.get("builder") == "raw":
        return "raw"
    if fmt in ("sqfs", "squashfs"):
        return "sqfs"
    if fmt in ("ext2", ""):
        # builder 'none' infers from filename; default to ext2 otherwise
        fn = drive_cfg.get("filename", "")
        if fn.endswith(".sqfs"):
            return "sqfs"
        return "ext2"
    return fmt


def find_latest_snapshot(watch_dir, app_name):
    """Return the path of the newest *complete* ``{app}_epoch*_input*`` snapshot.

    Newest = max (epoch, input). A snapshot is considered complete once its
    ``config.json`` is present (the node writes it last).
    """
    best = None
    best_key = None
    for name in glob.iglob(f"{app_name}_epoch*_input*", root_dir=watch_dir):
        d = os.path.join(watch_dir, name)
        if not os.path.isdir(d):
            continue
        m = _SNAPSHOT_RE.match(name)
        if m is None:
            continue
        if not os.path.isfile(os.path.join(d, "config.json")):
            continue
        key = (int(m.group(1)), int(m.group(2)))
        if best_key is None or key > best_key:
            best_key = key
            best = d
    return best


def locate_drive_bin(snapshot_dir, drive_name, drives_cfg):
    """Path to the ``.bin`` backing the named drive inside ``snapshot_dir``."""
    start = drive_start_address(drive_name, drives_cfg)
    with open(os.path.join(snapshot_dir, "config.json")) as f:
        cfg = json.load(f)["config"]
    for entry in cfg.get("flash_drive", []):
        if entry.get("start") == start:
            data_filename = entry["backing_store"]["data_filename"]
            return os.path.normpath(os.path.join(snapshot_dir, data_filename))
    raise Exception(
        f"No flash drive at 0x{start:x} for '{drive_name}' in {snapshot_dir}/config.json")


def extract_drive(bin_path, fmt, dest):
    """Open a drive image and place its contents at ``dest``.

    For ext2/sqfs ``dest`` is a directory populated with the filesystem tree;
    for raw ``dest`` is the destination file (the drive copied verbatim).
    """
    bin_dir = os.path.dirname(os.path.abspath(bin_path))
    if fmt == "raw":
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        shutil.copyfile(bin_path, dest)
        return dest

    # filesystem formats -> clean dest dir then extract into it
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)

    if fmt == "ext2":
        # rdump the root directory tree out of the ext2 image (read-only,
        # no loop mount). debugfs writes into dest preserving the tree.
        args = ["debugfs", "-R", f"rdump / {dest}", bin_path]
    elif fmt == "sqfs":
        args = ["unsquashfs", "-f", "-d", dest, bin_path]
    else:
        raise Exception(f"Unsupported drive format: {fmt}")

    result = run_cmd(args, datadirs=[bin_dir, dest], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to extract drive ({fmt}): {result.stderr or result.stdout}")
    return dest


def _serve(modules, host, port, storage_override):
    """Child-process entry point: run the query-server bound to extracted data."""
    from cartesapp.manager import cartesapp_run_query_server
    cartesapp_run_query_server(
        modules=modules, host=host, port=port, storage_override=storage_override)


class _Reader:
    """Watches a snapshot dir and keeps a single query-server child in sync."""

    def __init__(self, watch_dir, drives, drives_cfg, modules, host, port,
                 app_name="app", storage_drive=None, work_dir="_reader",
                 debounce=2.0):
        self.watch_dir = watch_dir
        self.drives = drives                  # ordered list of watched drive names
        self.drives_cfg = drives_cfg
        self.modules = modules
        self.host = host
        self.port = port
        self.app_name = app_name
        self.storage_drive = storage_drive    # which watched drive holds storage.db
        self.work_dir = os.path.abspath(work_dir)
        self.debounce = debounce
        self.child = None
        self._last_snapshot = None

    def _dest_for(self, drive_name, fmt):
        base = os.path.join(self.work_dir, drive_name)
        return base if fmt != "raw" else f"{base}.raw"

    def refresh(self):
        """Extract drives from the latest snapshot and (re)spawn the child."""
        snapshot = find_latest_snapshot(self.watch_dir, self.app_name)
        if snapshot is None:
            LOGGER.info("No complete snapshot yet in %s", self.watch_dir)
            return False
        if snapshot == self._last_snapshot and self.child is not None and self.child.is_alive():
            return False
        LOGGER.info("Loading snapshot %s", os.path.basename(snapshot))

        storage_override = None
        raw_files = {}
        for drive_name in self.drives:
            drive_cfg = self.drives_cfg.get(drive_name, {})
            fmt = drive_format(drive_cfg)
            bin_path = locate_drive_bin(snapshot, drive_name, self.drives_cfg)
            dest = self._dest_for(drive_name, fmt)
            extract_drive(bin_path, fmt, dest)
            LOGGER.info("Extracted drive '%s' (%s) -> %s", drive_name, fmt, dest)
            if fmt == "raw":
                raw_files[drive_name] = dest
                # Expose raw drive paths to the app via env (e.g. cartesapplib
                # ledger reads $LEDGER_FILE). Generic, app-agnostic.
                os.environ[f"CARTESAPP_RAW_{drive_name.upper()}"] = dest
            elif drive_name == self.storage_drive:
                storage_override = dest

        self._restart_child(storage_override)
        self._last_snapshot = snapshot
        return True

    def _restart_child(self, storage_override):
        if self.child is not None and self.child.is_alive():
            LOGGER.info("Stopping current query-server (snapshot swap)")
            self.child.terminate()
            self.child.join()
        self.child = Process(
            target=_serve,
            args=(self.modules, self.host, self.port, storage_override),
            daemon=True)
        self.child.start()
        LOGGER.info("query-server (pid %s) serving on %s:%s%s",
                    self.child.pid, self.host, self.port,
                    f" storage={storage_override}" if storage_override else "")


def run_reader(watch_dir, drives, drives_cfg, modules, host="0.0.0.0", port=8090,
               app_name="app", storage_drive=None, work_dir="_reader"):
    """Watch ``watch_dir`` for new node snapshots and serve queries from them."""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    if not os.path.isdir(watch_dir):
        raise Exception(f"Watch directory does not exist: {watch_dir}")

    reader = _Reader(watch_dir, drives, drives_cfg, modules, host, port,
                     app_name=app_name, storage_drive=storage_drive, work_dir=work_dir)

    # Initial serve from whatever snapshot already exists.
    reader.refresh()

    pending = {"at": 0.0}

    class _Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            # debounce: a snapshot is many file writes; coalesce.
            pending["at"] = time.time() + reader.debounce

    observer = Observer()
    observer.schedule(_Handler(), watch_dir, recursive=True)
    observer.start()
    LOGGER.info("Watching %s for new '%s' snapshots", watch_dir, app_name)
    print(f"cartesapp reader watching {watch_dir} (drives={drives}) -> query-server on {host}:{port}")
    try:
        while True:
            time.sleep(1)
            if pending["at"] and time.time() >= pending["at"]:
                pending["at"] = 0.0
                try:
                    reader.refresh()
                except Exception:
                    LOGGER.exception("Failed to refresh from new snapshot")
    except KeyboardInterrupt:
        LOGGER.info("Shutting down reader")
    finally:
        observer.stop()
        observer.join()
        if reader.child is not None and reader.child.is_alive():
            reader.child.terminate()
            reader.child.join()
