import os
import glob
import json
import shutil
import typing


class FileHandler:
    def read_file(self, filename: str) -> str:
        with open(filename) as f:
            return "".join(f.readlines())

    def mkdir(self, dir_: str) -> None:
        if not os.path.exists(dir_):
            os.makedirs(dir_)

    def read_json(self, filename: str) -> typing.Any:
        with open(filename, "r") as f:
            return json.load(f)

    def write_json(self, obj: typing.Any, filename: str, indent: int = 4) -> None:
        with open(filename, "w") as f:
            json.dump(obj, f, indent=indent)

    def copy(self, in_: str, out_: str, overwrite: bool = False):
        if os.path.exists(out_) and not overwrite:
            return
        else:
            shutil.copy(in_, out_)

    def to_file(self, obj: typing.Any, filename: str, file_mode: str) -> None:
        with open(f"{filename}", file_mode) as f:
            f.write(obj)

    def rm(self, dir_: str) -> None:
        for f in glob.glob(f"{dir_}/*"):
            os.remove(f)
