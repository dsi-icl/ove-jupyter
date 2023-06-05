import os
import re
import argparse

from ove.ove_base.server import create_server
from ove.ove_base.file_server import get_parser


if __name__ == "__main__":
    args = get_parser().parse_args()
    create_server(args.port, args.out, args.env, is_background=False)
