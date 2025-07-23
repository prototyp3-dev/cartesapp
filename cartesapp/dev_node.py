import os
import shutil
import tempfile
import glob
from multiprocessing import Process
from typing import Dict, Any

from cartesapp.external_tools import run_node, run_cm, run_cmd, popen_cmd, build_drives
# from cartesapp.manager import cartesapp_run
from cartesapp.utils import get_dir_size

import logging

LOGGER = logging.getLogger(__name__)

# TODO: review how control cartesapp
# run node in docker
# when there is change, disable, get data drive, rebuild, push snapshot, enable

entrypoint_file = """#!/bin/sh
app_drive=%s
pmem_file=pmem%i
workdir="%s"
entrypoint_cmd(){
  %s
}
while : ; do
  echo "Initializing Dapp"
  cd $workdir
  entrypoint_cmd || echo 'Error running app'
  echo "Restarting..."
  echo "  unmounting App drive"
  cd /
  umount /mnt/$app_drive
  echo "  mounting App drive"
  mount /dev/$pmem_file /mnt/$app_drive
  echo "  app drive mounted"
done
"""

BYTES_MB = 1024 * 1024
BYTES_MIN_DIV = BYTES_MB * 16
REENABLE_MIN_WAIT_TIME = 3

class CMSnapshot():
    """Cartesi Machine Rollup Node behavior for using in test suite"""
    tmpdir = tempfile.TemporaryDirectory() # delete=False)
    config: Dict[str,Any] = {}

    def __init__(self, **config):
        super().__init__()
        original_base_path = config.get('base_path','.cartesi')

        self.testdir = self.tmpdir.name

        self.imagedir = os.path.join(self.testdir,"image")
        self.workdir = os.path.join(self.testdir,"work")

        self.config |= {'app_file_system_name': 'app'}
        self.config |= config
        self.config["store"] = True
        self.config["base_path"] = self.testdir
        self.config["machine"]["user"] = "root"

        self.drive_file_name_patterns: Dict[str,str] = {}

        self.setup_cm(original_base_path)

    def setup_cm(self,original_base_path: str) -> str:
        import re
        drives = self.config.get('drives')
        if drives is None or type(drives) != type({}):
            raise Exception("Invalid drives configuration")
        found_root_fs = False
        found_app_fs = False
        drive_counter = 8
        pmem_counter = 0
        app_pmem = None
        for drive_name,drive_config in drives.items():
            found_file = None
            filename = f"{drive_name}.ext2"
            filepath = os.path.join(original_base_path,filename)
            if os.path.isfile(filepath):
                found_file = filepath
                shutil.copyfile(filepath, os.path.join(self.config["base_path"], filename))
            filename = f"{drive_name}.sqfs"
            filepath = os.path.join(original_base_path,filename)
            if os.path.isfile(filepath):
                found_file = filepath
                shutil.copyfile(filepath, os.path.join(self.config["base_path"], filename))
            if drive_name == self.config.get('app_file_system_name'):
                found_app_fs = True
                app_pmem = pmem_counter

                drive_size = "128Mb"
                if drive_config.get('builder') == 'directory':
                    dir_size = get_dir_size(drive_config.get('directory'),['.'])
                    divs = dir_size * 1.1 // BYTES_MIN_DIV + 1
                    drive_size = f"{int((divs*BYTES_MIN_DIV)//BYTES_MB)}Mb"
                elif found_file is not None:
                    fsize = os.path.getsize(found_file)
                    divs = fsize * 1.1 // BYTES_MIN_DIV + 1
                    drive_size = f"{divs*BYTES_MIN_DIV}Mb"

                self.config["drives"][drive_name]["size"] = drive_size
                # self.config["drives"][drive_name]["format"] = "ext2"
                # self.config["drives"][drive_name]["user"] = "dapp"
            elif drive_name == 'root':
                found_root_fs = True
            self.drive_file_name_patterns[drive_name] = "%0.3x0000000000000-*.bin" % drive_counter
            drive_counter += 1
            pmem_counter += 1

        if not found_root_fs:
            raise Exception("No root filesystem found")
        if not found_app_fs:
            raise Exception("No app filesystem found")

        machine_config = self.config.get("machine") or {}
        workdir = machine_config.get("workdir")
        if workdir is None:
            workdir = "/mnt/app"
        original_entrypoint_cmd = machine_config.get("entrypoint") or "rollup-init /usr/local/bin/run_cartesapp"
        r = re.match(r"((?:(?!rollup-init).)*)(?:rollup-init)?\s((?:--verbose\s|--address\s[^\s]*\s|--dapp\s[^\s]*\s)*)(.*)", original_entrypoint_cmd)
        if r is None:
            raise Exception("Invalid entrypoint command")
        entrypoint_cmd = f"{r.group(1)} {r.group(3)}"
        os.makedirs(os.path.join(self.testdir, "entrypoint"))
        with open(os.path.join(self.testdir, "entrypoint", "entrypoint.sh"), "w") as f:
            f.write(entrypoint_file % (
                self.config.get('app_file_system_name'),
                app_pmem,
                workdir,
                entrypoint_cmd))
        os.chmod(os.path.join(self.testdir, "entrypoint", "entrypoint.sh"), 0o755)
        self.config["drives"]["entrypoint"] = {
            "builder": "directory",
            "directory":os.path.join(self.testdir, "entrypoint"),
            "format":"sqfs",
            "avoid-overwrite": 'false'
        }

        rollups_init_str = "rollup-init"
        if rollups_init_str not in original_entrypoint_cmd:
            rollups_init_str = ""

        self.config["machine"]["entrypoint"] = f"{rollups_init_str} /mnt/entrypoint/entrypoint.sh"
        self.config["machine"]["workdir"] = "/"

        run_cm(**self.config)
        return self.imagedir

    def replace_app_drive(self,new_snapshot_dir: str) -> str:

        # step 1: rebuild app drive
        params: Dict[str,Any] = {} | self.config
        drives = params.get('drives')
        if drives is None or type(drives) != type({}):
            raise Exception("Invalid drives configuration")

        app_file_system_name = params.get('app_file_system_name')
        if app_file_system_name is None:
            raise Exception("No app filesystem name specified")

        if os.path.exists(self.workdir): shutil.rmtree(self.workdir)
        os.makedirs(self.workdir)
        appfile = None
        for drive_name,drive_config in drives.items():
            if drive_name == app_file_system_name:
                drive_config['avoid-overwrite'] = 'false'
                curr_ext = ""
                for f in glob.iglob(f'{drive_name}.sqfs',root_dir=self.testdir):
                    curr_ext = os.path.splitext(f)[1]
                    break
                if curr_ext == "":
                    raise Exception(f"No {drive_name} filesystem found")
                appfile = os.path.join(self.testdir,f"{drive_name}{curr_ext}")
            else:
                drive_config['avoid-overwrite'] = 'true'

        if appfile is None:
            raise Exception(f"App filesystem not found")

        build_drives(**params)

        # step 2: replace app drive

        input_filename = os.path.join(self.workdir,"input-%i.bin")
        output_filename = os.path.join(self.workdir,"input-%i-output-%o.bin")
        report_filename = os.path.join(self.workdir,"input-%i-report-%o.bin")
        outputs_root_hash = os.path.join(self.workdir,"input-%i-output-hashes-root-hash.bin")

        #   Create dummy input file
        with open(input_filename % 0,'wb') as f:
            pass
        cm_args = []
        cm_args.append('cartesi-machine')
        cm_args.append(f"--load={new_snapshot_dir}")

        final_image_path = os.path.join(self.workdir,"image")
        cm_args.append(f"--store={final_image_path}")

        app_file_pattern = self.drive_file_name_patterns[app_file_system_name]
        app_file_address = app_file_pattern.split('-')[0]
        app_file_size = os.stat(appfile).st_size
        cm_args.append(f"--replace-flash-drive=filename:{appfile},start:0x{app_file_address},length:{hex(app_file_size)}")
        cm_args.append(f"--cmio-advance-state=input:{input_filename},output:{output_filename}," +
            f"report:{report_filename},output_hashes_root_hash:{outputs_root_hash}," +
            "input_index_begin:0,input_index_end:1")
        cm_args.append("--no-rollback")

        #   run cm command
        result = run_cmd(cm_args,datadirs=[self.workdir], capture_output=True,text=True)
        LOGGER.debug(result.stdout)

        if result.returncode != 0:
            msg = f"Error seting cm up: {str(result.stderr)}"
            LOGGER.error(msg)
            raise Exception(msg)

        return final_image_path

