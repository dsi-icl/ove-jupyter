import typing
import requests

from .utils import Mode


class RequestHandler:
    def __init__(self, mode: Mode, host: str):
        self.mode = mode
        self.host = host

    def _get(self, url: str) -> typing.Any:
        return requests.get(f"{self.host}/{url}").json()

    def _delete(self, url: str) -> None:
        if self.mode == Mode.PRODUCTION:
            requests.delete(f"{self.host}/{url}")
        else:
            print(f"DELETE: {self.host}/{url}")

    def _post(self, url: str, data: typing.Any) -> typing.Optional[typing.Any]:
        if self.mode == Mode.PRODUCTION:
            return requests.post(f"{self.host}/{url}", json=data).json()
        else:
            print(f"POST: {self.host}/{url} - {data}")
            return None

    def load_section(self, cell_no: int, i: int, section: dict, sections: list[dict]) -> int:
        section_id = sections.get(f"{cell_no}-{i}", None)
        if section_id is not None:
            self._delete(f"sections/{section_id['id']}")

        section_id = self._post("section", section)
        return len(sections) if section_id is None else section_id["id"]

    def get_geometry(self, space: str) -> dict:
        geometry = self._get(f"spaces/{space}/geometry")
        return geometry

    def clear_space(self, space: str) -> None:
        self._delete(f"sections?space={space}")
