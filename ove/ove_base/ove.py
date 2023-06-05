import typing
import multiprocessing

from dotenv import dotenv_values
from ove.utils import Mode, get_dir
from ove.ove_base.geometry import Geometry
from ove.ove_base.data_type import DataType
from ove.ove_base.file_handler import FileHandler
from ove.ove_base.file_server import create_server
from ove.ove_base.asset_handler import AssetHandler
from ove.ove_base.request_handler import RequestHandler
from ove.ove_base.section_builder import SectionBuilder
from ove.ove_base.layout_validator import LayoutValidator
from ove.ove_base.output_formatter import OutputFormatter
from ove.ove_base.controller_builder import ControllerBuilder
from ove.ove.ipython_display_type import IPythonDisplayType


def load_dir(out_dir: str, remove: bool) -> None:
    file_handler = FileHandler()
    file_handler.mkdir(out_dir)

    if remove:
        file_handler.rm(out_dir)


def load_server(config: dict, server_thread: multiprocessing.Process) -> None:
    if server_thread is not None:
        server_thread.terminate()

    server_thread = multiprocessing.Process(target=create_server,
                                            args=(int(config["port"]), config["out"], config["env"], True))
    server_thread.start()
    FileHandler().copy(f"{get_dir()}/ove_base/file_server.py", f"{config['out']}/file_server.py")

    return server_thread


def load_config(args: dict) -> dict:
    config = {
        "space": args.space.replace("\"", ""),
        "rows": args.rows,
        "cols": args.cols,
        "env": args.env.replace("\"", ""),
        "out": args.out.replace("\"", ""),
        "sections": {},
        "remove": args.remove,
        "mode": Mode(args.mode),
        "multi_controller": False
    }
    config = {**{k[4:].lower(): v for k, v in dotenv_values(config["env"]).items() if "OVE_" in k}, **config}

    ove_handler = RequestHandler(config["mode"], config["core"])
    config["geometry"] = ove_handler.get_geometry(config["space"])
    ove_handler.clear_space(config["space"])

    return config


def base_run(config: dict, args: dict, outputs: list[tuple[DataType, typing.Any, typing.Any]]):
    validator = LayoutValidator()
    file_handler = FileHandler()
    asset_handler = AssetHandler(config["out"], config["host"], file_handler)
    output_formatter = OutputFormatter(file_handler, asset_handler)

    display_type = validator.validate(args)
    geometry = Geometry(args, display_type, config["geometry"], config["rows"], config["cols"], args.split)

    controller_urls = []

    for output_idx, output in enumerate(outputs):
        idx, data_type, data, metadata = output
        section = SectionBuilder(
            config["core"], asset_handler, output_formatter).build_section(
            data, geometry, args.cell_no, output_idx, len(outputs), config["space"], data_type, metadata)

        section_id = RequestHandler(config["mode"], config["core"]).load_section(
            args.cell_no, output_idx, section, config["sections"])
        config["sections"][f"{args.cell_no}-{output_idx}"] = {
            "id": section_id,
            "data": section
        }

        if not config["multi_controller"]:
            controller_urls.append(
                {"idx": idx, "url": f"{section['app']['url']}/control.html?oveSectionId={section_id}"})

    project = output_formatter.format_project(config["sections"], config["space"])
    file_handler.write_json(project, filename=f"{config['out']}/project.json")

    if config["mode"] == Mode.DEVELOPMENT:
        overview = output_formatter.format_overview(config["space"], f"{config['host']}:{config['port']}",
                                                    config["core"])
        file_handler.to_file(overview, filename=f"{config['out']}/overview.html", file_mode="w")

    if config["multi_controller"]:
        ControllerBuilder(config["out"], file_handler).generate_controller(config["sections"])

    return controller_urls
