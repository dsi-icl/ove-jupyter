import os
import json
import pathlib
import tornado
import argparse

from .handlers import OVEJupyterHandler, ConfigHandler, TeeHandler, StaticHandler, ModeHandler
from jupyter_server.extension.application import ExtensionApp
from traitlets import Int

from ove_jupyter_utils.utils import load_base_config

from dotenv import dotenv_values
from ove_jupyter_utils.ove_handler import OVEHandler

class OVEJupyterApp(ExtensionApp):
    name = "ove-jupyter"
    default_url = "/ove-jupyter"
    load_other_extensions = True
    file_url_prefix = "/render"

    static_paths = [os.path.join(pathlib.Path.cwd(), ".ove")]

    ove_config = {}
    ove_handler = OVEHandler()

    def initialize_handlers(self):
        def config_handler(config: dict):
            config["out"] = os.path.join(pathlib.Path.cwd(), config["out"])
            self.static_paths.append(config["out"])
            config["env"] = os.path.join(pathlib.Path.cwd(), config["env"])

            self.ove_handler.load_config(argparse.Namespace(**config))

        def tee_handler(data: dict):
            config = data["config"]
            config["from_"] = config["from"]
            config["to_"] = config["to"]
            config.pop("from")
            config.pop("to")
            return json.dumps(self.ove_handler.tee(argparse.Namespace(**data["config"]), data["outputs"]))

        def mode_handler():
            return self.ove_handler.config["mode"]

        self.handlers.extend([
            (f"{self.default_url}/hello", OVEJupyterHandler),
            (f"{self.default_url}/config", ConfigHandler, {"handler": config_handler}),
            (f"{self.default_url}/tee", TeeHandler, {"handler": tee_handler}),
            (f"{self.default_url}/static/(.*)", StaticHandler, {"path": ".ove"}),
            (f"{self.default_url}/mode", ModeHandler, {"handler": mode_handler})
        ])
        print("Loaded OVE Jupyter Server Extension")