import os
import re
import argparse

from ove.ove_base.server import create_server
from ove.ove_base.file_server import get_parser
from ove.ove_base.locks import LATEX_LOCK


if __name__ == "__main__":
    args = get_parser().parse_args()
    if LATEX_LOCK is None:
        raise Exception("No locking available")
    create_server(args.port, args.out, args.env, is_background=False)
