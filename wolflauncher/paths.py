from pathlib import Path

from .platforms import current_platform


def user_config_dir() -> Path:
    return current_platform().user_config_dir()


def user_data_dir() -> Path:
    return current_platform().user_data_dir()
