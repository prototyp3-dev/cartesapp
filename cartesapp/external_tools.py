import os
import subprocess
from typing import List, Tuple
from shutil import which

import logging

from cartesapp.sdk import get_sdk_image
from cartesapp.utils import str2bool, get_dir_size

LOGGER = logging.getLogger(__name__)

DOCKER_CMD = ["docker","run","--rm"]

BLANK_APP_ADDRESS="0xE34467a44bD506b0bCc4474eb19617b156D93c29"
AUTHORITY_ADDRESS="0xb3B509f8669b193654e5417D2fE19a3436283642"

BLOCK_SIZE = 4096
IMAGE_DIR = "image"

def is_tool(name):
    return which(name) is not None

def run_cmd(args: List[str], force_docker: bool = False, force_host: bool = False, datadirs: List[str] | None = None, **kwargs) -> subprocess.CompletedProcess[str]:
    if force_docker and force_host: raise Exception(f"Incompatible params {force_docker=}, {force_host=}")
    if not force_docker:
        if is_tool(args[0]):
            LOGGER.debug(f"Running: {' '.join(args)}")
            return subprocess.run(args,**kwargs)
        msg = f"Command {args[0]} not found. Falling back to use docker"
        if force_host: raise Exception(msg)
        LOGGER.debug(msg)
    if not is_tool(DOCKER_CMD[0]):
        msg = "Could find tool or docker to run command"
        LOGGER.error(msg)
        raise Exception(msg)
    docker_args = DOCKER_CMD.copy()
    name = subprocess.run("whoami", capture_output=True).stdout.decode().strip()
    docker_args.extend(["--env",f"USER={name}","--env",f"GROUP={os.getgid()}","--env",f"UID={os.getuid()}","--env",f"GID={os.getgid()}"])
    docker_args.extend(["-w",os.getcwd()])
    if datadirs is not None:
        for datadir in datadirs:
            docker_datadir = datadir if os.path.isabs(datadir) else f"{os.getcwd()}:{datadir}"
            docker_args.extend(["-v",f"{datadir}:{docker_datadir}"])
    docker_args.append(get_sdk_image())
    docker_args.extend(args)
    LOGGER.debug(f"Running: {' '.join(docker_args)}")
    return subprocess.run(docker_args,**kwargs)

def popen_cmd(args: List[str], force_docker: bool = False, force_host: bool = False, datadirs: List[str] | None = None, **kwargs):
    if force_docker and force_host: raise Exception(f"Incompatible params {force_docker=}, {force_host=}")
    if not force_docker:
        if is_tool(args[0]):
            LOGGER.debug(f"Running popen: {' '.join(args)}")
            proc = subprocess.Popen(args,**kwargs)
            return proc
        msg = f"Command {args[0]} not found. Falling back to use docker"
        if force_host: raise Exception(msg)
        LOGGER.debug(msg)
    LOGGER.debug(f"Command {args[0]} not found. Falling back to use docker")
    if not is_tool(DOCKER_CMD[0]):
        msg = "Could find tool or docker to run command"
        LOGGER.error(msg)
        raise Exception(msg)
    docker_args = DOCKER_CMD.copy()
    name = subprocess.run("whoami", capture_output=True).stdout.decode().strip()
    docker_args.extend(["--env",f"USER={name}","--env",f"GROUP={os.getgid()}","--env",f"UID={os.getuid()}","--env",f"GID={os.getgid()}"])
    docker_args.extend(["-w",os.getcwd()])
    if datadirs is not None:
        for datadir in datadirs:
            docker_datadir = datadir if os.path.isabs(datadir) else f"{os.getcwd()}:{datadir}"
            docker_args.extend(["-v",f"{datadir}:{docker_datadir}"])
    docker_args.append(get_sdk_image())
    docker_args.extend(args)
    LOGGER.debug(f"Running popen: {' '.join(docker_args)}")
    proc = subprocess.Popen(docker_args,**kwargs)
    return proc

def get_rootfs(rootfs: str = '.cartesi/root.ext2'):
    cm_rootfs = os.path.join(os.path.abspath('.'),rootfs) if not os.path.isabs(rootfs) else rootfs
    base_path = os.path.dirname(cm_rootfs)
    if not os.path.isdir(base_path): os.makedirs(base_path)
    args = ["cp","/usr/share/cartesi-machine/images/rootfs.ext2",cm_rootfs]
    run_cmd(args, force_docker=True, datadirs=[base_path])



