import typing
import multiprocessing

from IPython import get_ipython
from dotenv import dotenv_values
from IPython.lib.display import IFrame
from IPython.core import magic_arguments
from IPython.utils.capture import CapturedIO, capture_output
from IPython.core.magic import magics_class, Magics, cell_magic, line_magic

from ove.utils import OVEException, xorExist
from ove.request_handler import RequestHandler
from ove.ove import load_server, load_config, run, load_dir


@magics_class
class OVEMagic(Magics):
    def __init__(self, shell):
        # You must call the parent constructor
        super(OVEMagic, self).__init__(shell)
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

    def inject(self, default_injected: tuple = None, controller_injection: tuple = None):
        if (default_injected is None and controller_injection is None) or (
                default_injected is not None and controller_injection is not None):
            raise OVEException("Unknown injection")

        if default_injected is not None:
            return default_injected[0]._outputs[default_injected[1]]

        section, section_id = controller_injection
        if self.config_["mode"] == "production":
            injected = self.get_injected(
                IFrame(f"{section['app']['url']}/control.html?oveSectionId={section_id}", "100%", "400px"))
        else:
            print(f"Injecting: {section['app']['states']['load']['url']}")
            injected = self.get_injected(IFrame(section["app"]["states"]["load"]["url"], "100%", "400px"))

        if injected is not None and not self.config_["multi_controller"]:
            return injected

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

        injected_outputs = []
        io = self.get_output(cell)

        def injection_handler(i: typing.Optional[int] = None, controller_injection: typing.Optional[tuple] = None):
            if not xorExist(i, controller_injection):
                raise OVEException("Unknown injection")
            if i is not None:
                injected_outputs.append(self.inject((io, i)))
            else:
                injected_outputs.append(self.inject(controller_injection))

        run(self.config_, args, io._outputs, injection_handler)

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

        self.config_ = load_config(args)
        load_dir(self.config_["out"], self.config_["remove"])
        self.server_thread = load_server(self.config_, self.server_thread)

        RequestHandler(self.config_["mode"], self.config_["core"]).clear_space(self.config_["space"])

    @line_magic
    def ove_controller(self, line):
        self.config_["multi_controller"] = True
