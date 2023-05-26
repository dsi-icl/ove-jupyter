from ove.utils import Mode
from ove.request_handler import RequestHandler


class OVEHandler:
    def __init__(self, mode: Mode, host: str):
        self.request_handler = RequestHandler(mode, host)

    def load_section(self, cell_no: int, i: int, section: dict, sections: list[dict]) -> int:
        section_id = sections.get(f"{cell_no}-{i}", None)
        if section_id is not None:
            self.request_handler.delete(f"sections/{section_id['id']}")

        section_id = self.request_handler.post("section", section)
        return len(sections) if section_id is None else section_id["id"]

    def get_geometry(self, space: str) -> dict:
        geometry = self.request_handler.get(f"spaces/{space}/geometry")
        return geometry

    def clear_space(self, space: str) -> None:
        self.request_handler.delete(f"sections?space={space}")
