import os
import re
import glob
import json
import math
import base64
import requests
import http.server
import socketserver
import multiprocessing

from IPython import get_ipython
from dotenv import dotenv_values
from IPython.display import IFrame
from IPython.core import magic_arguments
from IPython.utils.capture import capture_output, CapturedIO
from IPython.core.displaypub import CapturingDisplayPublisher
from IPython.core.magic import register_cell_magic, register_line_magic


class OVEException(Exception):
    def __init__(self, message):
        super().__init__(f"OVE Error: {message}")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=kwargs["directory"], **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:
        pass


def mkdir(dir_):
    if not os.path.exists(dir_):
        os.makedirs(dir_)


config = {}
server_thread = None


def create_server(port, out):
    httpd = socketserver.TCPServer(("", port), handler_from(out))
    httpd.serve_forever()


def handler_from(directory):
    def _init(self, *args, **kwargs):
        return http.server.SimpleHTTPRequestHandler.__init__(self, *args, directory=self.directory,
                                                             **kwargs)

    return type(f'HandlerFrom<{directory}>',
                (http.server.SimpleHTTPRequestHandler,),
                {'__init__': _init, 'directory': directory})


def validate_args(args):
    if args.cell_no is None:
        raise OVEException("No id provided")
    cur_row = args.row - 1 if args.row is not None else math.floor((args.cell_no - 1) / config["rows"])
    cur_col = args.col - 1 if args.col is not None else (args.cell_no - 1) % config["cols"]

    if not ((
                    args.width is not None and args.height is not None and args.row is None and args.col is None and args.x is not None and args.y is not None) or (
                    args.row is not None and args.col is not None and args.x is None and args.y is None and args.width is None and args.height is None) or (
                    args.width is None and args.height is None and args.x is None and args.y is None and args.row is None and args.col is None)):
        raise OVEException("Invalid cell config")

    if args.width is None and args.height is None and args.x is None and args.y is None and args.row is None and args.col is None:
        if cur_row >= config["rows"]:
            raise OVEException("Unable to display cell - limit reached")
    return cur_row, cur_col


def get_geometry(args):
    section_width = args.width if args.width is not None else math.floor(config["geometry"]["w"] / config["rows"])
    section_height = args.height if args.height is not None else math.floor(
        config["geometry"]["h"] / config["cols"])

    x_pos = args.x if args.x is not None else cur_row / section_width
    y_pos = args.y if args.y is not None else cur_col / section_height

    return {"w": section_width, "h": section_height, "x": x_pos, "y": y_pos}


def get_output(cell):
    """
    This is a utils.io.CapturedIO object with stdout/err attributes
    for the text of the captured output.
    CapturedOutput also has a show() method for displaying the output,
    and __call__ as well, so you can use that to quickly display the
    output.
    """
    with capture_output(True, True, True) as io:
        get_ipython().run_cell(cell)
    return io, [{k: v for k, v in output.data.items() if "text/plain" not in k and "text/latex" not in k} for output in
                io.outputs]


def format_dataframe(html):
    html = html.replace("border=\"1\" ", "").replace(" style=\"text-align: right;\"", "")
    html = re.sub(r"<style .*>(?:.|\r|\n|\t)*</style>", "", html)
    head = """
<head>
    <title>OVE Jupyter</title>
    <style>
        /* Box sizing rules */
        *,
        *::before,
        *::after {
            box-sizing: border-box;
        }

        /* Remove default margin */
        body,
        h1,
        h2,
        h3,
        h4,
        p,
        figure,
        blockquote,
        dl,
        dd {
            margin: 0;
        }

        /* Remove list styles on ul, ol elements with a list role, which suggests default styling will be removed */
        ul[role='list'],
        ol[role='list'] {
            list-style: none;
        }

        /* Set core root defaults */
        html:focus-within {
            scroll-behavior: smooth;
        }

        /* Set core body defaults */
        body {
            min-height: 100vh;
            text-rendering: optimizeSpeed;
            line-height: 1.5;
        }

        /* A elements that don't have a class get default styles */
        a:not([class]) {
            text-decoration-skip-ink: auto;
        }

        /* Make images easier to work with */
        img,
        picture {
            max-width: 100%;
            display: block;
        }

        /* Inherit fonts for inputs and buttons */
        input,
        button,
        textarea,
        select {
            font: inherit;
        }

        /* Remove all animations, transitions and smooth scroll for people that prefer not to see them */
        @media (prefers-reduced-motion: reduce) {
            html:focus-within {
                scroll-behavior: auto;
            }

            *,
            *::before,
            *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }
        }
        
        .dataframe {
            font-family: Arial, Helvetica, sans-serif;
            border-collapse: collapse;
            width: 100vw;
            height: 100vh;
        }

        .dataframe td, th {
            border: 1px solid #ddd;
            padding: 8px;
        }

        .dataframe tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        
        .dataframe tr:nth-child(odd) {
            background-color: #ffffff
        }

        .dataframe tr:hover {
            background-color: #ddd;
        }

        .dataframe th {
            padding-top: 12px;
            padding-bottom: 12px;
            background-color: #002147;
            color: white;
        }

        .dataframe th, td, tr {
            text-align: center;
        }
    </style>
</head>
    """
    return f"""
<!doctype html>
<!doctype html>
<html lang="en">
{head}
<body>
{html}
</body>
</html>
    """.strip()


def get_ove_app(data_type):
    if data_type == "html":
        return "html"
    elif data_type == "png" or data_type == "jpg":
        return "images"
    elif data_type == "svg":
        return "svg"
    else:
        raise OVEException(f"Unknown data type: {data_type}")


