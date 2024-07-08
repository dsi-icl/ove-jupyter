import math
import typing

from enum import Enum
from .utils import OVEException
from .layout_validator import DisplayType


class SplitMode(Enum):
    WIDTH = "width"
    HEIGHT = "height"

    @classmethod
    def get_split_mode(cls, split: str, position: dict):
        return cls(split) if split is not None else (cls.WIDTH if position["w"] > position["h"] else cls.HEIGHT)


class Geometry:
    def __init__(self, args: dict, mode: DisplayType, section_geometry: dict, bounds: dict, i_total: int) -> dict:
        self.split_mode = SplitMode.get_split_mode(args.split, section_geometry)
        positions = self._get_position(args, mode, section_geometry, bounds, i_total)
        self.xs = [position["x"] for position in positions]
        self.ys = [position["y"] for position in positions]
        self.widths = [position["width"] for position in positions]
        self.heights = [position["height"] for position in positions]

    # noinspection DuplicatedCode
    def _get_position(self, args: dict, mode: DisplayType, section_geometry: dict, bounds: dict, i_total: int) -> list[dict]:
        columns, rows = bounds["columns"], bounds["rows"]
        if mode == DisplayType.AUTOMATIC:
            section_width, section_height = 1 / columns, 1 / rows
            cur_col, cur_row = math.floor((args.cell_no - 1) / rows), (args.cell_no - 1) % rows

            if cur_col >= columns:
                raise OVEException("Unable to display cell - limit reached")

            if self.split_mode == SplitMode.WIDTH:
                return [{"x": (cur_col * section_width) + (section_width / i_total) * i, "y": cur_row * section_height, "width": section_width / i_total,
                        "height": section_height} for i in range(i_total)]
            else:
                return [{"x": cur_col * section_width, "y": (cur_row * section_height) + (section_height / i_total) * i, "width": section_width, "height": section_height / i_total} for i in range(i_total)]
        elif mode == DisplayType.GRID:
            section_width, section_height = 1 / columns, 1 / rows
            if (len(args.col) > 1):
                return [{"x": (args.col[i] - 1) * section_width, "y": (args.row[i] - 1) * section_height,
                         "width": section_width, "height": section_height} for i in range(len(args.col))]
            elif self.split_mode == SplitMode.WIDTH:
                return [{"x": (args.col[0] - 1) * section_width + (section_width / i_total) * i, "y": (args.row[0] - 1) * section_height, "width": section_width / i_total, "height": section_height} for i in range(i_total)]
            else:
                return [{"x": (args.col[0] - 1) * section_width, "y": (args.row[0] - 1) * section_height + (section_height / i_total) * i, "width": section_width, "height": section_height / i_total} for i in range(i_total)]
        elif mode == DisplayType.PIXEL:
            if len(args.x) > 1:
                return [{"x": args.x[i], "y": args.y[i], "width": args.width[i], "height": args.height[i]} for i in
                        range(len(args.x))]
            elif self.split_mode == SplitMode.WIDTH:
                return [{"x": args.x[0] + (args.width[0] / i_total) * i, "y": args.y[0], "width": args.width[0] / i_total, "height": args.height[0]} for i in range(i_total)]
            else:
                return [{"x": args.x[0], "y": args.y[0] + (args.height[0] / i_total) * i, "width": args.width[0], "height": args.height[0] / i_total} for i in range(i_total)]
        elif mode == DisplayType.FLEX:
            xs = []
            cell_width, cell_height = 1 / columns, 1 / rows
            if len(args.from_) > 1:
                for i in range(math.floor(len(args.from_) / 2)):
                    tlc, blc, trc, brc = args.from_[i] - 1, args.from_[i + 1] - 1, args.to_[i] - 1, args.to_[i + 1] - 1
                    x_span, y_span = trc - tlc, brc - blc
                    section_width, section_height = cell_width * x_span, cell_height * y_span
                    xs.append(
                        {"x": tlc * cell_width, "y": blc * cell_height, "width": section_width, "height": section_height})
            elif self.split_mode == SplitMode.WIDTH:
                for i in range(i_total):
                    tlc, blc, trc, brc = args.from_[0] - 1, args.from_[1] - 1, args.to_[0] - 1, args.to_[1] - 1
                    x_span, y_span = trc - tlc, brc - blc
                    section_width, section_height = cell_width * x_span, cell_height * y_span
                    xs.append({"x": tlc * cell_width + (section_width / i_total) * i, "y": blc * cell_height, "width": section_width / i_total, "height": section_height})
            else:
                for i in range(i_total):
                    tlc, blc, trc, brc = args.from_[0] - 1, args.from_[1] - 1, args.to_[0] - 1, args.to_[1] - 1
                    x_span, y_span = trc - tlc, brc - blc
                    section_width, section_height = cell_width * x_span, cell_height * y_span
                    xs.append({"x": tlc * cell_width, "y": blc * cell_height + (section_height / i_total) * i, "width": section_width, "height": section_height / i_total})
            return xs
        else:
            raise OVEException(f"Unknown display mode: {mode}")
