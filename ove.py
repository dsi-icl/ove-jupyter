import os
import re
import glob
import json
import math
import base64
import shutil
import markdown
import requests
import http.server
import socketserver
import urllib.request
import multiprocessing

from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import threading

from IPython import get_ipython
from dotenv import dotenv_values
from IPython.core import magic_arguments
from IPython.display import IFrame, Latex, display
from IPython.lib.latextools import latex_to_png, latex_to_html
from IPython.utils.capture import capture_output, CapturedIO
from IPython.core.displaypub import CapturingDisplayPublisher
from IPython.core.magic import register_cell_magic, register_line_magic


def handle_markdown_css():
    if os.path.exists(f"{config['out']}/markdown-github.css"):
        return
    else:
        shutil.copy("./markdown-github.css", f"{config['out']}/markdown-github.css")


class OVEException(Exception):
    def __init__(self, message):
        super().__init__(f"OVE Error: {message}")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=kwargs["directory"], **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        http.server.SimpleHTTPRequestHandler.end_headers(self)

    def log_message(self, format: str, *args) -> None:
        pass


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


def mkdir(dir_):
    if not os.path.exists(dir_):
        os.makedirs(dir_)


config = {}
server_thread = None


def create_server(port, out):
    server = ThreadedHTTPServer(("", port), handler_from(out))
    server.serve_forever()


