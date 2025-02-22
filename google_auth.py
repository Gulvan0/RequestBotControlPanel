import google.auth.exceptions
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from paths import TOKEN_PATH


AUTH_SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.force-ssl',
    'https://www.googleapis.com/auth/forms',
    'https://www.googleapis.com/auth/spreadsheets',
]


def get_credentials(client_secret_path: str) -> Credentials:
    creds = None

    if TOKEN_PATH.is_file():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), AUTH_SCOPES)
            creds.refresh(Request())
        except google.auth.exceptions.RefreshError as error:
            creds = None
            print(f'An error occurred: {error}')

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, AUTH_SCOPES)
            creds = flow.run_local_server()
        TOKEN_PATH.write_text(creds.to_json())

    return creds