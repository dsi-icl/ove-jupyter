import typing
from enum import Enum

from ove.utils import OVEException
from ove.ipython_display_type import IPythonDisplayType


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

    @classmethod
    def from_ipython_display_type(cls, output_type: str, display_mode: typing.Optional[IPythonDisplayType],
                                  data: str):
        if display_mode is not None and display_mode == IPythonDisplayType.AUDIO and "text/html" in output_type:
            return cls.AUDIO
        elif display_mode is not None and (
                display_mode == IPythonDisplayType.VIDEOS or display_mode == IPythonDisplayType.YOUTUBE) and "text/html" in output_type:
            return cls.VIDEO
        elif "text/html" in output_type:
            return cls.DATAFRAME if "dataframe" in data else cls.HTML
        elif "image/png" in output_type:
            return cls.PNG
        elif "image/jpeg" in output_type:
            return cls.JPEG
        elif "image/svg+xml" in output_type:
            return cls.SVG
        elif "text/latex" in output_type:
            return cls.LATEX
        elif "text/markdown" in output_type:
            return cls.MARKDOWN
        elif "application/json" in output_type:
            return cls.JSON
        elif "application/geo+json" in output_type:
            return cls.GEOJSON
        elif "text/plain" in output_type:
            return None
        else:
            print(f"Unhandled data type: {output_type}")
            return None

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
