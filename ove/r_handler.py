import re
import markdown

from argparse import ArgumentParser
from ove.request_handler import RequestHandler
from ove.ove import load_config, run, load_dir


class OVEHandler:
    def __init__(self):
        self.config = {}
        self.config_parser = self._build_config_parser()
        self.tee_parser = self._build_tee_parser()
        self.args = None

    def _build_config_parser(self) -> ArgumentParser:
        parser = ArgumentParser(add_help=False)
        parser.add_argument("-s", "--space", type=str, default="LocalFour", nargs="?")
        parser.add_argument("-r", "--rows", type=int, default=2, nargs="?")
        parser.add_argument("-c", "--cols", type=int, default=2, nargs="?")
        parser.add_argument("-e", "--env", type=str, default=".env", nargs="?")
        parser.add_argument("-o", "--out", type=str, default=".ove", nargs="?")
        parser.add_argument("-rm", "--remove", type=bool, default=True, nargs="?")
        parser.add_argument("-m", "--mode", type=str, default="production", choices=["development", "production"],
                            nargs="?")
        return parser

    def _build_tee_parser(self) -> ArgumentParser:
        parser = ArgumentParser(add_help=False)
        parser.add_argument("cell_no", type=int)
        parser.add_argument("-r", "--row", type=int, default=None, nargs="?")
        parser.add_argument("-c", "--col", type=int, default=None, nargs="?")
        parser.add_argument("-w", "--width", type=int, default=None, nargs="?")
        parser.add_argument("-h", "--height", type=int, default=None, nargs="?")
        parser.add_argument("-x", "--x", type=int, default=None, nargs="?")
        parser.add_argument("-y", "--y", type=int, default=None, nargs="?")
        parser.add_argument("-f", "--from", type=int, default=None, nargs=2, dest="from_")
        parser.add_argument("-t", "--to", type=int, default=None, nargs=2, dest="to_")
        parser.add_argument("-s", "--split", type=str, default=None, nargs="?")
        return parser

    def ove_config(self, data: str) -> None:
        matches = re.search(r"# ?ove_config ?(.*)", data)
        if matches is None:
            return
        line = matches.group(1)
        args = self.config_parser.parse_args(line.split(" "))
        self.config = load_config(args)
        load_dir(self.config["out"], self.config["remove"])

        RequestHandler(self.config["mode"], self.config["core"]).clear_space(self.config["space"])

    def handle_markdown(self, data: str) -> None:
        outputs = [{"data": {"text/plain": "r-markdown", "text/markdown": data}, "metadata": {}}]
        run(self.config, self.args, outputs, injection_handler=None)

    def tee_config(self, data: str) -> None:
        matches = re.search(r"# ?tee ?(.*)", data)
        if matches is None:
            return
        line = matches.group(1)
        self.args = self.tee_parser.parse_args(line.split(" "))
