import copy
import json
import time
import typing
import logging
import requests
import multiprocessing

from IPython import get_ipython
from IPython.lib.display import IFrame
from IPython.core import magic_arguments
from IPython.utils.capture import CapturedIO, capture_output
from IPython.core.magic import magics_class, Magics, cell_magic, line_magic

from ove.utils import load_base_config
from ove.ove_base.server import create_server
from ove.ove_base.file_handler import FileHandler
from ove.utils import OVEException, xorExist, get_dir
from ove.ipython.ipython_display_type import IPythonDisplayType, to_data_type


@magics_class
class OVEMagic(Magics):
    def __init__(self, shell):
        # You must call the parent constructor
        super(OVEMagic, self).__init__(shell)
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        self.config_ = {}
        self.server_thread = None

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
        mode = requests.get(f"{self.config_['host']}:{self.config_['port']}/mode").json()["mode"]
        if mode == "production":
            return self.get_injected(IFrame(controller_injection, "100%", "400px"))
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

            injected["output_idx"] = [io._outputs[output_idx]]

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

    def load_server(self, server_thread: multiprocessing.Process) -> None:
        # pass
        if self.server_thread is not None:
            self.server_thread.terminate()

        self.server_thread = multiprocessing.Process(target=create_server,
                                                     args=(8000, self.config_["out"], self.config_["env"], True))
        self.server_thread.start()
        FileHandler().copy(f"{get_dir()}/ove_base/file_server.py", f"{self.config_['out']}/file_server.py")

    @magic_arguments.magic_arguments()
    @magic_arguments.argument("cell_no", type=int)
    @magic_arguments.argument("--row", "-r", type=int, default=None, nargs="?")
    @magic_arguments.argument("--col", "-c", type=int, default=None, nargs="?")
    @magic_arguments.argument("--width", "-w", type=int, default=None, nargs="?")
    @magic_arguments.argument("--height", "-h", type=int, default=None, nargs="?")
    @magic_arguments.argument("--x", "-x", type=int, default=None, nargs="?")
    @magic_arguments.argument("--y", "-y", type=int, default=None, nargs="?")
    @magic_arguments.argument("--from", "-f", type=int, default=None, nargs=2, dest="from_")
    @magic_arguments.argument("--to", "-t", type=int, default=None, nargs=2, dest="to_")
    @magic_arguments.argument("--split", "-s", type=str, default=None, nargs="?")
    @cell_magic
    def tee(self, line, cell):
        args = magic_arguments.parse_argstring(self.tee, line)
        requests.post(f"{self.config_['host']}:{self.config_['port']}/tee", json=vars(args))

        io = self.get_output(cell)
        formatted_outputs, injected = self.format_ipython(io)
        controller_urls = requests.post(f"{self.config_['host']}:{self.config_['port']}/output",
                                        json=formatted_outputs).json()

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
    @magic_arguments.argument("--space", "-s", type=str, default="LocalFour", nargs="?")
    @magic_arguments.argument("--rows", "-r", type=int, default="2", nargs="?")
    @magic_arguments.argument("--cols", "-c", type=int, default="2", nargs="?")
    @magic_arguments.argument("--env", "-e", type=str, default=".env", nargs="?")
    @magic_arguments.argument("--out", "-o", type=str, default=".ove", nargs="?")
    @magic_arguments.argument("--remove", "-rm", type=bool, default=True, nargs="?")
    @magic_arguments.argument("--mode", "-m", type=str, default="production", nargs="?")
    @line_magic
    def ove_config(self, line):
        args = magic_arguments.parse_argstring(self.ove_config, line)
        self.config_ = load_base_config(args)
        self.load_server(self.server_thread)
        time.sleep(1)

        requests.post(f"{self.config_['host']}:{self.config_['port']}/config", json=vars(args))

    @line_magic
    def ove_controller(self, line):
        requests.post(f"{self.config_['host']}:{self.config_['port']}/controller")