def run_dev_node(cfile,node_configs,watch_patterns=['*.py'],watch_path='.'):
    import subprocess, time
    from multiprocessing import Event
    from watchdog.observers import Observer
    from watchdog.events import PatternMatchingEventHandler
    import uuid

    class ReloadCartesappEventHandler(PatternMatchingEventHandler):
        def __init__(self, reload_event):
            super().__init__(patterns=watch_patterns)
            self.reload_event = reload_event
        def on_modified(self, event):
            self.reload_event.set()
        def on_deleted(self, event):
            self.reload_event.set()
        def on_moved(self, event):
            self.reload_event.set()

    path = watch_path

    observer = Observer()
    reload_event = Event()

    container_name = f"cartesapp-dev-node-{uuid.uuid4().hex[:8]}"
    app_name = "app"
    if node_configs.get('APP_NAME') is not None:
        app_name = node_configs.get('APP_NAME')

    run_configs = {
        "reload_event": reload_event,
        "config": cfile,
        "delay_restart_time":5,
        "container_name": container_name,
        "app_name": app_name
    }
    if node_configs.get('delay_restart_time') is not None:
        run_configs['delay_restart_time'] = node_configs.get('delay_restart_time')

    LOGGER.info("Building snapshot image")
    cs = CartesappSnapshotBuilder(**run_configs)
    event_handler = ReloadCartesappEventHandler(reload_event)

    observer.schedule(event_handler, path, recursive=True)

    logging.getLogger("watchdog").setLevel(logging.WARNING)

    node_configs['only-args'] = True
    node_configs['workdir'] = cs.cm.testdir
    node_configs['name'] = container_name
    if node_configs.get('envs') is None:
        node_configs['envs'] = {}
    if node_configs.get('volumes') is None:
        node_configs['volumes'] = {}

    tmpdirname = os.path.basename(cs.cm.testdir)
    local_snapshots_dir = os.path.join(cs.cm.testdir, "snapshots")
    snapshots_dir = os.path.join(os.path.abspath(os.sep),"mnt", tmpdirname, "snapshots")
    node_configs['envs']['CARTESI_SNAPSHOTS_DIR'] = snapshots_dir
    node_configs['volumes'][local_snapshots_dir] = snapshots_dir

    if not os.path.isdir(local_snapshots_dir): os.makedirs(local_snapshots_dir)
    os.chmod(cs.cm.testdir, 0o777)

    node_args = run_node(**node_configs)

    if node_args is None or len(node_args) == 0:
        raise Exception("Failed to get dev node args")

    try:
        LOGGER.info("Starting Observer")
        observer.start()
        LOGGER.info("Starting Node")
        node = subprocess.Popen(node_args, start_new_session=True)
        LOGGER.info("Starting Snapshot Updater")
        cs.start()
        output, errors = node.communicate()
        if node.returncode > 0:
            raise Exception(f"Error running dev node: {str(node.returncode)}")
    except KeyboardInterrupt:
        observer.stop()
        node.terminate()
        cs.terminate()
    finally:
        node.wait()
        cs.join()
        observer.join()


