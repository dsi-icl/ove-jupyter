import pathlib

import tornado

from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.extension.handler import ExtensionHandlerMixin
from jupyter_server.files.handlers import FilesHandler

from ove_jupyter_utils import custom_hello_world


class OVEJupyterHandler(ExtensionHandlerMixin, JupyterHandler):
    def initialize(self, name):
        ExtensionHandlerMixin.initialize(self, name)

    @tornado.web.authenticated
    def get(self):
        print(pathlib.Path.cwd())
        # print(self.static_url(".ove"))
        self.finish(custom_hello_world())


class ConfigHandler(ExtensionHandlerMixin, JupyterHandler):
    def initialize(self, name, handler):
        self.handler = handler
        self.name = name

    @tornado.web.authenticated
    def post(self):
        config = self.get_json_body()
        self.handler(config)
        self.finish("{}")


class TeeHandler(ExtensionHandlerMixin, JupyterHandler):
    def initialize(self, name, handler):
        self.handler = handler
        self.name = name

    @tornado.web.authenticated
    def post(self):
        data = self.get_json_body()
        self.finish(self.handler(data))


class StaticHandler(tornado.web.StaticFileHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "*")
        self.set_header("Access-Control-Allow-Methods", "*")


class ModeHandler(ExtensionHandlerMixin, JupyterHandler):
    def initialize(self, name, handler):
        self.name = name
        self.handler = handler
    @tornado.web.authenticated
    def get(self):
        self.finish(self.handler().value)