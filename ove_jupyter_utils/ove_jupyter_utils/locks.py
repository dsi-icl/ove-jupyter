import threading

LATEX_LOCK = threading.RLock()
MARKDOWN_LOCK = threading.RLock()
