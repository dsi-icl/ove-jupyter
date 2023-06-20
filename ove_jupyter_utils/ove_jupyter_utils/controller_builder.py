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
            f"<li><button onclick=\"changeContent('{get_app_url(section)}/control.html?oveSectionId={section['id']}')\">Cell {format_cell_name(k)} - {get_app_url(section).split('/')[-1]}</button></li>"
            for k, section in sections.items()])

    def _get_controller_start_url(self, sections: list[dict]) -> str:
        if len(sections) == 0:
            return ""
        id_, section_id = min([(k, v["id"]) for k, v in sections.items()], key=lambda x: x[1])
        return f"{sections[id_]['data']['app']['url']}/control.html?oveSectionId={section_id}"

    def _create_controller(self, sections: list[dict]) -> str:
        content = self._create_controller_nav_content(sections)
        start_url = self._get_controller_start_url(sections)
        outline = self.file_handler.read_file(f"{get_dir()}/ove_base/assets/controller_format.html")
        return outline.replace("%%content%%", content).replace("%%start_url%%", start_url)

    def generate_controller(self, uuid: str, sections: list[dict]) -> None:
        self.file_handler.to_file(self._create_controller(sections), f"{self.out_dir}/control_{uuid}.html", file_mode="w")
