from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import typing as tp


SCRIPT_ID = "AKfycbyWOxwe7oBOS4sdouwGaKeYOhDqikj-YGSlOE2JHmvUHWgrEKFbwKRZNAGTY4nYhKLcfg"


class AppsScriptFunction(StrEnum):
    CLOSE_FORM = "close"
    REOPEN_FORM = "reopen"
    GET_RAW_NEW_RESPONSES = "get_new_responses"
    CLEAR_NEW_RESPONSES = "clear_new_responses"
    APPEND_OPEN_REQUESTS = "append_open_requests"
    PICK_OPEN_REQUEST = "pick_open_request"
    RESOLVE_REQUEST = "resolve_request"
    CLOSE_REMAINING_OPEN_REQUESTS = "close_remaining_open"


class Language(StrEnum):
    RU = "Русский"
    EN = "English"


@dataclass
class FormResponse:
    submission_timestamp: datetime
    language: Language
    level_id: int
    showcase_link: str | None


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