def run_node(workdir: str = '.cartesi',**kwargs):
    import subprocess

    base_path = os.path.join(os.path.abspath('.'),workdir) if not os.path.isabs(workdir) else workdir
    imagedir = os.path.join(base_path,IMAGE_DIR)
    if not os.path.isdir(imagedir):
        raise Exception("Couldn't find image, please build it first")

    sdk_image_name = get_sdk_image()

    name = subprocess.run("whoami", capture_output=True).stdout.decode().strip()
    su = ["--env",f"USER={name}","--env",f"GROUP={os.getgid()}","--env",f"UID={os.getuid()}","--env",f"GID={os.getgid()}"]
    app_name = "app"
    if kwargs.get('APP_NAME') is not None:
        app_name = kwargs.get('APP_NAME')
    args = ["docker","run","--rm",
        f"--volume={imagedir}:/mnt/apps/{app_name}","--env",f"APP_NAME={app_name}"]

    app_address = kwargs.get('application-address')
    if app_address is None:
        app_address = BLANK_APP_ADDRESS
    consensus_address = kwargs.get('consensus-address')
    if consensus_address is None:
        consensus_address = AUTHORITY_ADDRESS

    if kwargs.get('rpc-url') is not None or kwargs.get('rpc-ws') is not None:
        if kwargs.get('cmd') is None and (kwargs.get('rpc-url') is None or kwargs.get('rpc-ws') is None):
            raise Exception("Should define both rpc-url and rpc-ws")
        kwargs['enable-hash-check' ] = 'true'
        if kwargs.get('rpc-url') is not None:
            args.extend(["--env",f"CARTESI_BLOCKCHAIN_HTTP_ENDPOINT={kwargs.get('rpc-url')}"])
        if kwargs.get('rpc-ws') is not None:
            args.extend(["--env",f"CARTESI_BLOCKCHAIN_WS_ENDPOINT={kwargs.get('rpc-ws')}"])

    if kwargs.get('enable-hash-check') is not None:
        hash_check = kwargs.get('enable-hash-check')
        args.extend(["--env",f"CARTESI_FEATURE_MACHINE_HASH_CHECK_ENABLED={hash_check}"])
        hash_check_enabled = str2bool(hash_check)
        if hash_check_enabled and kwargs.get('application-address') is None:
            app_address = None
        if hash_check_enabled and kwargs.get('consensus-address') is None:
            consensus_address = None
    else:
        args.extend(["--env","CARTESI_FEATURE_MACHINE_HASH_CHECK_ENABLED=false"])

    if app_address is not None:
        args.extend(["--env",f"APPLICATION_ADDRESS={app_address}"])
    if consensus_address is not None:
        args.extend(["--env",f"CONSENSUS_ADDRESS={consensus_address}"])

    args.extend(su)

    if kwargs.get('port') is not None:
        args.extend(["-p",f"{kwargs.get('port')}:80"])
    else:
        args.extend(["-p","8080:80"])
    if kwargs.get('db-port') is not None:
        args.extend(["-p",f"{kwargs.get('db-port')}:5432"])
    else:
        args.extend(["-p","5432:5432"])
    if kwargs.get('rpc-url') is None:
        if kwargs.get('anvil-port') is not None:
            args.extend(["-p",f"{kwargs.get('anvil-port')}:8545"])
        else:
            args.extend(["-p","8545:8545"])
    if kwargs.get('add-host') is not None:
        args.append(f"--add-host={kwargs.get('add-host')}")
    if kwargs.get('name') is not None:
        args.append(f"--name={kwargs.get('name')}")

    envs = kwargs.get('envs')
    if envs is not None and type(envs) == type({}):
        for k,v in envs.items():
            args.extend(["--env",f"{k}={v}"])

    volumes = kwargs.get('volumes')
    if volumes is not None and type(volumes) == type({}):
        for k,v in volumes.items():
            args.extend(["--volume",f"{k}:{v}"])

    args.append(sdk_image_name)

    if kwargs.get('cmd') is not None:
        args.extend(str(kwargs.get('cmd')).split())
    if kwargs.get('only-args'):
        return args
    try:
        # print(" ".join(args))
        node = subprocess.Popen(args, start_new_session=True)
        output, errors = node.communicate()
        if node.returncode > 0:
            raise Exception(f"Error running reader node: {str(node.returncode)}")
    except KeyboardInterrupt:
        node.terminate()
    finally:
        node.wait()


