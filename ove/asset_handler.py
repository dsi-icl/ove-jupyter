import os
import json
import base64

from ove.data_type import DataType
from ove.file_handler import FileHandler
from ove.utils import get_dir, OVEException


class AssetHandler:
    def __init__(self, out_dir: str, host: str, file_handler: FileHandler):
        self.file_handler = file_handler
        self.out_dir = out_dir
        self.host = host

    def handle_markdown_css(self) -> None:
        self.file_handler.copy(f"{get_dir()}/assets/markdown-github.css", f"{self.out_dir}/markdown-github.css")

    def write_asset(self, data: str, cell_no: int, i: int, data_type: DataType):
        if type(data) == str:
            if "http" == data[:4]:
                return data
            elif "." == data[0] or "/" == data[0]:
                filename = self._get_filename(data, data_type, cell_no, i, is_raw=False)
                self.file_handler.copy(os.path.abspath(data), f"{self.out_dir}/{filename}")
                return filename
        if data_type.is_media():
            raise OVEException("Raw data source not supported")
        filename = self._get_filename(data, data_type, cell_no, i, is_raw=True)
        self._write_asset(data, filename, data_type)
        return filename

    def get_asset_url(self, asset_filename: str) -> str:
        return f"{self.host}/{asset_filename}"

    def _get_filename(self, data: str, data_type: DataType, cell_no: int, i: int, is_raw: bool) -> str:
        if is_raw:
            return f"cell-{cell_no}-{i}.{data_type.get_file_extension()}"
        else:
            return f"cell-{cell_no}-{i}.{data.split('.')[-1]}"

    def _write_asset(self, data: str, filename: str, data_type: DataType) -> str:
        data, file_mode = self._format_asset(data, data_type)

        self.file_handler.to_file(data, f"{self.out_dir}/{filename}", file_mode)
        return filename

    def _format_asset(self, data: str, data_type: DataType) -> tuple[str, str]:
        if data_type == DataType.PNG or data_type == DataType.JPEG:
            return base64.b64decode(data), "wb"
        elif data_type == DataType.GEOJSON:
            return json.dumps(data, indent=4), "w"
        else:
            return data, "w"
