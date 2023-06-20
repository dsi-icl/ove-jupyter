import re
import typing

from enum import Enum
from ove.ove_base.data_type import DataType


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


def to_data_type(display_mode: typing.Optional[IPythonDisplayType], output_type: str, data: str) -> typing.Optional[
    DataType]:
    if display_mode is not None and display_mode == IPythonDisplayType.AUDIO and "text/html" in output_type:
        return DataType.AUDIO
    elif display_mode is not None and (
            display_mode == IPythonDisplayType.VIDEOS or display_mode == IPythonDisplayType.YOUTUBE) and "text/html" in output_type:
        return DataType.VIDEO
    elif "text/html" in output_type:
        return DataType.DATAFRAME if "dataframe" in data else DataType.HTML
    elif "image/png" in output_type:
        return DataType.PNG
    elif "image/jpeg" in output_type:
        return DataType.JPEG
    elif "image/svg+xml" in output_type:
        return DataType.SVG
    elif "text/latex" in output_type:
        return DataType.LATEX
    elif "text/markdown" in output_type:
        return DataType.MARKDOWN
    elif "application/json" in output_type:
        return DataType.JSON
    elif "application/geo+json" in output_type:
        return DataType.GEOJSON
    elif "text/plain" in output_type:
        return None
    else:
        print(f"Unhandled data type: {output_type}")
        return None