UNITS = {"b": 1, "kb": 2**10, "mb": 2**20, "gb": 2**30, "tb": 2**40}

def parse_size(size):
    import re
    m = re.compile(r'(\d+)\s*(\S+)').match(size)
    if m is None: return 0
    number = m.group(1)
    unit = m.group(2)
    return int(float(number)*UNITS[unit.lower()])


def get_drive_format(filename: str) -> str:
    name, drive_format = os.path.splitext(filename)
    if drive_format == '.ext2': return 'ext2'
    if drive_format == '.sqfs': return 'sqfs'
    raise Exception(f"File {filename} format not supported")

def genext2fs(drive_name:str, destination:str,
        str_size: str|None = None,directory: str|None = None,
        extra_size: str|None = None, tarball: str|None = None) -> str:
    import math,shutil
    dest_filename = os.path.join(destination,f"{drive_name}.ext2")
    if os.path.isfile(dest_filename): os.remove(dest_filename)
    data_flash_args = ["xgenext2fs","--faketime","--allow-holes","--block-size",str(BLOCK_SIZE),]
    if str_size is not None:
        total_size = parse_size(str_size)
        blocks = math.ceil(total_size/BLOCK_SIZE)
        data_flash_args.extend(["--size-in-blocks",str(blocks)])
    if directory is not None:
        dest_dir = os.path.join(destination,drive_name)
        if not os.path.isdir(dest_dir) or directory != dest_dir:
            dest_dir = shutil.copytree(
                directory,
                dest_dir,
                ignore=shutil.ignore_patterns('.*'))
        data_flash_args.extend(["--root",dest_dir])
    if extra_size is not None:
        total_extra_size = parse_size(extra_size)
        extra_blocks = math.ceil(total_extra_size/BLOCK_SIZE)
        data_flash_args.extend(["--readjustment",f"+{extra_blocks}"])
    if tarball is not None:
        dest_tarball = os.path.join(destination,f"{drive_name}.tar")
        if not os.path.isfile(dest_tarball) or tarball != dest_tarball:
            shutil.copyfile(tarball,dest_tarball)
        data_flash_args.extend(["--tarball",dest_tarball])
    data_flash_args.append(dest_filename)
    result = run_cmd(data_flash_args,datadirs=[destination],capture_output=True,text=True)
    LOGGER.debug(result.stdout)
    if result.returncode != 0:
        msg = f"Error seting cm up (creating data flash drive): {str(result.stderr)}"
        LOGGER.error(msg)
        raise Exception(msg)
    if directory is not None and directory != os.path.join(destination,drive_name): shutil.rmtree(os.path.join(destination,drive_name))
    if tarball is not None and tarball != os.path.join(destination,f"{drive_name}.tar"): os.remove(os.path.join(destination,f"{drive_name}.tar"))
    return dest_filename

def squashfs(drive_name:str, destination:str,directory: str|None = None,tarball: str|None = None,exact_size: str|None = None) -> str:
    import shutil
    dest_filename = os.path.join(destination,f"{drive_name}.sqfs")
    if os.path.isfile(dest_filename): os.remove(dest_filename)
    data_flash_args = ["mksquashfs"]
    if directory is not None:
        dest_dir = os.path.join(destination,drive_name)
        if not os.path.isdir(dest_dir) or directory != dest_dir:
            dest_dir = shutil.copytree(
                directory,
                os.path.join(destination,drive_name),
                ignore=shutil.ignore_patterns('.*'))
        data_flash_args.extend([dest_dir,dest_filename])
        if exact_size is not None:
            int_exact_size = parse_size(exact_size)
            dirsize = get_dir_size(dest_dir)
            if dirsize > int_exact_size:
                raise Exception(f"Directory size exceeds maximum allowed size of {int_exact_size} bytes")
            with open(os.path.join(dest_dir,"buffer.bin"),'wb') as f:
                chunk_size = 4096  # You can adjust this chunk size
                bytes_written = 0
                size_in_bytes = int_exact_size-dirsize
                while bytes_written < size_in_bytes:
                    bytes_to_write = min(chunk_size, size_in_bytes - bytes_written)
                    random_bytes = os.urandom(bytes_to_write)
                    f.write(random_bytes)
                    bytes_written += bytes_to_write
            dirsize = get_dir_size(dest_dir)
            data_flash_args.extend(["-Xcompression-level", "1","-no-duplicates"])
    if tarball is not None:
        dest_tarball = os.path.join(destination,f"{drive_name}.tar")
        if not os.path.isfile(dest_tarball) or not tarball != dest_tarball:
            shutil.copyfile(tarball,dest_tarball)
        data_flash_args.extend(["-",dest_filename,"-tar",dest_tarball])
    data_flash_args.extend(["-noI","-noD","-noF","-noX","-wildcards","-e","... .*"]) #"-e","... __pycache__"
    result = run_cmd(data_flash_args,datadirs=[destination],capture_output=True,text=True)
    LOGGER.debug(result.stdout)
    if result.returncode != 0:
        msg = f"Error seting cm up (creating data flash drive): {str(result.stderr)}"
        LOGGER.error(msg)
        raise Exception(msg)
    if directory is not None and directory != os.path.join(destination,drive_name): shutil.rmtree(os.path.join(destination,drive_name))
    if tarball is not None and tarball != os.path.join(destination,f"{drive_name}.tar"): os.remove(os.path.join(destination,f"{drive_name}.tar"))
    return dest_filename


