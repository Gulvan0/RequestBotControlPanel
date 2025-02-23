from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, IntEnum, Enum, auto
from time import sleep

import requests
from datetime import datetime, timedelta


class Endpoint(StrEnum):
    GET_LEVELS = "http://www.boomlings.com/database/getGJLevels21.php"


class LevelFieldKey(IntEnum):
    LEVEL_ID = 1
    LEVEL_NAME = 2
    AUTHOR_PLAYER_ID = 6
    DIFFICULTY_NUMERATOR = 9
    GAME_VERSION = 13
    LENGTH = 15
    DEMON = 17
    STARS = 18
    FEATURE_SCORE = 19
    AUTO = 25
    COPIED_ID = 30
    REQUESTED_STARS = 39
    EPIC = 42
    DEMON_DIFFICULTY = 43


class LevelDifficulty(Enum):
    UNRATED = 'Unrated'
    AUTO = 'Auto'
    EASY = 'Easy'
    NORMAL = 'Normal'
    HARD = 'Hard'
    HARDER = 'Harder'
    INSANE = 'Insane'
    EASY_DEMON = 'Easy Demon'
    MEDIUM_DEMON = 'Medium Demon'
    HARD_DEMON = 'Hard Demon'
    INSANE_DEMON = 'Insane Demon'
    EXTREME_DEMON = 'Extreme Demon'


class RequestedDifficulty(Enum):
    AUTO = 'Auto'
    EASY = 'Easy'
    NORMAL = 'Normal'
    HARD = 'Hard'
    HARDER = 'Harder'
    INSANE = 'Insane'
    DEMON = 'Demon'

    @classmethod
    def from_stars(cls, requested_stars_cnt: int) -> RequestedDifficulty:
        match requested_stars_cnt:
            case 2:
                return RequestedDifficulty.EASY
            case 3:
                return RequestedDifficulty.NORMAL
            case 4 | 5:
                return RequestedDifficulty.HARD
            case 6 | 7:
                return RequestedDifficulty.HARDER
            case 8 | 9:
                return RequestedDifficulty.INSANE
            case 10:
                return RequestedDifficulty.DEMON
            case _:
                return RequestedDifficulty.AUTO


class LevelLength(IntEnum):
    TINY = 0
    SHORT = 1
    MEDIUM = 2
    LONG = 3
    XL = 4
    PLATFORMER = 5


class LevelGrade(Enum):
    UNRATED = auto()
    RATED = auto()
    FEATURED = auto()
    EPIC = auto()
    LEGENDARY = auto()
    MYTHIC = auto()


@dataclass
class Level:
    level_id: int
    name: str
    author_name: str
    difficulty: LevelDifficulty
    stars: int | None
    stars_requested: int | None
    game_version: str
    length: LevelLength
    grade: LevelGrade
    copied_level_id: int | None


class ApiWrapper:
    def __init__(self):
        self.last_api_call: datetime | None = None
        self.api_call_interval = timedelta(seconds=0.51)

    def perform_request(self, endpoint: Endpoint, data: dict) -> str | None:
        if self.last_api_call:
            time_passed = datetime.now() - self.last_api_call
            remaining_seconds = (self.api_call_interval - time_passed).total_seconds()
            if remaining_seconds > 0:
                sleep(remaining_seconds)

        data.update(secret="Wmfd2893gb7")

        response = requests.post(
            url=endpoint,
            data=data,
            headers={"User-Agent": ""}
        ).text

        self.last_api_call = datetime.now()

        if response == "-1":
            return None
        return response


API = ApiWrapper()


def _get_level_fields(level_string: str) -> dict[int, str]:
    splitted = level_string.split(":")
    return dict(zip(map(int, splitted[::2]), splitted[1::2]))


