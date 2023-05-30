from enum import Enum
from ove.data_type import DataType
from ove.utils import OVEException


class OVEApp(Enum):
    AUDIO = "audio"
    HTML = "html"
    IMAGES = "images"
    MAPS = "maps"
    SVG = "svg"
    VIDEOS = "videos"

    def is_media(self) -> bool:
        return self.name == "videos" or self.name == "audio"

    @classmethod
    def from_data_type(cls, data_type: DataType):
        if data_type == DataType.HTML or data_type == DataType.DATAFRAME or data_type == DataType.LATEX or data_type == DataType.MARKDOWN or data_type == DataType.JSON:
            return cls.HTML
        elif data_type == DataType.PNG or data_type == DataType.JPEG:
            return cls.IMAGES
        elif data_type == DataType.SVG:
            return cls.SVG
        elif data_type == DataType.GEOJSON:
            return cls.MAPS
        elif data_type == DataType.VIDEO:
            return cls.VIDEOS
        elif data_type == DataType.AUDIO:
            return cls.AUDIO
        else:
            raise OVEException(f"Unknown data type: {data_type}")