def build_drive_none(drive_name,destination, **drive) -> str:
    import filecmp, shutil
    filename = drive.get('filename')
    if filename is None:
        raise Exception("parameter 'filename' not defined")
    drive_format = get_drive_format(filename)
    dest_filename = os.path.join(destination,f"{drive_name}.{drive_format}")
    if str2bool(drive.get('avoid-overwriting')) and os.path.isfile(dest_filename): return dest_filename
    if drive_name == 'root':
        if not os.path.isfile(filename): get_rootfs(filename)
    if not os.path.isfile(dest_filename) or not filecmp.cmp(filename, dest_filename, shallow=True):
        shutil.copyfile(filename, dest_filename)
    return dest_filename

def build_drive_empty(drive_name,destination, **drive) -> str:
    drive_format = drive.get('format')
    dest_filename = os.path.join(destination,f"{drive_name}.{drive_format}")
    if str2bool(drive.get('avoid-overwriting')) and os.path.isfile(dest_filename): return dest_filename
    if drive_format == 'ext2': # create with xgenext2fs
        return genext2fs(
            drive_name,
            destination,
            str_size=drive.get('size')
        )
    if drive_format == 'raw': # zeroed binary file
        if drive.get('size') is None: raise Exception(f"Drive {drive_name} size not defined")
        total_size = parse_size(drive.get('size'))
        dest_filename = os.path.join(destination,f"{drive_name}.{drive_format}")
        with open(dest_filename, 'wb') as f: f.write(b'\0' * total_size)
    raise Exception(f"Empty drive {drive_name} format {drive_format} not supported")

def build_drive_directory(drive_name,destination, **drive) -> str:
    drive_format = drive.get('format')
    if drive.get('directory') is None: raise Exception(f"Drive {drive_name} directory not defined")
    dest_filename = os.path.join(destination,f"{drive_name}.{drive_format}")
    if str2bool(drive.get('avoid-overwriting')) and os.path.isfile(dest_filename): return dest_filename
    if drive_format == 'ext2': # create with xgenext2fs
        return genext2fs(
            drive_name,
            destination,
            directory=drive.get('directory'),
            extra_size=drive.get('extraSize'),
            str_size=drive.get('size')
        )
    if drive_format == 'sqfs': # create with mksquashfs
        return squashfs(
            drive_name,
            destination,
            directory=drive.get('directory'),
            exact_size=drive.get('size')
        )
    raise Exception(f"Directory drive {drive_name} format {drive_format} not supported")

def build_drive_tar(drive_name,destination, **drive) -> str:
    drive_format = drive.get('format')
    if drive.get('filename') is None: raise Exception(f"Drive {drive_name} filename not defined")
    dest_filename = os.path.join(destination,f"{drive_name}.{drive_format}")
    if str2bool(drive.get('avoid-overwriting')) and os.path.isfile(dest_filename): return dest_filename
    if drive_format == 'ext2': # create with xgenext2fs
        return genext2fs(
            drive_name,
            destination,
            tarball=drive.get('filename'),
            extra_size=drive.get('extraSize'),
        )
    if drive_format == 'sqfs': # create with mksquashfs
        return squashfs(
            drive_name,
            destination,
            tarball=drive.get('filename'),
        )
    raise Exception(f"Tar drive {drive_name} format {drive_format} not supported")

