import os
import re
import json
import math
import base64
import shutil
import typing
import requests

from markdown import markdown
from IPython import get_ipython
from IPython.display import display
from urllib.request import urlretrieve
from IPython.lib.latextools import latex_to_html
from IPython.utils.capture import CapturedIO, capture_output


class OVEException(Exception):
    def __init__(self, message):
        super().__init__(f"OVE Error: {message}")


def read_file(filename: str) -> str:
    with open(filename) as f:
        return "".join(f.readlines())


def get_dir() -> str:
    return "/".join(os.path.realpath(__file__).split("/")[:-1])


def mkdir(dir_: str) -> None:
    if not os.path.exists(dir_):
        os.makedirs(dir_)


def handle_markdown_css(out: str) -> None:
    if os.path.exists(f"{out}/markdown-github.css"):
        return
    else:
        shutil.copy(f"{get_dir()}/assets/markdown-github.css", f"{out}/markdown-github.css")


def validate_pixels(args: dict) -> str:
    if args.width is not None and args.height is not None and args.x is not None and args.y is not None:
        return "validated"
    elif args.width is None and args.height is None and args.x is None and args.y is None:
        return "empty"
    else:
        return "error"


def validate_grid(args: dict) -> str:
    if args.row is not None and args.col is not None:
        return "validated"
    elif args.row is None and args.col is None:
        return "empty"
    else:
        return "error"


def validate_flex(args: dict) -> str:
    def helper(x: typing.Any) -> bool:
        return x is not None and hasattr(x, "__len__") and len(x) == 2

    if helper(args.from_) and helper(args.to_) and args.to_[0] > args.from_[0] and args.to_[1] > args.from_[1]:
        return "validated"
    elif args.from_ is None and args.to_ is None:
        return "empty"
    else:
        return "error"


def validate_args(args: dict):
    if args.cell_no is None:
        raise OVEException("No id provided")

    validation = validate_flex(args), validate_pixels(args), validate_grid(args)

    if validation.count("validated") != 1 and validation.count("empty") != len(validation):
        raise OVEException("Invalid cell config")

    if validation.count("empty") == len(validation):
        return "empty"
    return ["flex", "pixel", "grid"][validation.index("validated")]


def get_position(args: dict, mode: str, geometry: dict, rows: int, cols: int) -> dict:
    if mode == "empty":
        section_width, section_height = math.floor(geometry["w"] / cols), math.floor(geometry["h"] / rows)
        cur_col, cur_row = math.floor((args.cell_no - 1) / rows), (args.cell_no - 1) % rows

        if cur_col >= cols:
            raise OVEException("Unable to display cell - limit reached")

        return {"x": cur_col * section_width, "y": cur_row * section_height, "w": section_width, "h": section_height}
    elif mode == "grid":
        section_width, section_height = math.floor(geometry["w"] / cols), math.floor(geometry["h"] / rows)
        return {"x": (args.col - 1) * section_width, "y": (args.row - 1) * section_height,
                "w": section_width, "h": section_height}
    elif mode == "pixel":
        return {"x": args.x, "y": args.y, "w": args.width, "h": args.height}
    elif mode == "flex":
        tlc, blc, trc, brc = args.from_[0] - 1, args.from_[1] - 1, args.to_[0] - 1, args.to_[1] - 1
        x_span, y_span = trc - tlc, brc - blc
        cell_width, cell_height = math.floor(geometry["w"] / cols), math.floor(geometry["h"] / rows)
        section_width, section_height = cell_width * x_span, cell_height * y_span
        return {"x": tlc * cell_width, "y": blc * cell_height, "w": section_width, "h": section_height}
    else:
        raise OVEException(f"Unknown display mode: {mode}")


def format_geojson(geojson: str, metadata: dict) -> dict:
    if metadata["layer_options"].get("basemap_id", None) is not None:
        basemap = metadata["url_template"].replace("{basemap_id}", f"{metadata['layer_options']['basemap_id']}")
    else:
        basemap = metadata["url_template"]
    outline = read_file(f"{get_dir()}/assets/geojson_format.json")
    return json.loads(outline.replace("%%basemap%%", basemap).replace("%%geojson%%", json.dumps(geojson)))


