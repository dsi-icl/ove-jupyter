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


def validate_pixels(args):
    if args.width is not None and args.height is not None and args.x is not None and args.y is not None:
        return "validated"
    elif args.width is None and args.height is None and args.x is None and args.y is None:
        return "empty"
    else:
        return "error"


def validate_grid(args):
    if args.row is not None and args.col is not None:
        return "validated"
    elif args.row is None and args.col is None:
        return "empty"
    else:
        return "error"


def validate_flex(args):
    def helper(x):
        return x is not None and hasattr(x, "__len__") and len(x) == 2

    if helper(args.from_) and helper(args.to_) and args.to_[0] > args.from_[0] and args.to_[1] > args.from_[1]:
        return "validated"
    elif args.from_ is None and args.to_ is None:
        return "empty"
    else:
        return "error"


def validate_args(args):
    if args.cell_no is None:
        raise OVEException("No id provided")

    validation = validate_flex(args), validate_pixels(args), validate_grid(args)

    if validation.count("validated") != 1 and validation.count("empty") != len(validation):
        raise OVEException("Invalid cell config")

    if validation.count("empty") == len(validation):
        return "empty"
    return ["flex", "pixel", "grid"][validation.index("validated")]


def get_position(args, mode):
    if mode == "empty":
        section_width, section_height = math.floor(config["geometry"]["w"] / config["rows"]), math.floor(
            config["geometry"]["h"] / config["cols"])
        cur_row, cur_col = math.floor((args.cell_no - 1) / config["rows"]), (args.cell_no - 1) % config["cols"]

        if cur_row >= config["rows"]:
            raise OVEException("Unable to display cell - limit reached")

        return {"x": cur_col * section_width, "y": cur_row * section_height, "w": section_width, "h": section_height}
    elif mode == "grid":
        section_width, section_height = math.floor(config["geometry"]["w"] / config["rows"]), math.floor(
            config["geometry"]["h"] / config["cols"])
        return {"x": (args.col - 1) * section_width, "y": (args.row - 1) * section_height,
                "w": section_width, "h": section_height}
    elif mode == "pixel":
        return {"x": args.x, "y": args.y, "w": args.width, "h": args.height}
    elif mode == "flex":
        tlc, blc, trc, brc = args.from_[0] - 1, args.from_[1] - 1, args.to_[0] - 1, args.to_[1] - 1
        x_span, y_span = trc - tlc, brc - blc
        row_width, col_width = math.floor(config["geometry"]["w"] / config["rows"]), math.floor(
            config["geometry"]["h"] / config["cols"])
        section_width, section_height = row_width * x_span, col_width * y_span
        return {"x": tlc * row_width, "y": blc * col_width, "w": section_width, "h": section_height}
    else:
        raise OVEException(f"Unknown display mode: {mode}")


def get_geometry(args, cur_row, cur_col):
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
    return io, [{k: v for k, v in output.data.items() if "text/plain" not in k} for output in io.outputs]


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


def handle_data(data, cell_no, geometry, i, i_total, data_type):
    if data_type == "html" and "dataframe" in data:
        data = format_dataframe(data)

    split_mode = "width" if geometry["w"] > geometry["h"] else "height"
    filename = f"cell-{cell_no}-{i}.{data_type}"
    file_mode = "w"
    file_data = data
    ove_app = get_ove_app(data_type)

    if ove_app == "images":
        file_mode = "wb"
        file_data = base64.b64decode(data)

    to_file(filename, file_data, file_mode)

    if split_mode == "width":
        width = math.floor(geometry["w"] / i_total)
        x = geometry["x"] + (i * width)
        y, height = geometry["y"], geometry["h"]
    else:
        height = math.floor(geometry["h"] / i_total)
        y = geometry["y"] + (i * height)
        width, x = geometry["w"], geometry["x"]

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
        "x": x,
        "y": y,
        "space": config["space"]
    }


def to_file(filename: str, obj, file_mode: str):
    with open(f"{config['out']}/{filename}", file_mode) as f:
        f.write(obj)


def load_section(cell_no, i, section):
    section_id = config["sections"].get(f"{cell_no}-{i}", None)
    if section_id is not None:
        if config["mode"] == "production":
            requests.delete(f"{config['OVE_CORE']}/sections/{section_id['id']}")
        else:
            print(f"DELETE: {config['OVE_CORE']}/sections/{section_id['id']}")

    if config["mode"] == "production":
        return requests.post(f"{config['OVE_CORE']}/section", json=section).json()["id"]
    else:
        print(f"POST: {config['OVE_CORE']}/section - {section}")
        return len(config["sections"])


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
    if args.mode != "production" and args.mode != "development":
        raise OVEException(f"Unknown mode: {args.mode}")
    config = {
        "space": args.space.replace("\"", ""),
        "rows": args.rows,
        "cols": args.cols,
        "env": args.env.replace("\"", ""),
        "out": args.out.replace("\"", ""),
        "sections": {},
        "mode": args.mode
    }
    config = {**{k: v for k, v in dotenv_values(config["env"]).items() if "OVE_" in k}, **config}
    if config["mode"] == "production":
        config["geometry"] = requests.get(f"{config['OVE_CORE']}/spaces/{config['space']}/geometry").json()
    else:
        config["geometry"] = {"w": 3840, "h": 2160}


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
    @magic_arguments.argument("--from", "-f", type=int, default=None, nargs=2, dest="from_")
    @magic_arguments.argument("--to", "-t", type=int, default=None, nargs=2, dest="to_")
    @register_cell_magic
    def tee(line, cell):
        global config

        args = magic_arguments.parse_argstring(tee, line)

        mode = validate_args(args)
        geometry = get_position(args, mode)
        io, output = get_output(cell)

        injected_outputs = []

        for i, o in enumerate(output):
            injected_outputs.append(io._outputs[i])
            for k, v in o.items():
                if "text/html" in k:
                    section = handle_data(v, args.cell_no, geometry, i, len(output), data_type="html")
                elif "image/png" in k:
                    section = handle_data(v, args.cell_no, geometry, i, len(output), data_type="png")
                elif "image/jpeg" in k:
                    section = handle_data(v, args.cell_no, geometry, i, len(output), len(o.items()), data_type="jpg")
                elif "image/svg+xml" in k:
                    section = handle_data(v, args.cell_no, geometry, i, len(output), data_type="svg")
                else:
                    print(f"Unhandled data type: {k}")

                if section is not None:
                    section_id = load_section(args.cell_no, i, section)
                    config["sections"][f"{args.cell_no}-{i}"] = {
                        "id": section_id,
                        "data": section
                    }

                    if config["mode"] == "production":
                        injected_outputs.append(
                            get_injected(f"{section['app']['url']}/control.html?oveSectionId={section_id}"))
                    else:
                        print(f"Injecting: {section['app']['states']['load']['url']}")
                        injected_outputs.append(get_injected(section["app"]["states"]["load"]["url"]))

        to_project()
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
        args = magic_arguments.parse_argstring(ove_config, line)
        if config != {}:
            return

        load_config(args)
        load_server(args.remove)
        if config["mode"] == "production":
            requests.delete(f"{config['OVE_CORE']}/sections?space={config['space']}")
        else:
            print(f"DELETE: {config['OVE_CORE']}/sections?space={config['space']}")
