import typing
from enum import Enum

from .utils import OVEException


class DataType(Enum):
    AUDIO = "audio"
    DATAFRAME = "dataframe"
    GEOJSON = "geojson"
    HTML = "html"
    JPEG = "jpg"
    JSON = "json"
    LATEX = "latex"
    MARKDOWN = "markdown"
    PNG = "png"
    SVG = "svg"
    VIDEO = "videos"

    def get_file_extension(self):
        if self == DataType.LATEX or self == DataType.MARKDOWN or self == DataType.HTML or self == DataType.DATAFRAME or self == DataType.JSON:
            return "html"
        elif self == DataType.GEOJSON:
            return "json"
        elif self.is_media():
            raise OVEException("Raw media not supported")
        else:
            return self.value

    def is_media(self):
        return self.value == "videos" or self.value == "audio"
