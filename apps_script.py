from calendar import month
from datetime import datetime
from enum import StrEnum

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import typing as tp

from common_types import FormResponse, Language, OpenRequest


SCRIPT_ID = "AKfycby6qY02LIuIPW2NyW972Sz0AalKvyPFJfwjtmuw8dUrR8gRnIuVuTpNwhq1M_ujB5ER4w"


class AppsScriptFunction(StrEnum):
    CLOSE_FORM = "close"
    REOPEN_FORM = "reopen"
    GET_RAW_NEW_RESPONSES = "get_new_responses"
    CLEAR_NEW_RESPONSES = "clear_new_responses"
    APPEND_OPEN_REQUESTS = "append_open_requests"
    PICK_OPEN_REQUEST = "pick_open_request"
    RESOLVE_REQUEST = "resolve_request"
    CLOSE_REMAINING_OPEN_REQUESTS = "close_remaining_open"


def parse_sheet_datetime(raw: str) -> datetime:
    parts = raw.strip().split(' ')
    date = parts[0]
    time = parts[1] if len(parts) > 1 else "0:00:00"
    date_parts = date.split('-')
    time_parts = time.split(':')
    return datetime(
        year=int(date_parts[0]),
        month=int(date_parts[1]),
        day=int(date_parts[2]),
        hour=int(time_parts[0]),
        minute=int(time_parts[1]),
        second=int(time_parts[2]),
    )


def build_open_request_from_row(request_row: list) -> OpenRequest:
    return OpenRequest(
        submission_timestamp=parse_sheet_datetime(request_row[0]),
        language=Language.from_spreadsheet_value(request_row[1]),
        level_name=request_row[2],
        creator=request_row[3],
        level_id=int(request_row[4]),
        stars=int(request_row[5]) if str(request_row[5]).isdigit() else None,
        difficulty=request_row[6],
        showcase_link=request_row[7] or None if len(request_row) > 7 else None
    )


class AppsScriptApiWrapper:
    def __init__(self, creds: Credentials):
        self.service = build("script", "v1", credentials=creds)

    def execute_function(self, func: AppsScriptFunction, parameters: list[tp.Any] | None = None) -> tp.Any:
        request = dict(function=func.value)
        if parameters:
            request.update(parameters=parameters)

        try:
            response = self.service.scripts().run(scriptId=SCRIPT_ID, body=request).execute()
            if "error" in response:
                error = response["error"]["details"][0]
                print(f"Script error message: {0}.{format(error['errorMessage'])}")

                if "scriptStackTraceElements" in error:
                    print("Script error stacktrace:")
                    for trace in error["scriptStackTraceElements"]:
                        print(trace)
            else:
                print("Executed!")
                return response
        except HttpError as error:
            print(f"An error occurred: {error}")
            print(error.content)

        return None

    def get_new_responses(self) -> list[FormResponse]:
        response = self.execute_function(AppsScriptFunction.GET_RAW_NEW_RESPONSES)

        form_responses = []
        for row in response['response']['result']:
            language = Language(row[1])
            form_responses.append(FormResponse(
                submission_timestamp=datetime.strptime(row[0], '%m/%d/%Y %H:%M:%S'),
                language=language,
                level_id=int(row[2 if language == Language.EN else 4]),
                showcase_link=row[3 if language == Language.EN else 5] or None
            ))

        return form_responses

    def pick_open_request(self, first: bool) -> OpenRequest | None:
        response = self.execute_function(AppsScriptFunction.PICK_OPEN_REQUEST, [first])
        result = response['response']['result']
        return build_open_request_from_row(result[0]) if result else None

    def close_remaining_requests(self, will_be_dumped: bool) -> list[OpenRequest]:
        response = self.execute_function(AppsScriptFunction.CLOSE_REMAINING_OPEN_REQUESTS, [will_be_dumped])
        return list(map(build_open_request_from_row, response['response']['result']))
