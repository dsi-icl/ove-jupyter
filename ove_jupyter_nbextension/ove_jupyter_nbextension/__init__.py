from .app import OVEJupyterApp
from jupyter_server.serverapp import ServerApp


def _jupyter_server_extension_points():
    return [
        {"module": "ove_jupyter_nbextension.app", "app": OVEJupyterApp}
    ]


launch_instance = OVEJupyterApp.launch_instance

load_jupyter_server_extension = OVEJupyterApp.load_classic_server_extension