class CartesappSnapshotBuilder(Process):
    def __init__(self, reload_event, config, container_name, app_name, delay_restart_time=10,reset=True,):
        super().__init__()
        self.delay_restart_time = delay_restart_time
        self.reload_event = reload_event
        self.reset = reset
        self.container_name = container_name
        self.app_name = app_name
        self.cm = CMSnapshot(**config)
        self.snapshots_dir = os.path.join(self.cm.testdir, "snapshots")
    def run(self):
        import time
        while True:
            time.sleep(1)
            if self.reload_event.is_set():
                LOGGER.info("Detected changes in app")
                while self.reload_event.is_set():
                    self.reload_event.clear()
                    time.sleep(self.delay_restart_time)
                # copy file from container
                app_snapshot_dir = None
                for f in glob.iglob(f"{self.app_name}_epoch*_input*",root_dir=self.snapshots_dir):
                    d = os.path.join(self.snapshots_dir,f)
                    if os.path.isdir(d):
                        app_snapshot_dir = d
                        break
                if app_snapshot_dir is None:
                    LOGGER.info("No snapshot found")
                    app_snapshot_dir = self.cm.imagedir
                LOGGER.info("Disabling application")
                t_disable = time.time()
                popen_cmd(
                    ["docker", "exec", self.container_name,"cartesi-rollups-cli","app","status",self.app_name,"disabled"],
                    force_host=True).wait()
                LOGGER.info("Rebuilding snapshot")
                rebuilt_dir = self.cm.replace_app_drive(app_snapshot_dir)
                LOGGER.info("Copying built snapshot with new code to container snapshot")
                for filename in os.listdir(rebuilt_dir):
                    source_path = os.path.join(rebuilt_dir, filename)
                    destination_path = os.path.join(app_snapshot_dir, filename)
                    if os.path.isfile(source_path):
                        if os.path.isfile(destination_path):
                            os.remove(destination_path)
                        shutil.copy2(source_path, destination_path)
                LOGGER.info("Re-enabling application")
                t_enable = time.time()
                if t_enable - t_disable < REENABLE_MIN_WAIT_TIME: # wait at least REENABLE_MIN_WAIT_TIME seconds
                    time.sleep(REENABLE_MIN_WAIT_TIME - (t_enable - t_disable))
                popen_cmd(
                    ["docker", "exec", self.container_name,"cartesi-rollups-cli","app","status",self.app_name,"enabled"],
                    force_host=True).wait()
                LOGGER.info("Clearing event")
                self.reload_event.clear()
