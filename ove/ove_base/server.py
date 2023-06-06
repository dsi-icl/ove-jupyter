import io
import json
import sys
import traceback
import typing
import argparse

from traceback import format_exc
from ove.ove_base.ove_handler import OVEHandler
from http.server import SimpleHTTPRequestHandler
from ove.ove_base.file_server import BaseHandler, ThreadedHTTPServer


class Server(BaseHandler):
    def __init__(self, *args, **kwargs):
        self.handler = OVEHandler()
        super().__init__(*args, **kwargs)

    def _send_code(self, code: int):
        self.send_response(code)
        self.end_headers()

    def _load_and_decode(self):
        content = self.rfile.read(int(self.headers.get("Content-Length"))).decode("utf-8")
        if self.headers.get("Content-Type") == "application/json":
            return json.loads(content)
        else:
            return content

    def _send_data(self, encoded_data: str, code: int = 200, content_type: str = "text/html") -> None:
        enc = sys.getfilesystemencoding()
        encoded = encoded_data.encode(enc, 'surrogateescape')
        f = io.BytesIO()
        f.write(encoded)
        f.seek(0)
        self.send_response(code)
        self.send_header("Content-type", f"{content_type}; charset=%s" % enc)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        SimpleHTTPRequestHandler.copyfile(self, f, self.wfile)
        f.close()

    def _send_json(self, data: typing.Any) -> None:
        self._send_data(json.dumps(data), content_type="application/json")

    def do_GET(self) -> None:
        if not self.is_authorized():
            self.send_unauthorised()
        elif self.path == "/mode":
            self._send_json({"mode": self.handler.config['mode'].value})
        else:
            SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self) -> None:
        try:
            if not self.is_authorized():
                self.send_unauthorised()
            elif self.path == "/config":
                args = self._load_and_decode()
                if self.headers.get("Content-Type") != "application/json":
                    args = self.handler.parse_config(args)
                else:
                    args = argparse.Namespace(**args)

                self.handler.ove_config(args)
                self._send_code(200)
            elif self.path == "/tee":
                args = self._load_and_decode()
                if self.headers.get("Content-Type") != "application/json":
                    args = self.handler.parse_tee(args)
                else:
                    args = argparse.Namespace(**args)

                self.handler.tee(args)
                self._send_code(200)
            elif self.path == "/output":
                outputs = self._load_and_decode()
                urls = self.handler.handle_output(outputs)
                self._send_json(urls)
            elif self.path == "/controller":
                self.handler.config["multi_controller"] = True
                self._send_code(200)
            else:
                self._send_code(404)
        except Exception as e:
            print("Handling exception")
            self._send_data(format_exc(), code=500)


def create_server(port, out, config, is_background):
    server = ThreadedHTTPServer(("", port), handler_from(out, is_background, config))
    server.serve_forever()


def handler_from(directory, is_background, config):
    def _init(self, *args, **kwargs):
        return SimpleHTTPRequestHandler.__init__(self, *args, directory=self.directory, **kwargs)

    return type(f"HandlerFrom<{directory}>",
                (Server,),
                {"__init__": _init, "directory": directory, "is_background": is_background, "config": config,
                 "handler": OVEHandler()})
