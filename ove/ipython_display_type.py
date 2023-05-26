import re
import typing
from enum import Enum


class IPythonDisplayType(Enum):
    AUDIO = "Audio"
    CODE = "Code"
    DISPLAY_HANDLE = "DisplayHandle"
    DISPLAY_OBJECT = "DisplayObject"
    FILE_LINK = "FileLink"
    FILE_LINKS = "FileLinks"
    GEOJSON = "GeoJSON"
    HTML = "HTML"
    IFRAME = "IFrame"
    IMAGE = "Image"
    JAVASCRIPT = "Javascript"
    JSON = "JSON"
    LATEX = "Latex"
    MARKDOWN = "Markdown"
    MATH = "Math"
    PRETTY = "Pretty"
    PROGRESS_BAR = "ProgressBar"
    SVG = "SVG"
    SCRIBD_DOCUMENT = "ScribdDocument"
    TEXT_DISPLAY_OBJECT = "TextDisplayObject"
    VIDEOS = "Video"
    VIMEO = "VimeoVideo"
    YOUTUBE = "YouTubeVideo"

    @classmethod
    def from_ipython_output(cls, output: dict):
        if output["data"].get("text/plain", None) is None:
            return None

        search = re.search(r"IPython\.(?:core|lib)\.display\.([^ ]+)", output["data"]["text/plain"])
        if not bool(search):
            return None

        return cls(search.group(1))

    def format_ipython_output(self, output: dict) -> dict:
        if self == IPythonDisplayType.YOUTUBE:
            output["data"] = {k: v for k, v in output["data"].items() if "image" not in k}

        return output
