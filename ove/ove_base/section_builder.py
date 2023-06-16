import typing

from ove.ove_base.ove_app import OVEApp
from ove.ove_base.geometry import Geometry
from ove.ove_base.data_type import DataType
from ove.ove_base.asset_handler import AssetHandler
from ove.ove_base.output_formatter import OutputFormatter


class SectionBuilder:
    def __init__(self, ove_host: str, asset_handler: AssetHandler, output_formatter: OutputFormatter):
        self.asset_handler = asset_handler
        self.ove_host = ove_host
        self.formatter = output_formatter

    def build_section(self, uuid: str, data: str, geometry: Geometry, cell_no: int, i: int, i_total: int, space: str,
                      data_type: DataType, metadata: dict) -> dict:
        app = OVEApp.from_data_type(data_type)
        data = self.formatter.format_data(data, data_type, metadata)
        asset_filename = self.asset_handler.write_asset(uuid, data, cell_no, i, data_type)
        asset_url = self.asset_handler.get_asset_url(asset_filename)
        x, y, width, height = geometry.split(i, i_total)

        return {
            "app": {
                "states": {
                    "load": {
                        "url": asset_url
                    }
                },
                "url": f"{self.ove_host}/app/{app.value}"
            },
            "h": height,
            "w": width,
            "x": x,
            "y": y,
            "space": space
        }