def handler_from(directory):
    def _init(self, *args, **kwargs):
        return http.server.SimpleHTTPRequestHandler.__init__(self, *args, directory=self.directory,
                                                             **kwargs)

    return type(f'HandlerFrom<{directory}>',
                (Handler,),
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
        cur_col, cur_row = math.floor((args.cell_no - 1) / config["cols"]), (args.cell_no - 1) % config["cols"]

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
    return io, [{k: v for k, v in output.data.items()} for output in io.outputs if len(output.data) > 0]


def format_geojson(geojson, metadata):
    if metadata["layer_options"].get("basemap_id", None) is not None:
        basemap = metadata["url_template"].replace("{basemap_id}", f"{metadata['layer_options']['basemap_id']}")
    else:
        basemap = metadata["url_template"]
    return {
        "layers": [
            {
                "type": "L.tileLayer",
                "visible": False,
                "wms": False,
                "url": basemap
            },
            {
                "type": "L.geoJSON",
                "visible": False,
                "wms": False,
                "data": geojson,
                "options": {
                    "style": {
                        "fill": True,
                        "fillColor": "#B29255",
                        "fillOpacity": 0.7,
                        "color": "#715E3A",
                        "weight": 4,
                        "opacity": 0.7
                    }
                }
            }
        ],
        "center": ["-11137.70850550061", "6710544.04980525"],
        "resolution": "77",
        "zoom": "12"
    }


def format_dict(obj):
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
            background-color: white;
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
    </style>
</head>
    """
    return f"""
<!doctype html>
<!doctype html>
<html lang="en">
{head}
<body>
<pre id="json">{json.dumps(obj, indent=4)}</pre>
</body>
</html>
    """.strip()


def format_markdown(md):
    handle_markdown_css()
    head = """
<head>
    <title>OVE Jupyter</title>
    <link rel="stylesheet" type="text/css" href="../markdown-github.css">
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
            box-sizing: border-box;
            min-width: 200px;
            max-width: 980px;
            margin: 0 auto;
            padding: 45px;
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
    </style>
</head>
    """
    return f"""
<!doctype html>
<!doctype html>
<html lang="en">
{head}
<body>
<main class="markdown-body">
    {markdown.markdown(md)}
</main>
</body>
</html>
    """.strip()


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


def get_data_type(k, display_mode, data):
    if display_mode is not None and "Audio" in display_mode and "text/html" in k:
        return "audio"
    elif display_mode is not None and "Video" in display_mode and "text/html" in k:
        return "videos"
    elif "text/html" in k:
        return "dataframe" if "dataframe" in data else "html"
    elif "image/png" in k:
        return "png"
    elif "image/jpeg" in k:
        return "jpg"
    elif "image/svg+xml" in k:
        return "svg"
    elif "text/latex" in k:
        return "latex"
    elif "text/markdown" in k:
        return "markdown"
    elif "application/json" in k:
        return "json"
    elif "application/geo+json" in k:
        return "geojson"
    elif "text/plain" in k:
        return None
    else:
        return None
        print(f"Unhandled data type: {k}")


def get_ove_app(data_type):
    if data_type == "html":
        return "html"
    elif data_type == "png" or data_type == "jpg":
        return "images"
    elif data_type == "svg":
        return "svg"
    elif data_type == "geojson":
        return "maps"
    elif data_type == "videos":
        return "videos"
    elif data_type == "audio":
        return "audio"
    else:
        raise OVEException(f"Unknown data type: {data_type}")


def write_media(data, cell_no, i):
    if "http" in data:
        return data
    if "." not in data:
        raise OVEException("Raw data source not supported")
    raise OVEException("Local files not supported")
    # filename = f"cell-{cell_no}-{i}.{data.split('.')[-1]}"
    # urllib.request.urlretrieve(f"file://{os.path.abspath(data)}", f"{config['out']}/{filename}")
    # return f"{config['OVE_HOST']}:8000/{filename}"


def write_data(data, cell_no, i, data_type, ove_app):
    filename = f"cell-{cell_no}-{i}.{data_type.replace('geo', '')}"
    file_mode = "w"
    file_data = data

    if ove_app == "images":
        file_mode = "wb"
        file_data = base64.b64decode(data)
    if ove_app == "maps":
        file_data = json.dumps(data, indent=4)

    to_file(filename, file_data, file_mode)
    return f"{config['OVE_HOST']}:8000/{filename}"


def is_media(data_type):
    return data_type == "videos" or data_type == "audio"


def split_geometry(geometry, split_mode, i, i_total):
    if split_mode == "width":
        width = math.floor(geometry["w"] / i_total)
        x = geometry["x"] + (i * width)
        y, height = geometry["y"], geometry["h"]
    else:
        height = math.floor(geometry["h"] / i_total)
        y = geometry["y"] + (i * height)
        width, x = geometry["w"], geometry["x"]

    return x, y, width, height


def is_dataframe(data, data_type):
    return data_type == "html" and "dataframe" in data


def handle_data(data, cell_no, geometry, i, i_total, split_mode, data_type):
    ove_app = get_ove_app(data_type)
    file_url = write_media(data, cell_no, i) if is_media(data_type) else write_data(data, cell_no, i, data_type,
                                                                                    ove_app)
    x, y, width, height = split_geometry(geometry, split_mode, i, i_total)

    return {
        "app": {
            "states": {
                "load": {
                    "url": file_url
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
        "mode": args.mode,
        "multi_controller": False
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


def get_injected(content):
    with capture_output(True, True, True) as io:
        display(content)
    return io._outputs[0]


def format_cell_name(cell_name: str):
    xs = cell_name.split("-")
    return f"{xs[0]}.{xs[1]}" if int(xs[1]) > 0 else f"{xs[0]}"


def get_app_url(section):
    return section["data"]["app"]["url"]

def create_controller_nav_content():
    if len(config["sections"]) == 0:
        return ""
    return "\n\t\t\t".join([f"<li><button onclick=\"changeContent('{get_app_url(section)}/control.html?oveSectionId={section['id']}')\">Cell {format_cell_name(k)} - {get_app_url(section).split('/')[-1]}</button></li>" for k, section in config["sections"].items()])


def get_controller_start_url():
    if len(config["sections"]) == 0:
        return ""
    k_, section_id = min([(k, v["id"]) for k, v in config["sections"].items()], key=lambda x: x[1])
    return f"{config['sections'][k_]['data']['app']['url']}/control.html?oveSectionId={section_id}"


def create_controller():
    content = create_controller_nav_content()
    start_url = get_controller_start_url()
    script = """
<script>
    function changeContent(url) {
        document.getElementById("content").src = url
    }
</script>
    """
    head = """
<head>
    <meta charset="UTF-8">
    <title>OVE Jupyter Unified Controller</title>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <meta name="description" content="Unified controller for ove-jupyter generated sections"/>
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
    </style>
</head>
    """
    return f"""
<!DOCTYPE html>
<html lang="en">
{head}
<body>
<main style="display: flex; overflow: hidden">
    <nav style="width: 15vw; overflow-y: scroll; max-height: 100vh;">
        <ul>
            {content}
        </ul>
    </nav>
    <iframe id="content" src="{start_url}" style="width: 85vw; height: 100vh"></iframe>
</main>
</body>
</html>

{script}
    """.strip()


def format_latex(latex):
    latex = latex.replace("\\displaystyle ", "").replace("\\\\", "\\")
    if "$$" not in latex:
        latex = latex.replace("$", "$$")
    latex = latex_to_html(latex)
    head = """
<head>
    <title>OVE Jupyter</title>
    <link rel="stylesheet" type="text/css" href="../markdown-github.css">
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
            box-sizing: border-box;
            min-width: 200px;
            max-width: 980px;
            margin: 0 auto;
            padding: 45px;
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
    </style>
</head>
    """
    return f"""
<!doctype html>
<!doctype html>
<html lang="en">
{head}
<body>
<main class="markdown-body">
{latex}
</main>
</body>
</html>
    """.strip()


def get_source(data):
    return re.search(r"src=\"([^\"]+)\"", data).group(1)


def get_section(v, cell_no, geometry, i, i_total, split_mode, data_type, metadata):
    if data_type == None:
        return None

    if data_type == "audio":
        v = get_source(v)
    elif data_type == "videos":
        v = get_source(v)
    elif data_type == "dataframe":
        v = format_dataframe(v)
        data_type = "html"
    elif data_type == "latex":
        v = format_latex(v)
        data_type = "html"
    elif data_type == "markdown":
        v = format_markdown(v)
        data_type = "html"
    elif data_type == "json":
        v = format_dict(v)
        data_type = "html"
    elif data_type == "geojson":
        v = format_geojson(v, metadata["application/geo+json"])

    return handle_data(v, cell_no, geometry, i, i_total, split_mode, data_type=data_type)


def get_display_mode(output):
    if output["data"].get("text/plain", None) is None:
        return None

    search = re.search(r"IPython\.(?:core|lib)\.display\.([^ ]+)", output["data"]["text/plain"])
    if not bool(search):
        return None

    return search.group(1)


def get_split_mode(split, geometry):
    return split if split is not None else ("width" if geometry["w"] > geometry["h"] else "height")


def handle_split(k, data, cell_no, geometry, i, i_total, split_mode, display_mode, metadata):
    data_type = get_data_type(k, display_mode, data)
    section = get_section(data, cell_no, geometry, i, i_total, split_mode, data_type, metadata)

    if section is None:
        return None

    section_id = load_section(cell_no, i, section)
    config["sections"][f"{cell_no}-{i}"] = {
        "id": section_id,
        "data": section
    }

    if config["mode"] == "production":
        return get_injected(IFrame(f"{section['app']['url']}/control.html?oveSectionId={section_id}", "100%", "400px"))
    else:
        print(f"Injecting: {section['app']['states']['load']['url']}")
        return get_injected(IFrame(section["app"]["states"]["load"]["url"], "100%", "400px"))


def generate_controller():
    with open(f"{config['out']}/controller.html", "w") as f:
        f.write(create_controller())


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
        geometry = get_position(args, mode)
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

        to_project()
        if config["multi_controller"]:
            generate_controller()
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


    @register_line_magic
    def ove_controller(line):
        config["multi_controller"] = True