def build_drive_docker(drive_name,destination, **drive) -> str | None:
    dockerfile = drive.get('dockerfile')
    drive_format = drive.get('format')
    if dockerfile is None: dockerfile = 'Dockerfile'
    if drive_format not in ['ext2','sqfs']: raise Exception(f"Docker drive {drive_name} format {drive_format} not supported")
    dest_filename = os.path.join(destination,f"{drive_name}.{drive_format}")
    if str2bool(drive.get('avoid-overwriting')) and os.path.isfile(dest_filename): return dest_filename
    filename = None
    tarball = os.path.join(destination,f"{drive_name}.tar")

    # create tarball
    docker_tar_args = ["docker","build","--platform=linux/riscv64","-f",dockerfile,"--output",f"type=tar,dest={tarball}"]
    if drive.get('target') is not None:
        docker_tar_args.extend(["--target",drive.get('target')])
    build_args = drive.get('buildArgs')
    if build_args is not None and type(build_args) == type([]):
        for build_arg in build_args:
            docker_tar_args.extend(["--build-arg",build_arg])
    docker_envs = drive.get('envs')
    if docker_envs is not None and type(docker_envs) == type([]):
        for docker_env in docker_envs:
            docker_tar_args.extend(["--env",docker_env])
    docker_tar_args.append(".")

    if os.getenv('NON_INTERACTIVE_DOCKER') == '1':
        proc = run_cmd(docker_tar_args,datadirs=[destination],force_host=True,capture_output=True,text=True)
        LOGGER.debug(proc.stdout)
    else:
        proc = popen_cmd(docker_tar_args,datadirs=[destination],force_host=True)
        proc.wait()

    if proc.returncode != 0:
        msg = f"Error setting up Docker image: {str(proc.stderr)}"
        LOGGER.error(msg)
        raise Exception(msg)

    if drive_format == 'ext2': # create with xgenext2fs
        filename = genext2fs(
            drive_name,
            destination,
            tarball=tarball,
            extra_size=drive.get('extraSize'),
        )
    elif drive_format == 'sqfs': # create with mksquashfs
        filename = squashfs(
            drive_name,
            destination,
            tarball=tarball,
        )
    os.remove(tarball)
    return filename

def build_drives(base_path: str = '.cartesi', **config) -> List[str]:
    drives = config.get('drives')
    drives_flash_configs = []
    if drives is None or type(drives) != type({}): return drives_flash_configs

    for drive_name,drive_config in drives.items():
        drive = drives.get(drive_name)
        if drive is None or type(drive) != type({}):
            LOGGER.warning(f"No config for drive {drive_name}. Ignoring.")
            continue
        drive_config = build_drive(drive_name,base_path, **drive)
        if drive_config is None: continue
        drives_flash_configs.append(drive_config)
    return drives_flash_configs

def build_drive(drive_name,destination, **drive) -> str | None:
    drive_builder = drive.get('builder')
    filename = ""
    if drive_builder == 'none':
        filename = build_drive_none(drive_name,destination, **drive)
    elif drive_builder == 'empty':
        filename = build_drive_empty(drive_name,destination, **drive)
    elif drive_builder == 'directory':
        filename = build_drive_directory(drive_name,destination, **drive)
    elif drive_builder == 'tar':
        filename = build_drive_tar(drive_name,destination, **drive)
    elif drive_builder == 'docker':
        filename = build_drive_docker(drive_name,destination, **drive)
    elif drive_builder == 'volume':
        return None
    else:
        raise Exception(f"Unrecognized drive builder {drive_builder}")
    flash_config = f"--flash-drive=label:{drive_name},filename:{filename}"
    if drive.get('mount'): flash_config += f",mount:{drive.get('mount')}"
    if drive.get('shared'): flash_config += ",shared"
    if drive.get('user') is not None: flash_config += f",user:{drive.get('user')}"
    return flash_config

def build_volume_config(drive_name,destination, **drive) -> Tuple[str,str]:
    directory = drive.get('directory')
    if directory is None: raise Exception(f"Drive {drive_name} directory not defined")
    abs_directory = os.path.join(os.path.abspath('.'),directory) if not os.path.isabs(directory) else directory
    mountpoint = drive.get('mount') if drive.get('mount') else f"/mnt/{drive_name}"
    volume_config = f"--volume={abs_directory}:{mountpoint}"
    return (abs_directory,volume_config)

