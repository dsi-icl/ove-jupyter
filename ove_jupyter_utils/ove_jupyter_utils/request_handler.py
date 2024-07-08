import base64
import typing
import uuid
import json

import requests

from .utils import Mode
from urllib.parse import quote


class RequestHandler:
    def __init__(self, mode: Mode, core: str, observatory: str, username: str, password: str):
        self.mode = mode
        self.core = core
        self.observatory = observatory
        self.username = username
        self.password = password
        self.tokens = self._get_tokens()
        self.renderer = self._get_renderer()

    def _get(self, url: str) -> typing.Any:
        return requests.get(f"{self.renderer}/{url}").json()

    def _delete(self, url: str) -> None:
        if self.mode == Mode.PRODUCTION:
            requests.delete(f"{self.renderer}/{url}")
        else:
            print(f"DELETE: {self.renderer}/{url}")

    def _get_renderer(self):
        return requests.get(f"{self.core}/core/renderer",
                            headers={"Authorization": f"Bearer {self.tokens['access']}"}).json()

    def _get_tokens(self) -> dict:
        raw = f"{self.username}:{self.password}"
        encoded = base64.b64encode(bytes(raw, "utf-8")).decode("utf-8")
        return requests.post(f"{self.core}/login",
                             headers={"Authorization": f"Basic {encoded}"}).json()

    def _post(self, url: str, data: typing.Any) -> typing.Optional[typing.Any]:
        if self.mode == Mode.PRODUCTION:
            return requests.post(f"{self.renderer}/{url}", json=data,
                                 headers={"Content-Type": "application/json"}).json()
        else:
            print(f"POST: {self.renderer}/{url} - {data}")
            return None

    def load_section(self, cell_no: int, i: int, section: dict, sections: list[dict]) -> int:
        section_id = sections.get(f"{cell_no}-{i}", None)
        if section_id is not None:
            self._delete(f"sections/{section_id['id']}")

        section_id = self._post("section", section)
        return len(sections) if section_id is None else section_id["id"]

    def get_geometry(self) -> dict:
        geometry = self._get(f"spaces/{self.observatory}/geometry")
        return geometry

    def clear_space(self) -> None:
        self._delete(f"sections?space={self.observatory}")

    def get_bounds(self):
        return requests.get(f"{self.core}/core/observatories/bounds",
                            headers={"Authorization": f"Bearer {self.tokens['access']}"}).json()[self.observatory]

    def get_controller(self, sections: list[dict], project_id: str) -> str:
        return requests.get(
            f"{self.core}/project/{project_id}/control?observatory={self.observatory}&layout={json.dumps(sections)}",
            headers={"Authorization": f"Bearer {self.tokens['access']}"}).json()
