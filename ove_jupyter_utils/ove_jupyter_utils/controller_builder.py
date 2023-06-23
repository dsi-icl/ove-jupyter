import json

from .file_handler import FileHandler
from .utils import get_app_url, format_cell_name, get_dir


class ControllerBuilder:
    def __init__(self, out_dir: str, file_handler: FileHandler):
        self.file_handler = file_handler
        self.out_dir = out_dir

    def _create_controller_nav_content(self, sections: list[dict]) -> str:
        if len(sections) == 0:
            return ""
        return "\n\t\t\t".join([
            f"<li><button onclick=\"changeContent({i})\">Cell {format_cell_name(k)} - {get_app_url(section).split('/')[-1]}</button></li>"
            for i, (k, section) in enumerate(sections.items())])

    def _create_controller(self, sections: list[dict], core: str, mode: str) -> str:
        content = self._create_controller_nav_content(sections)
        outline = self.file_handler.read_file(f"{get_dir()}/assets/controller_format.html")
        outline = outline.replace("%%content%%", content).replace("%%ove_core%%", core)
        if mode == "development":
            outline = outline.replace("%%sections%%", json.dumps([{"id": i, **x["data"]} for i, x in enumerate(sections.values())]))
        else:
            outline = outline.replace("%%sections%%", "[]")
        return outline

    def generate_controller(self, sections: list[dict], core: str, mode: str) -> None:
        self.file_handler.to_file(self._create_controller(sections, core, mode), f"{self.out_dir}/control.html", file_mode="w")