def format_dict(obj: typing.Union[dict, list]) -> str:
    outline = read_file(f"{get_dir()}/assets/dict_format.html")
    return outline.replace("%%replace%%", json.dumps(obj, indent=4))


def format_markdown(md: str, out: str) -> str:
    handle_markdown_css(out)
    outline = read_file(f"{get_dir()}/assets/dataframe_format.html")
    return outline.replace("%%replace%%", markdown(md))


def format_dataframe(html: str) -> str:
    html = html.replace("border=\"1\" ", "").replace(" style=\"text-align: right;\"", "")
    html = re.sub(r"<style .*>(?:.|\r|\n|\t)*</style>", "", html)
    outline = read_file(f"{get_dir()}/assets/dataframe_format.html")
    return outline.replace("%%replace%%", html)


def get_data_type(k: str, display_mode: typing.Optional[str], data: str) -> typing.Optional[str]:
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


def get_ove_app(data_type: str) -> str:
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


def write_media(data: str, cell_no: int, i: int, out: str, host: str) -> str:
    if "http" == data[:4]:
        return data
    if "." not in data:
        raise OVEException("Raw data source not supported")
    filename = f"cell-{cell_no}-{i}.{data.split('.')[-1]}"
    urlretrieve(f"file://{os.path.abspath(data)}", f"{out}/{filename}")
    return f"{host}:8000/{filename}"


def write_data(data: str, cell_no: int, i: int, data_type: str, ove_app: str, host: str, out: str) -> str:
    filename = f"cell-{cell_no}-{i}.{data_type.replace('geo', '')}"
    file_mode = "w"
    file_data = data

    if ove_app == "images":
        file_mode = "wb"
        file_data = base64.b64decode(data)
    if ove_app == "maps":
        file_data = json.dumps(data, indent=4)

    to_file(filename, file_data, file_mode, out)
    return f"{host}:8000/{filename}"


def is_media(data_type: str) -> bool:
    return data_type == "videos" or data_type == "audio"


def split_geometry(geometry: dict, split_mode: str, i: int, i_total: int) -> tuple[int, int, int, int]:
    if split_mode == "width":
        width = math.floor(geometry["w"] / i_total)
        x = geometry["x"] + (i * width)
        y, height = geometry["y"], geometry["h"]
    else:
        height = math.floor(geometry["h"] / i_total)
        y = geometry["y"] + (i * height)
        width, x = geometry["w"], geometry["x"]

    return x, y, width, height


def is_dataframe(data: str, data_type: str) -> bool:
    return data_type == "html" and "dataframe" in data


def handle_data(data: str, cell_no: int, geometry: dict, i: int, i_total: int, split_mode: str, data_type: str,
                ove_host: str, out: str, host: str, space: str) -> dict:
    ove_app = get_ove_app(data_type)
    if is_media(data_type):
        file_url = write_media(data, cell_no, i, out, host)
    else:
        file_url = write_data(data, cell_no, i, data_type, ove_app, host, out)
    x, y, width, height = split_geometry(geometry, split_mode, i, i_total)

    return {
        "app": {
            "states": {
                "load": {
                    "url": file_url
                }
            },
            "url": f"{ove_host}/app/{ove_app}"
        },
        "h": height,
        "w": width,
        "x": x,
        "y": y,
        "space": space
    }


def to_file(filename: str, obj: typing.Any, file_mode: str, out: str) -> None:
    with open(f"{out}/{filename}", file_mode) as f:
        f.write(obj)


def load_section(cell_no: int, i: int, section: dict, sections: list[dict], mode: str, ove_host: str) -> int:
    section_id = sections.get(f"{cell_no}-{i}", None)
    if section_id is not None:
        if mode == "production":
            requests.delete(f"{ove_host}/sections/{section_id['id']}")
        else:
            print(f"DELETE: {ove_host}/sections/{section_id['id']}")

    if mode == "production":
        return requests.post(f"{ove_host}/section", json=section).json()["id"]
    else:
        print(f"POST: {ove_host}/section - {section}")
        return len(sections)


