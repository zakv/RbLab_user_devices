import sys
if sys.version_info < (3, 5):
    raise RuntimeError("KDC101 labscript driver requires Python 3.5+")
