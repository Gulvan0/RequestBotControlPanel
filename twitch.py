import requests


GET_STREAM_QUERY_TEMPLATE = """
query {
  user(login: "%USERNAME%") {
    stream {
      id
    }
  }
}
"""


def get_stream_id(username: str) -> str | None:
    response = requests.post(
        url="https://gql.twitch.tv/gql",
        json=dict(
            query=GET_STREAM_QUERY_TEMPLATE.replace("%USERNAME%", username),
            variables={}
        ),
        headers={
            "client-id": "kimne78kx3ncx6brgo4mv6wki5h1ko"
        }
    ).json() or {}

    data = response.get("data") or {}
    user = data.get("user") or {}
    stream = user.get("stream") or {}
    return stream.get("id")