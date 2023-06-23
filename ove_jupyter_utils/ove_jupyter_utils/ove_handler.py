import re

from argparse import ArgumentParser, Namespace

from .geometry import Geometry
from .data_type import DataType
from .file_handler import FileHandler
from .asset_handler import AssetHandler
from .request_handler import RequestHandler
from .section_builder import SectionBuilder
from .layout_validator import LayoutValidator
from .output_formatter import OutputFormatter
from .controller_builder import ControllerBuilder
from .utils import load_base_config, Mode, get_dir


class OVEHandler:
    def __init__(self):
        self.config = {}

    def load_config(self, config: Namespace) -> dict:
        self.config = load_base_config(config)
        ove_handler = RequestHandler(self.config["mode"], self.config["core"])
        self.config["geometry"] = ove_handler.get_geometry(self.config["space"])
        ove_handler.clear_space(self.config["space"])
        FileHandler().load_dir(self.config["out"], self.config["remove"])

    def tee(self, cell_config: Namespace, outputs: list[list]) -> list[dict]:
        validator = LayoutValidator()
        file_handler = FileHandler()
        asset_handler = AssetHandler(self.config["out"], f"{self.config['host']}/ove-jupyter/static", file_handler)
        output_formatter = OutputFormatter(file_handler, asset_handler)

        display_type = validator.validate(cell_config)
        geometry = Geometry(cell_config, display_type, self.config["geometry"], self.config["rows"], self.config["cols"], cell_config.split)

        controller_urls = []

        for output_idx, output in enumerate(outputs):
            idx, data_type, data, metadata = output
            data_type = DataType(data_type)
            section = SectionBuilder(
                self.config["core"], asset_handler, output_formatter).build_section(data, geometry, cell_config.cell_no, output_idx, len(outputs), self.config["space"], data_type, metadata)

            section_id = RequestHandler(self.config["mode"], self.config["core"]).load_section(
                cell_config.cell_no, output_idx, section, self.config["sections"])
            self.config["sections"][f"{cell_config.cell_no}-{output_idx}"] = {
                "id": section_id,
                "data": section
            }

            if not self.config["multi_controller"]:
                controller_urls.append(
                    {"idx": idx, "url": f"{section['app']['url']}/control.html?oveSectionId={section_id}"})

        project = output_formatter.format_project(self.config["sections"], self.config["space"])
        file_handler.write_json(project, filename=f"{self.config['out']}/project.json")

        if self.config["mode"] == Mode.DEVELOPMENT:
            overview = output_formatter.format_overview(self.config["space"],
                                                        f"{self.config['host']}/ove-jupyter/static",
                                                        self.config["core"])
            file_handler.to_file(overview, filename=f"{self.config['out']}/overview.html", file_mode="w")

        if self.config["multi_controller"]:
            ControllerBuilder(self.config["out"], file_handler).generate_controller(self.config["sections"], self.config["core"], self.config["mode"].value)

        return controller_urls
