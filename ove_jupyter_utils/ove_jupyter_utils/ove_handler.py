import re
import uuid

from argparse import ArgumentParser, Namespace

from .geometry import Geometry
from .data_type import DataType
from .file_handler import FileHandler
from .asset_handler import AssetHandler
from .request_handler import RequestHandler
from .section_builder import SectionBuilder
from .layout_validator import LayoutValidator
from .output_formatter import OutputFormatter
from .utils import load_base_config, Mode, get_dir


class OVEHandler:
    def __init__(self):
        self.config = {}

    def load_config(self, config: Namespace) -> dict:
        self.config = load_base_config(config)
        self.handler = RequestHandler(self.config["mode"], self.config["core"], self.config["observatory"],
                                      self.config["username"], self.config["password"])
        self.config["geometry"] = self.handler.get_geometry()
        self.config["bounds"] = self.handler.get_bounds()
        self.config["renderer"] = self.handler.renderer
        self.config["project_id"] = str(uuid.uuid4()).replace("-", "")
        self.handler.clear_space()
        FileHandler().load_dir(self.config["out"], self.config["remove"])

    def tee(self, cell_config: Namespace, outputs: list[list]) -> list[dict]:
        validator = LayoutValidator()
        file_handler = FileHandler()
        out = self.config["out"]
        static = f"{self.config['host']}/ove-jupyter/static"
        asset_handler = AssetHandler(out, static, file_handler)
        output_formatter = OutputFormatter(file_handler, asset_handler)

        display_type = validator.validate(cell_config)
        geometry = Geometry(cell_config, display_type, self.config["geometry"], self.config["bounds"], len(outputs))

        controller_urls = []

        for output_idx, output in enumerate(outputs):
            idx, data_type, data, metadata = output
            data_type = DataType(data_type)
            section_builder = SectionBuilder(self.config["renderer"], asset_handler, output_formatter)
            layout = section_builder.build_section(data, geometry, self.config["geometry"], cell_config.cell_no,
                                                   output_idx, data_type, metadata, self.config["project_id"])
            section = section_builder.convert_section(layout, self.config["geometry"], self.config["observatory"],
                                                      data_type)

            section_id = self.handler.load_section(cell_config.cell_no, output_idx, section, self.config["sections"])
            self.config["sections"][f"{cell_config.cell_no}-{output_idx}"] = {
                "id": section_id,
                "data": layout
            }

            if not self.config["multi_controller"]:
                controller_urls.append(
                    {"idx": idx, "url": f"{section['app']['url']}/control.html?oveSectionId={section_id}"})

        if self.config["mode"] == Mode.DEVELOPMENT:
            overview = output_formatter.format_overview(self.config["observatory"],
                                                        self.config["bounds"],
                                                        [x["data"] for x in self.config["sections"].values()])
            file_handler.to_file(overview, filename=f"{self.config['out']}/overview.html", file_mode="w")

        if self.config["multi_controller"]:
            controller = self.handler.get_controller([v["data"] for v in self.config["sections"].values()],
                                                     self.config["project_id"])
            file_handler.to_file(controller, filename=f"{self.config['out']}/control.html", file_mode="w")

        return controller_urls