def get_volume_configs(drive_path, **config) -> List[Tuple[str,str]]:
    drives = config.get('drives')
    volume_configs = []
    if drives is None or type(drives) != type({}): return volume_configs

    for drive_name,drive_config in drives.items():
        drive = drives.get(drive_name)
        if drive is None or type(drive) != type({}):
            continue
        drive_builder = drive.get('builder')
        if drive_builder != 'volume': continue
        volume_config = build_volume_config(drive_name,drive_path, **drive)
        volume_configs.append(volume_config)
    return volume_configs

def run_cm(base_path: str = '.cartesi', **config):
    import shutil
    machine_config = config.get("machine")
    if machine_config is None or type(machine_config) != type({}): raise Exception("Machine config not defined")
    entrypoint = machine_config.get("entrypoint")
    if entrypoint is None or type(entrypoint) != type(""): raise Exception("Entrypoint not defined")

    if not os.path.isdir(base_path): os.makedirs(base_path)

    drives_configs = build_drives(base_path, **config)
    volume_config_tuples = get_volume_configs(base_path, **config)

    volume_configs = []
    datadirs = [base_path]
    for vconf in volume_config_tuples:
        datadirs.append(vconf[0])
        volume_configs.append(vconf[1])

    cm_args = []
    cm_args.append('cartesi-machine')
    # cm_args.append("--assert-rolling-template")
    cm_args.extend(drives_configs)
    cm_args.extend(volume_configs)

    workdir = machine_config.get("workdir")
    if workdir is None:
        workdir = "/mnt/app"
    cm_args.append(f'--workdir="{workdir}"')
    if config.get('store'):
        imagedir = os.path.join(base_path,IMAGE_DIR)
        if os.path.isdir(imagedir): shutil.rmtree(imagedir)
        cm_args.append(f"--store={imagedir}")

    if config.get('interactive'):
        cm_args.append("-it")
    if str2bool(machine_config.get("assert-rolling-template")):
        cm_args.append("--assert-rolling-template")
    if str2bool(machine_config.get("network")):
        cm_args.append("--network")
    if str2bool(machine_config.get("initial-hash")):
        cm_args.append("--initial-hash")
    if str2bool(machine_config.get("final-hash")):
        cm_args.append("--final-hash")
    if str2bool(machine_config.get("skip-root-hash-check")):
        cm_args.append("--skip-root-hash-check")
    if str2bool(machine_config.get("skip-root-hash-store")):
        cm_args.append("--skip-root-hash-store")
    if str2bool(machine_config.get("no-rollup")):
        cm_args.append("--no-rollup")
    if str2bool(machine_config.get("no-bootargs")):
        cm_args.append("--no-bootargs")
    if machine_config.get("ram-image") is not None:
        cm_args.append(f"--ram-image={machine_config.get('ram-image')}")
    if machine_config.get("ram-length") is not None:
        cm_args.append(f"--ram-length={machine_config.get('ram-length')}")
    if machine_config.get("max-mcycle") is not None:
        cm_args.append(f"--max-mcycle={machine_config.get('max-mcycle')}")
    if machine_config.get("user") is not None:
        cm_args.append(f"--user={machine_config.get('user')}")

    init_cmds = machine_config.get('init')
    if init_cmds is not None and type(init_cmds) == type([]):
        for init_cmd in init_cmds:
            cm_args.append(f"-append-init={init_cmd}")
    bootargs = machine_config.get('envs')
    if bootargs is not None and type(bootargs) == type([]):
        for bootarg in bootargs:
            cm_args.append(f"-append-bootargs={bootarg}")
    machine_envs = machine_config.get('envs')
    if machine_envs is not None and type(machine_envs) == type([]):
        for machine_env in machine_envs:
            cm_args.append(f"-e={machine_env}")
    cm_args.extend(["--"])
    machine_envs = machine_config.get('envs')
    if machine_envs is not None and type(machine_envs) == type([]):
        for machine_env in machine_envs:
            cm_args.append(f"-e={machine_env}")
    cm_args.extend(machine_config.get("entrypoint").split())

    # print(" ".join(cm_args))
    if config.get('interactive'):
        stdout, stderr = popen_cmd(cm_args,datadirs=datadirs).communicate()
        if stdout:
            LOGGER.debug(stdout)
        if stderr:
            msg = f"Error seting cm up: {str(stderr)}"
            LOGGER.error(msg)
            raise Exception(msg)
    else:
        result = run_cmd(cm_args,datadirs=datadirs, capture_output=True,text=True)
        LOGGER.debug(result.stdout)

        if result.returncode != 0:
            msg = f"Error seting cm up: {str(result.stderr)}"
            LOGGER.error(msg)
            raise Exception(msg)
