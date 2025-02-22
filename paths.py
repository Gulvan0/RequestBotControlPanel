from pathlib import Path

from appdirs import user_config_dir


CONFIG_DIR_PATH = Path(user_config_dir("RequestBotControlPanel"))
CONFIG_PATH = CONFIG_DIR_PATH / 'settings.json'
TOKEN_PATH = CONFIG_DIR_PATH / 'token.json'


def get_image_path(name: str) -> Path:
    return Path.cwd() / f'images/{name}.png'