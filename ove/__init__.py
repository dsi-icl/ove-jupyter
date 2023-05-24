import os
import glob
import shutil
import requests
import multiprocessing

from ove.ove import *
from IPython import get_ipython
from dotenv import dotenv_values
from IPython.display import IFrame
from IPython.core import magic_arguments
from ove.file_server import create_server
from IPython.utils.capture import capture_output, CapturedIO
from IPython.core.magic import register_cell_magic, register_line_magic

config = {}
server_thread = None


def get_output(cell: typing.Any) -> tuple[CapturedIO, list[dict]]:
    with capture_output(True, True, True) as io:
        get_ipython().run_cell(cell)
    return io, [{k: v for k, v in output.data.items()} for output in io.outputs if len(output.data) > 0]


def load_server(remove: bool) -> None:
    global server_thread
    mkdir(config["out"])

    if remove:
        files = glob.glob(f"{config['out']}/*")
        for f in files:
            os.remove(f)

    if server_thread is not None:
        server_thread.terminate()

    server_thread = multiprocessing.Process(target=create_server,
                                            args=(int(config["OVE_PORT"]), config["out"], config["env"], True))
    server_thread.start()


def load_config(args: dict) -> None:
    global config
    if args.mode != "production" and args.mode != "development":
        raise OVEException(f"Unknown mode: {args.mode}")
    config = {
        "space": args.space.replace("\"", ""),
        "rows": args.rows,
        "cols": args.cols,
        "env": args.env.replace("\"", ""),
        "out": args.out.replace("\"", ""),
        "sections": {},
        "mode": args.mode,
        "multi_controller": False
    }
    config = {**{k: v for k, v in dotenv_values(config["env"]).items() if "OVE_" in k}, **config}
    if config["mode"] == "production":
        config["geometry"] = requests.get(f"{config['OVE_CORE']}/spaces/{config['space']}/geometry").json()
    else:
        config["geometry"] = {"w": 3840, "h": 2160}


def handle_split(k: str, data: str, cell_no: int, geometry: dict, i: int, i_total: int, split_mode: str,
                 display_mode: str, metadata: dict) -> typing.Optional[dict]:
    data_type = get_data_type(k, display_mode, data)
    section = get_section(data, cell_no, geometry, i, i_total, split_mode, data_type, metadata, config["OVE_CORE"],
                          config["out"], config["OVE_HOST"], config["space"])

    if section is None:
        return None

    section_id = load_section(cell_no, i, section, config["sections"], config["mode"], config["OVE_CORE"])
    config["sections"][f"{cell_no}-{i}"] = {
        "id": section_id,
        "data": section
    }

    if config["mode"] == "production":
        return get_injected(IFrame(f"{section['app']['url']}/control.html?oveSectionId={section_id}", "100%", "400px"))
    else:
        print(f"Injecting: {section['app']['states']['load']['url']}")
        return get_injected(IFrame(section["app"]["states"]["load"]["url"], "100%", "400px"))


def load_ipython_extension(ipython):
    @magic_arguments.magic_arguments()
    @magic_arguments.argument("cell_no", type=int)
    @magic_arguments.argument("--row", "-r", type=int, default=None, nargs="?")
    @magic_arguments.argument("--col", "-c", type=int, default=None, nargs="?")
    @magic_arguments.argument("--width", "-w", type=int, default=None, nargs="?")
    @magic_arguments.argument("--height", "-h", type=int, default=None, nargs="?")
    @magic_arguments.argument("--x", "-x", type=int, default=None, nargs="?")
    @magic_arguments.argument("--y", "-y", type=int, default=None, nargs="?")
    @magic_arguments.argument("--from", "-f", type=int, default=None, nargs=2, dest="from_")
    @magic_arguments.argument("--to", "-t", type=int, default=None, nargs=2, dest="to_")
    @magic_arguments.argument("--split", "-s", type=str, default=None, nargs="?")
    @register_cell_magic
    def tee(line, cell):
        global config

        args = magic_arguments.parse_argstring(tee, line)

        mode = validate_args(args)
        geometry = get_position(args, mode, config["geometry"], config["rows"], config["cols"])
        io, output = get_output(cell)

        injected_outputs = []
        split_mode = get_split_mode(args.split, geometry)

        for i, o in enumerate(output):
            i_total = len(output)
            injected_outputs.append(io._outputs[i])
            display_mode = get_display_mode(io._outputs[i])

            if display_mode is not None and "YouTubeVideo" in display_mode:
                o = {k: v for k, v in o.items() if "image" not in k}

            for k, v in o.items():
                injected = handle_split(k, v, args.cell_no, geometry, i, i_total, split_mode, display_mode,
                                        io._outputs[i]["metadata"])
                if injected is not None and not config["multi_controller"]:
                    injected_outputs.append(injected)

        to_project(config["sections"], config["space"], config["out"])
        if config["multi_controller"]:
            generate_controller(config["sections"], config["out"])
        shutil.copy(f"{get_dir()}/file_server.py", f"{config['out']}/file_server.py")
        io._outputs = injected_outputs

        io()

    @magic_arguments.magic_arguments()
    @magic_arguments.argument("--space", "-s", type=str, default="LocalFour", nargs="?")
    @magic_arguments.argument("--rows", "-r", type=int, default="2", nargs="?")
    @magic_arguments.argument("--cols", "-c", type=int, default="2", nargs="?")
    @magic_arguments.argument("--env", "-e", type=str, default=".env", nargs="?")
    @magic_arguments.argument("--out", "-o", type=str, default=".ove", nargs="?")
    @magic_arguments.argument("--remove", "-rm", type=bool, default=True, nargs="?")
    @magic_arguments.argument("--mode", "-m", type=str, default="production", nargs="?")
    @register_line_magic
    def ove_config(line):
        global config
        config = {}
        args = magic_arguments.parse_argstring(ove_config, line)

        load_config(args)
        load_server(args.remove)
        if config["mode"] == "production":
            requests.delete(f"{config['OVE_CORE']}/sections?space={config['space']}")
        else:
            print(f"DELETE: {config['OVE_CORE']}/sections?space={config['space']}")

    @register_line_magic
    def ove_controller(line):
        config["multi_controller"] = True
