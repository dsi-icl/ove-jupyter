import re

from argparse import ArgumentParser

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
        self.config_parser = self._build_config_parser()
        self.tee_parser = self._build_tee_parser()
        self.CONFIG_SIZE_LIMIT = 500
        self.ARGS_SIZE_LIMIT = 20_000
        self.args = {}

    def _build_config_parser(self) -> ArgumentParser:
        parser = ArgumentParser(add_help=False)
        parser.add_argument("-s", "--space", type=str, default="LocalFour", nargs="?")
        parser.add_argument("-r", "--rows", type=int, default=2, nargs="?")
        parser.add_argument("-c", "--cols", type=int, default=2, nargs="?")
        parser.add_argument("-e", "--env", type=str, default=".env", nargs="?")
        parser.add_argument("-o", "--out", type=str, default=".ove", nargs="?")
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

    def handle_queue(self, xs: dict, key: str, limit: int) -> dict:
        xs[key]["refresh"] = max([v["refresh"] for v in xs.values() if v.get("refresh", None) is not None], default=0)
        if len(xs) > limit:
            vs = sorted(map(lambda v: v["refresh"], xs.values()))[-limit:]
            return {k: v for k, v in xs.items() if v["refresh"] in vs}
        return xs

    def load_config(self, uuid: str, args: dict) -> dict:
        self.config[uuid] = load_base_config(args)
        self.config = self.handle_queue(self.config, uuid, self.CONFIG_SIZE_LIMIT)
        ove_handler = RequestHandler(self.config[uuid]["mode"], self.config[uuid]["core"])
        self.config[uuid]["geometry"] = ove_handler.get_geometry(self.config[uuid]["space"])
        ove_handler.clear_space(self.config[uuid]["space"])

    def ove_config(self, uuid: str, args: dict) -> None:
        self.load_config(uuid, args)

    def parse_tee(self, data: str) -> dict:
        return self.tee_parser.parse_args(data.split(" "))

    def tee(self, uuid: str, args: dict) -> None:
        if self.args.get(uuid, None) is None:
            self.args[uuid] = {}
            self.args = self.handle_queue(self.args, uuid, self.ARGS_SIZE_LIMIT)
        self.args[uuid][args.cell_no] = args

    def handle_output(self, uuid: str, outputs: list[list], cell_no) -> list[dict]:
        args = self.args[uuid][cell_no]
        validator = LayoutValidator()
        file_handler = FileHandler()
        asset_handler = AssetHandler(self.config[uuid]["out"], self.config[uuid]["host"], file_handler)
        output_formatter = OutputFormatter(file_handler, asset_handler)

        display_type = validator.validate(args)
        geometry = Geometry(args, display_type, self.config[uuid]["geometry"], self.config[uuid]["rows"],
                            self.config[uuid]["cols"], args.split)

        controller_urls = []

        for output_idx, output in enumerate(outputs):
            idx, data_type, data, metadata = output
            data_type = DataType(data_type)
            section = SectionBuilder(
                self.config[uuid]["core"], asset_handler, output_formatter).build_section(uuid,
                data, geometry, args.cell_no, output_idx, len(outputs), self.config[uuid]["space"], data_type, metadata)

            section_id = RequestHandler(self.config[uuid]["mode"], self.config[uuid]["core"]).load_section(
                args.cell_no, output_idx, section, self.config[uuid]["sections"])
            self.config[uuid]["sections"][f"{args.cell_no}-{output_idx}"] = {
                "id": section_id,
                "data": section
            }

            if not self.config[uuid]["multi_controller"]:
                controller_urls.append(
                    {"idx": idx, "url": f"{section['app']['url']}/control.html?oveSectionId={section_id}"})

        project = output_formatter.format_project(self.config[uuid]["sections"], self.config[uuid]["space"])
        file_handler.write_json(project, filename=f"{self.config[uuid]['out']}/project_{uuid}.json")

        if self.config[uuid]["mode"] == Mode.DEVELOPMENT:
            overview = output_formatter.format_overview(self.config[uuid]["space"],
                                                        f"{self.config[uuid]['host']}:{self.config[uuid]['port']}",
                                                        self.config[uuid]["core"])
            file_handler.to_file(overview, filename=f"{self.config[uuid]['out']}/overview_{uuid}.html", file_mode="w")

        if self.config[uuid]["multi_controller"]:
            ControllerBuilder(self.config[uuid]["out"], file_handler).generate_controller(uuid,
                                                                                          self.config[uuid]["sections"])

        return controller_urls
