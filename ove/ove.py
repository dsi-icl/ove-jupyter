import typing
import multiprocessing

from dotenv import dotenv_values
from ove.geometry import Geometry
from ove.data_type import DataType
from ove.file_handler import FileHandler
from ove.file_server import create_server
from ove.asset_handler import AssetHandler
from ove.request_handler import RequestHandler
from ove.section_builder import SectionBuilder
from ove.layout_validator import LayoutValidator
from ove.output_formatter import OutputFormatter
from ove.utils import Mode, OVEException, get_dir
from ove.controller_builder import ControllerBuilder
from ove.ipython_display_type import IPythonDisplayType


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

    return config


def run(config: dict, args: dict, outputs: list[dict], injection_handler: typing.Optional[typing.Callable]) -> None:
    validator = LayoutValidator()

    file_handler = FileHandler()
    asset_handler = AssetHandler(config["out"], config["host"], file_handler)
    output_formatter = OutputFormatter(file_handler, asset_handler)

    display_type = validator.validate(args)
    geometry = Geometry(args, display_type, config["geometry"], config["rows"], config["cols"], args.split)

    for output_idx, output in enumerate(outputs):
        if len(output["data"]) == 0:
            continue

        if injection_handler is not None:
            injection_handler(output_idx)

        display_mode = IPythonDisplayType.from_ipython_output(outputs[output_idx])
        if display_mode is not None:
            output = display_mode.format_ipython_output(output)

        n_outputs = len([k for k in output["data"].keys() if "text/plain" not in k])
        for output_type, data in output["data"].items():
            data_type = DataType.from_ipython_display_type(output_type, display_mode, data)

            section = SectionBuilder(
                config["core"], asset_handler, output_formatter).build_section(
                data, geometry, args.cell_no, output_idx, n_outputs, config["space"], data_type, output["metadata"].get(
                    output_type, None))
            if section is None:
                continue

            section_id = RequestHandler(config["mode"], config["core"]).load_section(
                args.cell_no, output_idx, section, config["sections"])
            config["sections"][f"{args.cell_no}-{output_idx}"] = {
                "id": section_id,
                "data": section
            }

            if not config["multi_controller"] and injection_handler is not None:
                injection_handler(controller_injection=(section, section_id))

    project = output_formatter.format_project(config["sections"], config["space"])
    file_handler.write_json(project, filename=f"{config['out']}/project.json")

    if config["mode"] == Mode.DEVELOPMENT:
        overview = output_formatter.format_overview(config["space"], f"{config['host']}:{config['port']}",
                                                    config["core"])
        file_handler.to_file(overview, filename=f"{config['out']}/overview.html", file_mode="w")

    if config["multi_controller"]:
        ControllerBuilder(config["out"], file_handler).generate_controller(config["sections"])

    file_handler.copy(f"{get_dir()}/file_server.py", f"{config['out']}/file_server.py")
