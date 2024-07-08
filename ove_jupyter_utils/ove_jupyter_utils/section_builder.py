import typing
import uuid

from .ove_app import OVEApp
from .geometry import Geometry
from .data_type import DataType
from .asset_handler import AssetHandler
from .output_formatter import OutputFormatter


class SectionBuilder:
    def __init__(self, renderer: str, asset_handler: AssetHandler, output_formatter: OutputFormatter):
        self.asset_handler = asset_handler
        self.renderer = renderer
        self.formatter = output_formatter

    def convert_section(self, data: dict, canvas: dict, space: str, data_type: DataType) -> dict:
        app = OVEApp.from_data_type(data_type)

        return {
            "app": {
                "states": {
                    "load": {
                        "url": data["asset"]
                    }
                },
                "url": f"{self.renderer}/app/{app.value}"
            },
            "h": data["height"] * canvas["h"],
            "w": data["width"] * canvas["w"],
            "x": data["x"] * canvas["w"],
            "y": data["y"] * canvas["h"],
            "space": space
        }

    def build_section(self, data: str, geometry: Geometry, canvas: dict, cell_no: int, i: int, data_type: DataType, metadata: dict, project_id: str) -> dict:
        data = self.formatter.format_data(data, data_type, metadata)
        asset_filename = self.asset_handler.write_asset(data, cell_no, i, data_type)
        asset_url = self.asset_handler.get_asset_url(asset_filename)
        return {
            "id": str(uuid.uuid4()).replace("-", ""),
            "x": geometry.xs[i],
            "y": geometry.ys[i],
            "width": geometry.widths[i],
            "height": geometry.heights[i],
            "ordering": i,
            "asset": asset_url,
            "assetId": None,
            "dataType": data_type.value.lower(),
            "projectId": project_id,
            "states": ["__default__"]
        }