def format_project(sections: list[dict], space: str) -> dict:
    outline = read_file(f"{get_dir()}/assets/project.json")
    return json.loads(outline.replace("%%space%%", space).replace("%%sections%%", json.dumps(
        [section["data"] for section in sections.values()])))


def to_project(sections: list[dict], space: str, out: str) -> None:
    with open(f"{out}/project.json", "w") as f:
        json.dump(format_project(sections, space), f, indent=4)


def get_injected(content: typing.Any) -> dict:
    with capture_output(True, True, True) as io:
        display(content)
    return io._outputs[0]


def format_cell_name(cell_name: str) -> str:
    xs = cell_name.split("-")
    return f"{xs[0]}.{xs[1]}" if int(xs[1]) > 0 else f"{xs[0]}"


def get_app_url(section: dict) -> str:
    return section["data"]["app"]["url"]


def create_controller_nav_content(sections: list[dict]) -> str:
    if len(sections) == 0:
        return ""
    return "\n\t\t\t".join([
        f"<li><button onclick=\"changeContent('{get_app_url(section)}/control.html?oveSectionId={section['id']}')\">Cell {format_cell_name(k)} - {get_app_url(section).split('/')[-1]}</button></li>"
        for k, section in sections.items()])


def get_controller_start_url(sections: list[dict]) -> str:
    if len(sections) == 0:
        return ""
    k_, section_id = min([(k, v["id"]) for k, v in sections.items()], key=lambda x: x[1])
    return f"{sections[k_]['data']['app']['url']}/control.html?oveSectionId={section_id}"


def create_controller(sections: list[dict]) -> str:
    content = create_controller_nav_content(sections)
    start_url = get_controller_start_url(sections)
    outline = read_file(f"{get_dir()}/assets/controller_format.html")
    return outline.replace("%%content%%", content).replace("%%start_url%%", start_url)


def format_latex(latex: str) -> str:
    latex = latex.replace("\\displaystyle ", "").replace("\\\\", "\\")
    if "$$" not in latex:
        latex = latex.replace("$", "$$")
    latex = latex_to_html(latex)
    outline = read_file(f"{get_dir()}/assets/latex_format.html")
    return outline.replace("%%replace%%", latex)


def format_html(html: str) -> str:
    html_format = "<!DOCTYPE html>\n<html lang=\"en\">"
    if len(html) > len(html_format) and html[:len(html_format)] == html_format:
        return html

    outline = read_file(f"{get_dir()}/assets/html_format.html")
    return outline.replace("%%replace%%", html)


def get_source(data: str) -> str:
    return re.search(r"src=\"([^\"]+)\"", data).group(1)


def get_section(v: str, cell_no: int, geometry: dict, i: int, i_total: int, split_mode: str, data_type: str,
                metadata: dict, ove_host: str, out: str, host: str, space: str) -> typing.Optional[dict]:
    if data_type == None:
        return None

    if data_type == "audio":
        v = get_source(v)
    elif data_type == "videos":
        v = get_source(v)
    elif data_type == "dataframe":
        v = format_dataframe(v)
        data_type = "html"
    elif data_type == "html":
        v = format_html(v)
        data_type = "html"
    elif data_type == "latex":
        v = format_latex(v)
        data_type = "html"
    elif data_type == "markdown":
        v = format_markdown(v, out)
        data_type = "html"
    elif data_type == "json":
        v = format_dict(v)
        data_type = "html"
    elif data_type == "geojson":
        v = format_geojson(v, metadata["application/geo+json"])

    return handle_data(v, cell_no, geometry, i, i_total, split_mode, data_type, ove_host, out, host, space)


def get_display_mode(output: dict) -> typing.Optional[str]:
    if output["data"].get("text/plain", None) is None:
        return None

    search = re.search(r"IPython\.(?:core|lib)\.display\.([^ ]+)", output["data"]["text/plain"])
    if not bool(search):
        return None

    return search.group(1)


def get_split_mode(split: bool, geometry: dict) -> bool:
    return split if split is not None else ("width" if geometry["w"] > geometry["h"] else "height")


def generate_controller(sections: list[dict], out: str) -> None:
    with open(f"{out}/controller.html", "w") as f:
        f.write(create_controller(sections))
