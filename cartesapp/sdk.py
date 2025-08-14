import os

from cartesapp.utils import read_config_file

SDK_IMAGE = "ghcr.io/prototyp3-dev/cartesapp"

def get_sdk_version():
    from importlib.metadata import version
    return version('cartesapp')

def get_sdk_image(config_file: str | None = None):
    config_sdk = None
    config = read_config_file(os.getenv('CARTESAPP_CONFIG_FILE') or config_file)
    if config is not None:
        config_sdk = config.get('sdk')
    if config_sdk is not None:
        return config_sdk
    return f"{SDK_IMAGE}:{get_sdk_version()}"
