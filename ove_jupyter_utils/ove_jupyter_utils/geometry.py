import math
import typing

from enum import Enum
from .utils import OVEException
from .layout_validator import DisplayType


class SplitMode(Enum):
    WIDTH = "width"
    HEIGHT = "height"

    @classmethod
    def get_split_mode(cls, split: bool, position: dict):
        return cls(split) if split is not None else (cls.WIDTH if position["w"] > position["h"] else cls.HEIGHT)


class Geometry:
    def __init__(self, args: dict, mode: DisplayType, section_geometry: dict, rows: int,
                 cols: int, split_mode: typing.Optional[str]) -> dict:
        position = self._get_position(args, mode, section_geometry, rows, cols)
        self.split_mode = SplitMode.get_split_mode(split_mode, position)
        self.x, self.y, self.width, self.height = position["x"], position["y"], position["w"], position["h"]

    def _get_position(self, args: dict, mode: DisplayType, section_geometry: dict, rows: int,
                      cols: int) -> dict:
        if mode == DisplayType.AUTOMATIC:
            section_width, section_height = math.floor(section_geometry["w"] / cols), math.floor(
                section_geometry["h"] / rows)
            cur_col, cur_row = math.floor((args.cell_no - 1) / rows), (args.cell_no - 1) % rows

            if cur_col >= cols:
                raise OVEException("Unable to display cell - limit reached")

            return {"x": cur_col * section_width, "y": cur_row * section_height, "w": section_width,
                    "h": section_height}
        elif mode == DisplayType.GRID:
            section_width, section_height = math.floor(section_geometry["w"] / cols), math.floor(
                section_geometry["h"] / rows)
            return {"x": (args.col - 1) * section_width, "y": (args.row - 1) * section_height,
                    "w": section_width, "h": section_height}
        elif mode == DisplayType.PIXEL:
            return {"x": args.x, "y": args.y, "w": args.width, "h": args.height}
        elif mode == DisplayType.FLEX:
            tlc, blc, trc, brc = args.from_[0] - 1, args.from_[1] - 1, args.to_[0] - 1, args.to_[1] - 1
            x_span, y_span = trc - tlc, brc - blc
            cell_width, cell_height = math.floor(section_geometry["w"] / cols), math.floor(section_geometry["h"] / rows)
            section_width, section_height = cell_width * x_span, cell_height * y_span
            return {"x": tlc * cell_width, "y": blc * cell_height, "w": section_width, "h": section_height}
        else:
            raise OVEException(f"Unknown display mode: {mode}")

    def split(self, i: int, i_total: int) -> tuple[int, int, int, int]:
        if self.split_mode == SplitMode.WIDTH:
            width = math.floor(self.width / i_total)
            x = self.x + (i * width)
            y, height = self.y, self.height
        elif self.split_mode == SplitMode.HEIGHT:
            height = math.floor(self.height / i_total)
            y = self.y + (i * height)
            width, x = self.width, self.x
        else:
            raise OVEException(f"Unknown split mode: {self.split_mode}")

        return x, y, width, height
