import googleapiclient.discovery
import googleapiclient.errors

from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError


class YoutubeApiWrapper:
    def __init__(self, creds: Credentials):
        self.youtube = googleapiclient.discovery.build(
            serviceName="youtube",
            version="v3",
            credentials=creds
        )

    def get_live_stream_video_id(self, channel_id: str) -> str | None:
        request = self.youtube.search().list(
            part="snippet",
            channelId=channel_id,
            order="date",
            maxResults=50
        )

        try:
            response = request.execute()
        except HttpError:
            return None

        for item in response.get('items', []):
            if item.get('snippet', {}).get('liveBroadcastContent') == 'live':
                return item['id']['videoId']

        return None

    def get_live_chat_id(self, video_id: str) -> str | None:
        request = self.youtube.videos().list(
            part="liveStreamingDetails",
            id=video_id
        )
        response = request.execute()

        return response.get('items', [{}])[0].get('liveStreamingDetails', {}).get('activeLiveChatId')

    def post_message_to_live_chat(self, live_chat_id: str, message_text: str) -> None:
        request = self.youtube.liveChatMessages().insert(
            part="snippet",
            body=dict(
                snippet=dict(
                    liveChatId=live_chat_id,
                    type="textMessageEvent",
                    textMessageDetails=dict(
                        messageText=message_text
                    )
                )
            )
        )
        request.execute()
