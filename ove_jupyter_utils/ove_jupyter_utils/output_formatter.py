import re
import json
import typing

from markdown import markdown
from IPython.lib.latextools import latex_to_html

from .data_type import DataType
from .file_handler import FileHandler
from .utils import get_dir, get_source
from .asset_handler import AssetHandler
from .locks import LATEX_LOCK, MARKDOWN_LOCK


class OutputFormatter:
    def __init__(self, file_handler: FileHandler, asset_handler: AssetHandler):
        self.file_handler = file_handler
        self.asset_handler = asset_handler

    def format_geojson(self, geojson: str, metadata: dict) -> dict:
        if metadata["layer_options"].get("basemap_id", None) is not None:
            basemap = metadata["url_template"].replace("{basemap_id}", f"{metadata['layer_options']['basemap_id']}")
        else:
            basemap = metadata["url_template"]
        outline = self.file_handler.read_file(f"{get_dir()}/assets/geojson_format.json")
        return json.loads(outline.replace("%%basemap%%", basemap).replace("%%geojson%%", json.dumps(geojson)))

    def format_dict(self, obj: typing.Union[dict, list]) -> str:
        outline = self.file_handler.read_file(f"{get_dir()}/assets/dict_format.html")
        return outline.replace("%%replace%%", json.dumps(obj, indent=4))

    def format_markdown(self, md: str) -> str:
        with MARKDOWN_LOCK:
            self.asset_handler.handle_markdown_css()
            outline = self.file_handler.read_file(f"{get_dir()}/assets/markdown_format.html")
            return outline.replace("%%replace%%", markdown(md))

    def format_dataframe(self, html: str) -> str:
        html = html.replace("border=\"1\" ", "").replace(" style=\"text-align: right;\"", "")
        html = re.sub(r"<style .*>(?:.|\r|\n|\t)*</style>", "", html)
        outline = self.file_handler.read_file(f"{get_dir()}/assets/dataframe_format.html")
        return outline.replace("%%replace%%", html)

    def format_latex(self, latex: str) -> str:
        with LATEX_LOCK:
            latex = latex.replace("\\displaystyle ", "").replace("\\\\", "\\")
            if "$$" not in latex:
                latex = latex.replace("$", "$$")
            latex = latex_to_html(latex)
            outline = self.file_handler.read_file(f"{get_dir()}/assets/latex_format.html")
            return outline.replace("%%replace%%", latex)

    def format_html(self, html: str) -> str:
        html_format = "<!DOCTYPE html>\n<html lang=\"en\">"
        if len(html) > len(html_format) and html[:len(html_format)] == html_format:
            return html

        outline = self.file_handler.read_file(f"{get_dir()}/assets/html_format.html")
        return outline.replace("%%replace%%", html)

    def format_overview(self, observatory: str, bounds: dict, sections: list) -> str:
        outline = self.file_handler.read_file(f"{get_dir()}/assets/overview.html")
        outline = outline.replace("const observatoryName = "";", f"const observatoryName = {observatory};")
        outline = outline.replace("const observatory = {};", f"const observatory = {json.dumps(bounds, indent=2)};")
        outline = outline.replace("const sections = [];",
                                  f"const sections = {json.dumps(sections, indent=2)};")
        return outline

    def format_data(self, data: str, data_type: DataType, metadata: dict) -> str:
        if data_type == DataType.AUDIO:
            return get_source(data)
        elif data_type == DataType.VIDEO:
            return get_source(data)
        elif data_type == DataType.DATATABLE:
            return self.format_dataframe(data)
        elif data_type == DataType.HTML:
            return self.format_html(data)
        elif data_type == DataType.LATEX:
            return self.format_latex(data)
        elif data_type == DataType.MARKDOWN:
            return self.format_markdown(data)
        elif data_type == DataType.JSON:
            return self.format_dict(data)
        elif data_type == DataType.GEOJSON:
            return self.format_geojson(data, metadata)
        else:
            return data
