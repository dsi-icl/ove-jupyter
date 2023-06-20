import tornado

from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.extension.handler import ExtensionHandlerMixin

from ove_jupyter_utils import custom_hello_world


class OVEJupyterHandler(ExtensionHandlerMixin, JupyterHandler):
    def initialize(self, name):
        ExtensionHandlerMixin.initialize(self, name)

    @tornado.web.authenticated
    def get(self):
        self.finish(custom_hello_world())


class ConfigHandler(ExtensionHandlerMixin, JupyterHandler):
    @tornado.web.authenticated
    def post(self):
        config = self.get_json_body()
        print(config)
        self.finish("config registered")