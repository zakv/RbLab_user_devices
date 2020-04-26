import sys


if sys.version_info < (3, 7):
    raise RuntimeError("PCOCamera only tested with Python 3.7+")
