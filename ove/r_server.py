from traceback import format_exc
from ove.r_handler import OVEHandler
from http.server import SimpleHTTPRequestHandler
from ove.file_server import Handler, ThreadedHTTPServer


class RServer(Handler):
    def __init__(self, *args, **kwargs):
        self.handler = OVEHandler()
        super().__init__(*args, **kwargs)

    def _send_code(self, code: int):
        self.send_response(code)
        self.end_headers()

    def _load_and_decode(self):
        return self.rfile.read(int(self.headers.get("Content-Length"))).decode("utf-8")

    def do_POST(self) -> None:
        if not self.is_authorized():
            self.send_unauthorised()
        elif self.path == "/source":
            try:
                data = self._load_and_decode()

                if "ove_config" in data:
                    self.handler.ove_config(data)
                else:
                    self.handler.tee_config(data)
                self._send_code(200)
            except Exception as e:
                print(e)
                print(format_exc())
                self._send_code(400)
        elif self.path == "/output":
            try:
                data = self._load_and_decode()

                self.handler.handle_markdown(data)
                self._send_code(200)
            except Exception as e:
                print(e)
                print(format_exc())
                self._send_code(400)
        else:
            self._send_code(404)



def create_server(port, out, config, is_background):
    server = ThreadedHTTPServer(("", port), handler_from(out, is_background, config))
    server.serve_forever()


def handler_from(directory, is_background, config):
    def _init(self, *args, **kwargs):
        return SimpleHTTPRequestHandler.__init__(self, *args, directory=self.directory, **kwargs)

    return type(f"HandlerFrom<{directory}>",
                (RServer,),
                {"__init__": _init, "directory": directory, "is_background": is_background, "config": config,
                 "handler": OVEHandler()})
