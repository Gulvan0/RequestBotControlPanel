from pathlib import Path

from appdirs import user_config_dir


CONFIG_DIR_PATH = Path(user_config_dir("RequestBotControlPanel"))
CONFIG_PATH = CONFIG_DIR_PATH / 'settings.json'
TOKEN_PATH = CONFIG_DIR_PATH / 'token.json'
CLIENT_SECRET_PATH = CONFIG_DIR_PATH / 'client_secret.json'
TMP_CLIENT_SECRET_SEARCH_PATH = Path("client_secret.json")


def get_image_path(name: str) -> Path:
    return Path.cwd() / f'images/{name}.png'