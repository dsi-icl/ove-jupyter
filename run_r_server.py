import os
import re
import sys
import argparse

from ove.r_server import create_server


def port_regex(arg_value: str) -> int:
    pattern = re.compile(
        r"^((6553[0-5])|(655[0-2][0-9])|(65[0-4][0-9]{2})|(6[0-4][0-9]{3})|([1-5][0-9]{4})|([0-5]{0,5})|([0-9]{1,4}))$")
    if not pattern.match(arg_value):
        raise argparse.ArgumentTypeError("Invalid port number")
    return int(arg_value)


def is_valid_dir(arg_value: str) -> str:
    if not os.path.exists(arg_value) or not os.path.isdir(arg_value):
        raise argparse.ArgumentTypeError("Invalid output directory")
    return arg_value


def is_valid_file(arg_value: str) -> str:
    if not os.path.exists(arg_value):
        raise argparse.ArgumentTypeError("Invalid config file")
    return arg_value


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", default=8000, type=port_regex, nargs="?")
    parser.add_argument("-o", "--out", default=".ove", type=is_valid_dir, nargs="?")
    parser.add_argument("-e", "--env", default=".env", type=is_valid_file, nargs="?")
    return parser


if __name__ == "__main__":
    args = get_parser().parse_args()
    create_server(args.port, args.out, args.env, is_background=False)
