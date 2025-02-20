from __future__ import annotations

from dataclasses import dataclass, asdict, field
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
    last_stream_processed_levels: set[int] = field(default_factory=set)


    @classmethod
    def load(cls) -> Caretaker:
        if CONFIG_PATH.is_file():
            loaded_dict = json.loads(CONFIG_PATH.read_text())
            loaded_dict["last_stream_processed_levels"] = set(loaded_dict["last_stream_processed_levels"])
            return Caretaker(**loaded_dict)

        CONFIG_DIR_PATH.mkdir(parents=True, exist_ok=True)
        return Caretaker()

    def save(self):
        saved_dict = asdict(self)
        saved_dict["last_stream_processed_levels"] = list(saved_dict["last_stream_processed_levels"])
        CONFIG_PATH.write_text(json.dumps(saved_dict, ensure_ascii=False, indent=4))
