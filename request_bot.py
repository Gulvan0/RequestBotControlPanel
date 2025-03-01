from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import requests
from pydantic import BaseModel

from common_types import OpenRequest, SendType


class RequestBotApiEndpoint(StrEnum):
    SEND_STREAM_START_MESSAGE = "/message/stream_start"
    SEND_STREAM_END_MESSAGE = "/message/stream_end"
    RESOLVE_REQUEST = "/request/resolve"
    PRE_APPROVE_REQUEST = "/request/preapprove"
    CREATE_REQUEST = "/request/create"
    CREATE_REQUEST_BATCH = "/request/create_batch"
    GET_RANDOM_REQUEST = "/request/random"
    GET_OLDEST_REQUEST = "/request/oldest"


class Request(BaseModel):
    id: int
    level_id: int
    language: str
    level_name: str | None
    yt_link: str | None
    additional_comment: str | None
    request_author: str
    is_author_user_id: bool
    details_message_id: int | None
    details_message_channel_id: int | None
    resolution_message_id: int | None
    resolution_message_channel_id: int | None
    created_at: datetime
    requested_at: datetime | None


def construct_request_creation_payload(request: OpenRequest, placeholder_yt_link: str) -> dict:
    return dict(
        level_id=request.level_id,
        creator_name=request.creator,
        language=request.language.get_bot_api_value(),
        showcase_yt_link=request.showcase_link or placeholder_yt_link
    )


def construct_request_resolution_payload(request_id: int, sent_for: SendType, stream_link: str | None) -> dict:
    return dict(
        request_id=request_id,
        sent_for=sent_for.get_bot_api_value(),
        stream_link=stream_link
    )


def construct_request_pre_approval_payload(request_id: int) -> dict:
    return dict(request_id=request_id)


Json = list | dict | int | float | bool | str | None


@dataclass
class RequestBotApiWrapper:
    root_url: str
    token: str

    def _get_url(self, endpoint: RequestBotApiEndpoint) -> str:
        return self.root_url.removesuffix("/") + endpoint

    def _get_headers(self) -> dict[str, str]:
        return {"x-key": self.token}

    def post(self, endpoint: RequestBotApiEndpoint, payload: dict | list) -> Json:
        return requests.post(
            url=self._get_url(endpoint),
            json=payload,
            headers=self._get_headers()
        ).json()

    def get(self, endpoint: RequestBotApiEndpoint) -> Json:
        return requests.get(
            url=self._get_url(endpoint),
            headers=self._get_headers()
        ).json()

    def pick_request(self, oldest: bool) -> Request | None:
        raw_request = self.get(RequestBotApiEndpoint.GET_OLDEST_REQUEST if oldest else RequestBotApiEndpoint.GET_RANDOM_REQUEST)
        if not raw_request:
            return None
        return Request.model_validate(raw_request)