def _parse_level(level_string: str, *, player_id_to_creator_name_mapping: dict[int, str] | None = None, precalculated_author_name: str | None = None) -> Level:
    assert player_id_to_creator_name_mapping is not None or precalculated_author_name is not None

    level_fields = _get_level_fields(level_string)

    author_player_id = int(level_fields.get(LevelFieldKey.AUTHOR_PLAYER_ID))
    author_name = precalculated_author_name or player_id_to_creator_name_mapping.get(author_player_id, "Anonymous")

    if level_fields.get(LevelFieldKey.AUTO) == '1':
        difficulty = LevelDifficulty.AUTO
    elif level_fields.get(LevelFieldKey.DEMON) == '1':
        match level_fields.get(LevelFieldKey.DEMON_DIFFICULTY):
            case '3':
                difficulty = LevelDifficulty.EASY_DEMON
            case '4':
                difficulty = LevelDifficulty.MEDIUM_DEMON
            case '5':
                difficulty = LevelDifficulty.INSANE_DEMON
            case '6':
                difficulty = LevelDifficulty.EXTREME_DEMON
            case _:
                difficulty = LevelDifficulty.HARD_DEMON
    else:
        match level_fields.get(LevelFieldKey.DIFFICULTY_NUMERATOR):
            case '10':
                difficulty = LevelDifficulty.EASY
            case '20':
                difficulty = LevelDifficulty.NORMAL
            case '30':
                difficulty = LevelDifficulty.HARD
            case '40':
                difficulty = LevelDifficulty.HARDER
            case '50':
                difficulty = LevelDifficulty.INSANE
            case _:
                difficulty = LevelDifficulty.UNRATED

    game_version_number = int(level_fields[LevelFieldKey.GAME_VERSION])
    if game_version_number <= 7:
        game_version = f'1.{game_version_number - 1}'
    elif game_version_number == 10:
        game_version = '1.7'
    else:
        game_version = f'{game_version_number / 10:.1f}'

    stars = int(level_fields[LevelFieldKey.STARS]) or None
    stars_requested = int(level_fields[LevelFieldKey.REQUESTED_STARS]) or None

    if not stars:
        grade = LevelGrade.UNRATED
    elif level_fields[LevelFieldKey.FEATURE_SCORE] == '0':
        grade = LevelGrade.RATED
    else:
        match int(level_fields[LevelFieldKey.EPIC]):
            case 1:
                grade = LevelGrade.EPIC
            case 2:
                grade = LevelGrade.LEGENDARY
            case 3:
                grade = LevelGrade.MYTHIC
            case _:
                grade = LevelGrade.FEATURED

    return Level(
        level_id=int(level_fields[LevelFieldKey.LEVEL_ID]),
        name=level_fields[LevelFieldKey.LEVEL_NAME],
        author_name=author_name,
        difficulty=difficulty,
        stars=stars,
        stars_requested=stars_requested,
        game_version=game_version,
        length=LevelLength(int(level_fields[LevelFieldKey.LENGTH])),
        grade=grade,
        copied_level_id=int(level_fields[LevelFieldKey.COPIED_ID]) or None
    )


def get_levels(level_ids: list[int]) -> dict[int, Level]:
    batch_size = 10  # We can't retrieve more than 10 levels per call

    current_batch_start = 0
    total_levels = len(level_ids)

    result = {}

    while current_batch_start < total_levels:
        current_batch_ids = level_ids[current_batch_start:current_batch_start + batch_size]

        raw_response = API.perform_request(
            Endpoint.GET_LEVELS,
            dict(
                type=19,
                str=','.join(map(str, current_batch_ids))
            )
        )

        response_parts = raw_response.split("#")
        level_strings = response_parts[0].split("|")
        creator_strings = response_parts[1].split("|")

        player_id_to_creator_name_mapping = {}
        for creator_string in creator_strings:
            creator_string_parts = creator_string.split(":")
            player_id_to_creator_name_mapping[int(creator_string_parts[0])] = creator_string_parts[1]

        for level_string in level_strings:
            level = _parse_level(level_string, player_id_to_creator_name_mapping=player_id_to_creator_name_mapping)
            result[level.level_id] = level

        current_batch_start += batch_size

    return result


def get_level(level_id: int) -> Level | None:
    raw_response = API.perform_request(
        Endpoint.GET_LEVELS,
        dict(
            type=19,
            str=str(level_id)
        )
    )
    if not raw_response:
        return None

    response_parts = raw_response.split("#")
    return _parse_level(response_parts[0], precalculated_author_name=response_parts[1].split(":")[1])
