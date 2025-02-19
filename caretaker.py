from __future__ import annotations

from dataclasses import dataclass, asdict
from appdirs import user_config_dir
from pathlib import Path
import json


CONFIG_DIR_PATH = Path(user_config_dir("RequestBotControlPanel"))
CONFIG_PATH = CONFIG_DIR_PATH / 'settings.json'


@dataclass
class Caretaker:
    api_root_url: str = ""  # TODO: Fill
    api_token: str = ""
    channel_id: str = "UChO6WUVUrzGI7iklJHYsVYw"
    form_link: str = ""  # TODO: Fill
    spreadsheet_link: str = ""  # TODO: Fill
    start_announcement_text: str = ""  # TODO: Fill
    end_goodbye_text: str = ""  # TODO: Fill
    last_stream_id: str | None = None


    @classmethod
    def load(cls) -> Caretaker:
        if CONFIG_PATH.is_file():
            return Caretaker(**json.loads(CONFIG_PATH.read_text()))

        CONFIG_DIR_PATH.mkdir(parents=True, exist_ok=True)
        return Caretaker()

    def save(self):
        CONFIG_PATH.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=4))
