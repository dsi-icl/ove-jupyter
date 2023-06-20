import pathlib

from .handlers import OVEJupyterHandler, ConfigHandler
from jupyter_server.extension.application import ExtensionApp
from traitlets import Int

from dotenv import dotenv_values

class OVEJupyterApp(ExtensionApp):
    name = "ove-jupyter"
    default_url = "/ove-jupyter"
    load_other_extensions = True
    file_url_prefix = "/render"

    def initialize_settings(self):
        self.serverapp.web_app.settings.update({
            "rows": self.settings.get("rows", 2),
            "cols": self.settings.get("cols", 2),
            "space": self.settings.get("space", "LocalFour"),
        })

    def initialize_handlers(self):
        self.handlers.extend([
            (f"{self.default_url}/hello", OVEJupyterHandler),
            (f"{self.default_url}/config", ConfigHandler)
        ])
        print("Loaded OVE Jupyter Server Extension")