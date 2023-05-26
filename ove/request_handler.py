import typing
import requests

from ove.utils import Mode


class RequestHandler:
    def __init__(self, mode: Mode, host: str):
        self.mode = mode
        self.host = host

    def get(self, url: str) -> typing.Any:
        return requests.get(f"{self.host}/{url}").json()

    def delete(self, url: str) -> None:
        if self.mode == Mode.PRODUCTION:
            requests.delete(f"{self.host}/{url}")
        else:
            print(f"DELETE: {self.host}/{url}")

    def post(self, url: str, data: typing.Any) -> typing.Optional[typing.Any]:
        if self.mode == Mode.PRODUCTION:
            return requests.post(f"{self.host}/{url}", json=data).json()
        else:
            print(f"POST: {self.host}/{url} - {data}")
            return None
