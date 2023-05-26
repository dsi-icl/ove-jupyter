import os
import re
import typing

from enum import Enum


class Mode(Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class OVEException(Exception):
    def __init__(self, message):
        super().__init__(f"OVE Error: {message}")


def get_dir() -> str:
    return "/".join(os.path.realpath(__file__).split("/")[:-1])


def get_source(data: str) -> str:
    return re.search(r"src=\"([^\"]+)\"", data).group(1)


def format_cell_name(cell_name: str) -> str:
    xs = cell_name.split("-")
    return f"{xs[0]}.{xs[1]}" if int(xs[1]) > 0 else f"{xs[0]}"


def get_app_url(section: dict) -> str:
    return section["data"]["app"]["url"]


def is_dataframe(data: str, data_type: str) -> bool:
    return data_type == "html" and "dataframe" in data


def xorExist(a: typing.Optional[typing.Any], b: typing.Optional[typing.Any]):
    return (a is not None and b is None) or (a is None and b is not None)
