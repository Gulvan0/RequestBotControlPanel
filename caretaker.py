from __future__ import annotations

from dataclasses import dataclass, asdict, field
import json

from common_types import BroadcastInfo
from paths import CONFIG_DIR_PATH, CONFIG_PATH


START_ANNOUNCEMENT_TEMPLATE = """
<@&1145682760074276984> REQUEST STREAM!
{{video_link}}
""".strip()


END_GOODBYE_TEXT = """
Stream is over, thanks everyone!
---
Стрим окончен, всем спасибо за участие!
""".strip()


@dataclass
class Caretaker:
    api_root_url: str = ""  # TODO (iteration 17.3): Fill
    api_token: str = ""
    youtube_channel_id: str = "UChO6WUVUrzGI7iklJHYsVYw"
    twitch_login: str = "kazvixx"
    form_link: str = "https://docs.google.com/forms/d/e/1FAIpQLSdiiNCszrGo6ISM3h8tVcJFa1l9JJ97GAUqiCJn-4yP_Q5Oeg/viewform?usp=header"
    spreadsheet_link: str = "https://docs.google.com/spreadsheets/d/1o162S5-ObUH5twiYT20dVUoKfu38vW1nOZ5rHz-Y6gI/edit?gid=1210513451#gid=1210513451"
    start_announcement_text: str = START_ANNOUNCEMENT_TEMPLATE
    end_goodbye_text: str = END_GOODBYE_TEXT
    last_stream_id: str | None = None
    last_stream_is_youtube: bool = False
    last_stream_processed_levels: set[int] = field(default_factory=set)

    @classmethod
    def load(cls) -> Caretaker:
        if CONFIG_PATH.is_file():
            loaded_dict = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            loaded_dict["last_stream_processed_levels"] = set(loaded_dict.get("last_stream_processed_levels", []))
            return Caretaker(**loaded_dict)

        CONFIG_DIR_PATH.mkdir(parents=True, exist_ok=True)
        return Caretaker()

    def save(self):
        saved_dict = asdict(self)
        saved_dict["last_stream_processed_levels"] = list(saved_dict.get("last_stream_processed_levels", []))
        CONFIG_PATH.write_text(json.dumps(saved_dict, ensure_ascii=False, indent=4), encoding='utf-8')

    def get_last_broadcast_info(self) -> BroadcastInfo | None:
        return BroadcastInfo(self.last_stream_id, self.last_stream_is_youtube) if self.last_stream_id else None
