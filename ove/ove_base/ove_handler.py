import re

from argparse import ArgumentParser
from ove.ove_base.geometry import Geometry
from ove.ove_base.data_type import DataType
from ove.ove_base.file_handler import FileHandler
from ove.ove_base.asset_handler import AssetHandler
from ove.utils import load_base_config, Mode, get_dir
from ove.ove_base.request_handler import RequestHandler
from ove.ove_base.section_builder import SectionBuilder
from ove.ove_base.layout_validator import LayoutValidator
from ove.ove_base.output_formatter import OutputFormatter
from ove.ove_base.controller_builder import ControllerBuilder


class OVEHandler:
    def __init__(self):
        self.config = {}
        self.config_parser = self._build_config_parser()
        self.tee_parser = self._build_tee_parser()
        self.args = {}

    def _build_config_parser(self) -> ArgumentParser:
        parser = ArgumentParser(add_help=False)
        parser.add_argument("-s", "--space", type=str, default="LocalFour", nargs="?")
        parser.add_argument("-r", "--rows", type=int, default=2, nargs="?")
        parser.add_argument("-c", "--cols", type=int, default=2, nargs="?")
        parser.add_argument("-e", "--env", type=str, default=".env", nargs="?")
        parser.add_argument("-o", "--out", type=str, default=".ove", nargs="?")
        parser.add_argument("-rm", "--remove", type=bool, default=True, nargs="?")
        parser.add_argument("-m", "--mode", type=str, default="production", choices=["development", "production"],
                            nargs="?")
        return parser

    def _build_tee_parser(self) -> ArgumentParser:
        parser = ArgumentParser(add_help=False)
        parser.add_argument("cell_no", type=int)
        parser.add_argument("-r", "--row", type=int, default=None, nargs="?")
        parser.add_argument("-c", "--col", type=int, default=None, nargs="?")
        parser.add_argument("-w", "--width", type=int, default=None, nargs="?")
        parser.add_argument("-h", "--height", type=int, default=None, nargs="?")
        parser.add_argument("-x", "--x", type=int, default=None, nargs="?")
        parser.add_argument("-y", "--y", type=int, default=None, nargs="?")
        parser.add_argument("-f", "--from", type=int, default=None, nargs=2, dest="from_")
        parser.add_argument("-t", "--to", type=int, default=None, nargs=2, dest="to_")
        parser.add_argument("-s", "--split", type=str, default=None, nargs="?")
        return parser

    def parse_config(self, data: str) -> dict:
        return self.config_parser.parse_args(data.split(" "))

    def load_config(self, args: dict) -> dict:
        self.config = load_base_config(args)
        ove_handler = RequestHandler(self.config["mode"], self.config["core"])
        self.config["geometry"] = ove_handler.get_geometry(self.config["space"])
        ove_handler.clear_space(self.config["space"])

    def ove_config(self, args: dict) -> None:
        self.load_config(args)
        FileHandler().load_dir(self.config["out"], self.config["remove"])

    def parse_tee(self, data: str) -> dict:
        return self.tee_parser.parse_args(data.split(" "))

    def tee(self, args: dict) -> None:
        self.args[args.cell_no] = args

    def handle_output(self, outputs: list[list], cell_no) -> list[dict]:
        args = self.args[cell_no]
        validator = LayoutValidator()
        file_handler = FileHandler()
        asset_handler = AssetHandler(self.config["out"], self.config["host"], file_handler)
        output_formatter = OutputFormatter(file_handler, asset_handler)

        display_type = validator.validate(args)
        geometry = Geometry(args, display_type, self.config["geometry"], self.config["rows"], self.config["cols"],
                            args.split)

        controller_urls = []

        for output_idx, output in enumerate(outputs):
            idx, data_type, data, metadata = output
            data_type = DataType(data_type)
            section = SectionBuilder(
                self.config["core"], asset_handler, output_formatter).build_section(
                data, geometry, args.cell_no, output_idx, len(outputs), self.config["space"], data_type, metadata)

            section_id = RequestHandler(self.config["mode"], self.config["core"]).load_section(
                args.cell_no, output_idx, section, self.config["sections"])
            self.config["sections"][f"{args.cell_no}-{output_idx}"] = {
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
                                                        f"{self.config['host']}:{self.config['port']}",
                                                        self.config["core"])
            file_handler.to_file(overview, filename=f"{self.config['out']}/overview.html", file_mode="w")

        if self.config["multi_controller"]:
            ControllerBuilder(self.config["out"], file_handler).generate_controller(self.config["sections"])

        return controller_urls
