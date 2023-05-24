import os
import re
import sys
import html

from io import StringIO
from dotenv import dotenv_values
from socketserver import ThreadingMixIn
from urllib.parse import quote, unquote
from http.server import SimpleHTTPRequestHandler, HTTPServer


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.is_background = kwargs["is_background"]
        self.config = kwargs["config"]
        super().__init__(*args, directory=kwargs["directory"], **kwargs)

    def _is_authorized(self):
        config = {k: v for k, v in dotenv_values(self.config).items() if "OVE_" == k[:4]}
        username = config.get("OVE_USERNAME", None)
        password = config.get("OVE_PASSWORD", None)

        if username is None and password is None:
            return True

        if username is None and password is not None or username is not None and password is None:
            raise Exception("Please provide both a username and a password")

        auth = self.headers.get("Authorized")
        print(auth)
        return not (auth is None or not auth.startswith("Basic") or auth[6:] != base64.b64decode(
            f"{self.username}:{self.password}"))

    def _send_unauthorised(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", "Basic")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._is_authorized():
            self._send_unauthorised()
            return
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_HEAD(self) -> None:
        if not self._is_authorized():
            self._send_unauthorised()
            return
        return SimpleHTTPRequestHandler.do_HEAD(self)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        SimpleHTTPRequestHandler.end_headers(self)

    def log_message(self, format: str, *args) -> None:
        if self.is_background:
            pass
        else:
            SimpleHTTPRequestHandler.log_message(self, format, *args)

    def copy_file_range(self, in_file, out_file):
        """ Copy only the range in self.range_from/to. """
        in_file.seek(self.range_from)
        # Add 1 because the range is inclusive
        left_to_copy = 1 + self.range_to - self.range_from
        buf_length = 64 * 1024
        bytes_copied = 0
        while bytes_copied < left_to_copy:
            read_buf = in_file.read(min(buf_length, left_to_copy))
            if len(read_buf) == 0:
                break
            out_file.write(read_buf)
            bytes_copied += len(read_buf)
        return bytes_copied

    def send_range_head(self):
        """Common code for GET and HEAD commands.
        This sends the response code and MIME headers.
        Return value is either a file object (which has to be copied
        to the output file by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.
        """
        path = self.translate_path(self.path)
        f = None
        if isdir(path):
            if not self.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.end_headers()
                return None
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return SimpleHTTPRequestHandler.list_directory(self, path)

        if not os.path.exists(path) and path.endswith('/data'):
            # FIXME: Handle grits-like query with /data appended to path
            # stupid grits
            if os.path.exists(path[:-5]):
                path = path[:-5]

        c_type = self.guess_type(path)
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
        except IOError:
            self.send_error(404, "File not found")
            return None

        if self.range_from is None:
            self.send_response(200)
        else:
            self.send_response(206)

        self.send_header("Content-type", c_type)
        fs = fstat(f.fileno())
        file_size = fs.st_size
        if self.range_from is not None:
            if self.range_to is None or self.range_to >= file_size:
                self.range_to = file_size - 1
            self.send_header("Content-Range",
                             "bytes %d-%d/%d" % (self.range_from,
                                                 self.range_to,
                                                 file_size))
            # Add 1 because ranges are inclusive
            self.send_header("Content-Length",
                             (1 + self.range_to - self.range_from))
        else:
            self.send_header("Content-Length", str(file_size))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

    def translate_path(self, path):
        """ Override to handle redirects.
        """
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = os.path.normpath(unquote(path))
        words = path.split('/')
        words = filter(None, words)
        path = self.directory
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.path.curdir, os.path.pardir): continue
            path = os.path.join(path, word)
        return path

    # Private interface ######################################################

    def _get_range_header(self):
        """ Returns request Range start and end if specified.
        If Range header is not specified returns (None, None)
        """
        range_header = self.headers.get("Range")
        if range_header is None:
            return (None, None)
        if not range_header.startswith("bytes="):
            print(f"Not implemented: parsing header Range: {range_header}")
            return (None, None)
        regex = re.compile(r"^bytes=(\d+)-(\d+)?")
        range_thing = regex.search(range_header)
        if range_thing:
            from_val = int(range_thing.group(1))
            if range_thing.group(2) is not None:
                return (from_val, int(range_thing.group(2)))
            else:
                return (from_val, None)
        else:
            print('CANNOT PARSE RANGE HEADER:', range_header)
            return (None, None)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


def create_server(port, out, config, is_background):
    server = ThreadedHTTPServer(("", port), handler_from(out, is_background, config))
    server.serve_forever()


def handler_from(directory, is_background, config):
    def _init(self, *args, **kwargs):
        return SimpleHTTPRequestHandler.__init__(self, *args, directory=self.directory, **kwargs)

    return type(f"HandlerFrom<{directory}>",
                (Handler,),
                {"__init__": _init, "directory": directory, "is_background": is_background, "config": config})


if __name__ == "__main__":
    port_regex = re.compile(
        r"^((6553[0-5])|(655[0-2][0-9])|(65[0-4][0-9]{2})|(6[0-4][0-9]{3})|([1-5][0-9]{4})|([0-5]{0,5})|([0-9]{1,4}))$")
    if len(sys.argv) < 3 or re.match(port_regex, sys.argv[1]) is None or not (
            os.path.exists(sys.argv[2]) and os.path.isdir(sys.argv[2])):
        raise Exception("Please provide a valid port number and working directory")
    if len(sys.argv) > 3 and os.path.exists(sys.argv[3]):
        config = sys.argv[3]
    else:
        config = None
    create_server(int(sys.argv[1]), sys.argv[2], config, is_background=False)
