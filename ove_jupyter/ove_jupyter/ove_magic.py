import copy
import json
import time
import uuid
import typing
import logging
import requests
import multiprocessing

from IPython import get_ipython
from IPython.lib.display import IFrame
from IPython.core import magic_arguments
from IPython.utils.capture import CapturedIO, capture_output
from IPython.core.magic import magics_class, Magics, cell_magic, line_magic

from ove_jupyter_utils.utils import load_base_config, OVEException, xorExist, get_dir
from ove_jupyter_utils.locks import LATEX_LOCK, MARKDOWN_LOCK
from ove_jupyter_utils.server import create_server
from ove_jupyter_utils.file_handler import FileHandler
from ove_jupyter_utils.ove_handler import OVEHandler
from .ipython_display_type import IPythonDisplayType, to_data_type


@magics_class
class OVEMagic(Magics):
    def __init__(self, shell):
        super(OVEMagic, self).__init__(shell)
        self.ove_handler = OVEHandler()
        self.host = None

    def get_output(self, cell: typing.Any) -> CapturedIO:
        with capture_output(True, True, True) as io:
            get_ipython().run_cell(cell)
        return io

    def get_injected(self, content: typing.Any) -> dict:
        with capture_output(True, True, True) as io:
            display(content)
        return io._outputs[0]

    def inject(self, controller_injection: typing.Optional[str] = None):
        if controller_injection is None:
            return None

        if self.ove_handler.config["mode"].value == "production":
            return self.get_injected(IFrame(controller_injection, "100%", "800px"))
        else:
            print(f"Injecting: {controller_injection}")
            return None

    def format_ipython(self, io: CapturedIO):
        formatted_outputs = []
        injected = {}

        for output_idx, output_ in enumerate(io._outputs):
            output = copy.deepcopy(output_)
            if len(output["data"]) == 0:
                continue

            injected[output_idx] = [io._outputs[output_idx]]

            display_mode = IPythonDisplayType.from_ipython_output(io._outputs[output_idx])
            if display_mode is not None:
                output = display_mode.format_ipython_output(output)

            output["data"] = {k: v for k, v in output["data"].items() if "text/plain" not in k}

            if len(output["data"]) > 1:
                raise OVEException(f"Unexpected output size: {len(output['data'])}")

            for output_type, data in output["data"].items():
                data_type = to_data_type(display_mode, output_type, data)
                metadata = output["metadata"].get(output_type, None)
                formatted_outputs.append((str(output_idx), data_type.value, data, metadata))

        return formatted_outputs, injected

    @magic_arguments.magic_arguments()
    @magic_arguments.argument("cell_no", type=int)
    @magic_arguments.argument("--row", "-r", type=int, default=None, nargs="*")
    @magic_arguments.argument("--col", "-c", type=int, default=None, nargs="*")
    @magic_arguments.argument("--width", "-w", type=str, default=None, nargs="*")
    @magic_arguments.argument("--height", "-h", type=str, default=None, nargs="*")
    @magic_arguments.argument("--x", "-x", type=str, default=None, nargs="*")
    @magic_arguments.argument("--y", "-y", type=str, default=None, nargs="*")
    @magic_arguments.argument("--from", "-f", type=int, default=None, nargs="*", dest="from_")
    @magic_arguments.argument("--to", "-t", type=int, default=None, nargs="*", dest="to_")
    @magic_arguments.argument("--split", "-s", type=str, default="width", nargs="?")
    @cell_magic
    def tee(self, line, cell):
        def optional_float(x):
            if x is None:
                return None
            def opt(y):
                if "/" in y:
                    return float(y.split("/")[0]) / float(y.split("/")[1])
                else:
                    return float(y)
            return [opt(y) for y in x]
        args = magic_arguments.parse_argstring(self.tee, line)
        args.x, args.y, args.width, args.height = optional_float(args.x), optional_float(args.y), optional_float(args.width), optional_float(args.height)

        io = self.get_output(cell)
        formatted_outputs, injected = self.format_ipython(io)
        controller_urls = self.ove_handler.tee(args, formatted_outputs)

        for data in controller_urls:
            idx = int(data["idx"])
            if injected.get(idx, None) is not None:
                injected[idx].append(self.inject(controller_injection=data["url"]))
            else:
                injected[idx] = self.inject(controller_injection=data["url"])

        injected_outputs = []
        for _, v in sorted(injected.items()):
            injected_outputs.extend([x for x in v if x is not None])

        io._outputs = injected_outputs
        io()

    @magic_arguments.magic_arguments()
    @magic_arguments.argument("--observatory", "-os", type=str, default="do", nargs="?")
    @magic_arguments.argument("--env", "-e", type=str, default=".env", nargs="?")
    @magic_arguments.argument("--out", "-o", type=str, default=".ove", nargs="?")
    @magic_arguments.argument("--mode", "-m", type=str, default="production", nargs="?")
    @magic_arguments.argument("--remove", "-rm", type=bool, default=True, nargs="?")
    @magic_arguments.argument("--multi_controller", "-mc", type=bool, default=False, nargs="?")
    @line_magic
    def ove_config(self, line):
        args = magic_arguments.parse_argstring(self.ove_config, line)
        if LATEX_LOCK is None or MARKDOWN_LOCK is None:
            raise Exception("No locking available")
        self.host = load_base_config(args)["host"]
        self.ove_handler.load_config(args)
