from loguru import logger
import sys
from functools import partialmethod


def setup_logging(debug: bool = False):
    if debug:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        info_fmt = "{time:YYYY-MM-DD HH:mm:ss}: <lvl>{message}</lvl>"
        logger.add(sys.stderr, level="INFO", format=info_fmt)
        logger.level("info", no=20, color="<white>")
        logger.__class__.foobar = partialmethod(logger.__class__.log, "info")
