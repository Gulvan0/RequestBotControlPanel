from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Language(StrEnum):
    RU = "Русский"
    EN = "English"

    @classmethod
    def from_bot_api_value(cls, value: str) -> Language:
        return Language.EN if value == "eng" else Language.RU

    @classmethod
    def from_spreadsheet_value(cls, value: str) -> Language:
        return Language(value)

    def get_spreadsheet_value(self) -> str:
        return str(self)

    def get_bot_api_value(self) -> str:
        return "eng" if self == Language.EN else "rus"


@dataclass
class FormResponse:
    submission_timestamp: datetime
    language: Language
    level_id: int
    showcase_link: str | None


@dataclass
class OpenRequest:
    submission_timestamp: datetime
    language: Language
    level_name: str
    creator: str
    level_id: int
    stars: int | None
    difficulty: str
    showcase_link: str | None


class SendType(StrEnum):
    NOT_SENT = "rejected"
    STARRATE = "starrate"
    FEATURE = "feature"
    EPIC = "epic"
    LEGENDARY = "legendary"
    MYTHIC = "mythic"

    def get_apps_script_value(self) -> str:
        return str(self)

    def get_bot_api_value(self) -> str | None:
        match self:
            case SendType.STARRATE:
                return "s"
            case SendType.FEATURE:
                return "f"
            case SendType.EPIC:
                return "e"
            case SendType.MYTHIC:
                return "m"
            case SendType.LEGENDARY:
                return "l"
            case _:
                return None


@dataclass
class BroadcastInfo:
    video_id: str
    is_youtube: bool