def handle_data(data, cell_no, geometry, i, j, i_total, j_total, data_type):
    if data_type == "html" and "dataframe" in data:
        data = format_dataframe(data)

    filename = f"cell-{cell_no}-{i}-{j}.{data_type}"
    file_mode = "w"
    file_data = data
    ove_app = get_ove_app(data_type)

    if ove_app == "images":
        file_mode = "wb"
        file_data = base64.b64decode(data)

    to_file(filename, file_data, file_mode)

    width = math.floor(geometry["w"] / j_total)
    height = math.floor(geometry["h"] / i_total)

    return {
        "app": {
            "states": {
                "load": {
                    "url": f"{config['OVE_HOST']}:8000/{filename}"
                }
            },
            "url": f"{config['OVE_CORE']}/app/{ove_app}"
        },
        "h": height,
        "w": width,
        "x": geometry["x"] + (j * width),
        "y": geometry["y"] + (i * height),
        "space": config["space"]
    }


def to_file(filename: str, obj, file_mode: str):
    with open(f"{config['out']}/{filename}", file_mode) as f:
        f.write(obj)


def load_section(cell_no, i, j, section):
    section_id = config["sections"].get(f"{cell_no}-{i}-{j}", None)
    if section_id is not None:
        requests.delete(f"{config['OVE_CORE']}/sections/{section_id['id']}")

    return requests.post(f"{config['OVE_CORE']}/section", json=section).json()["id"]


def load_server(remove):
    global server_thread
    mkdir(config["out"])

    if remove:
        files = glob.glob(f"{config['out']}/*")
        for f in files:
            os.remove(f)

    if server_thread is not None:
        server_thread.terminate()

    server_thread = multiprocessing.Process(target=create_server, args=(int(config["OVE_PORT"]), config["out"]))
    server_thread.start()


def load_config(args):
    global config
    config = {
        "space": args.space.replace("\"", ""),
        "rows": args.rows,
        "cols": args.cols,
        "env": args.env.replace("\"", ""),
        "out": args.out.replace("\"", ""),
        "sections": {}
    }
    config = {**{k: v for k, v in dotenv_values(config["env"]).items() if "OVE_" in k}, **config}
    config["geometry"] = requests.get(f"{config['OVE_CORE']}/spaces/{config['space']}/geometry").json()


def format_project():
    return {
        "HasVideos": False,
        "Metadata": {
            "authors": "",
            "default_mode": config["space"],
            "description": "",
            "name": "",
            "publications": "",
            "tags": [],
            "thumbnail": "",
        },
        "Sections": [section["data"] for section in config["sections"].values()]
    }


def to_project():
    with open(f"{config['out']}/project.json", "w") as f:
        json.dump(format_project(), f, indent=4)


def get_injected(src):
    with capture_output(True, True, True) as io:
        display(IFrame(src, "100%", "400px"))
    return io._outputs[0]


def load_ipython_extension(ipython):
    @magic_arguments.magic_arguments()
    @magic_arguments.argument("cell_no", type=int)
    @magic_arguments.argument("--row", "-r", type=int, default=None, nargs="?")
    @magic_arguments.argument("--col", "-c", type=int, default=None, nargs="?")
    @magic_arguments.argument("--width", "-w", type=int, default=None, nargs="?")
    @magic_arguments.argument("--height", "-h", type=int, default=None, nargs="?")
    @magic_arguments.argument("--x", "-x", type=int, default=None, nargs="?")
    @magic_arguments.argument("--y", "-y", type=int, default=None, nargs="?")
    @register_cell_magic
    def tee(line, cell):
        global config

        args = magic_arguments.parse_argstring(tee, line)

        cur_row, cur_col = validate_args(args)
        geometry = get_geometry(args)
        io, output = get_output(cell)

        injected_outputs = []

        for i, o in enumerate(output):
            injected_outputs.append(io._outputs[i])
            for j, (k, v) in enumerate(o.items()):
                if "text/html" in k:
                    section = handle_data(v, args.cell_no, geometry, i, j, len(output), len(o.items()),
                                          data_type="html")
                elif "image/png" in k:
                    section = handle_data(v, args.cell_no, geometry, i, j, len(output), len(o.items()), data_type="png")
                elif "image/jpeg" in k:
                    section = handle_data(v, args.cell_no, geometry, i, j, len(output), len(o.items()), data_type="jpg")
                elif "image/svg+xml" in k:
                    section = handle_data(v, args.cell_no, geometry, i, j, len(output), len(o.items()), data_type="svg")
                else:
                    print(k)
                    print(v)

                if section is not None:
                    section_id = load_section(args.cell_no, i, j, section)
                    config["sections"][f"{args.cell_no}-{i}-{j}"] = {
                        "id": section_id,
                        "data": section
                    }

                    injected_outputs.append(
                        get_injected(f"{section['app']['url']}/control.html?oveSectionId={section_id}"))

        to_project()
        io._outputs = injected_outputs

        io()

    @magic_arguments.magic_arguments()
    @magic_arguments.argument("--space", "-s", type=str, default="LocalFour", nargs="?")
    @magic_arguments.argument("--rows", "-r", type=int, default="2", nargs="?")
    @magic_arguments.argument("--cols", "-c", type=int, default="2", nargs="?")
    @magic_arguments.argument("--env", "-e", type=str, default=".env", nargs="?")
    @magic_arguments.argument("--out", "-o", type=str, default=".ove", nargs="?")
    @magic_arguments.argument("--remove", "-rm", type=bool, default=False, nargs="?")
    @register_line_magic
    def ove_config(line):
        args = magic_arguments.parse_argstring(ove_config, line)
        if config != {}:
            return

        load_config(args)
        load_server(args.remove)
        requests.delete(f"{config['OVE_CORE']}/sections?space={config['space']}")
