import logging
import os
import psutil
import sys

logger = logging.getLogger(__name__)

KB = 1024
MB = KB * KB
GB = 1024 * MB
TB = 1024 * GB

MEMORY_SIZES = [ "TB", "GB", "MB", "KB" ]


def toHuman(bytes):
    for size in MEMORY_SIZES:
        value = globals()[size]
        if bytes >= value:
            return f"{bytes / value:.1f}{size}"
    return f"{bytes} bytes"


def usage(human=False):
    process = psutil.Process(os.getpid())
    memory = process.memory_info().rss
    return toHuman(memory) if human else memory


def check(max, restart=True):
    memory = usage()
    # handle unfixable memory leak caused by rumps
    if memory > max:
        logger.info(f"Current memory usage is {toHuman(memory)}, which is larger than {toHuman(max)}.")
        if restart:
            os.execl(sys.executable, os.path.abspath(__file__), *sys.argv)
    else:
        logger.info(f"Current memory usage: {toHuman(memory)}, which is less than {toHuman(max)}.")


if __name__ == "__main__":
    logger.info(toHuman(340))
    logger.info(toHuman(2.5*KB))
    logger.info(toHuman(2.5*MB))
    logger.info(toHuman(2.5*GB + 2.5*MB))
    logger.info(toHuman(2.5*TB))
    check(GB, restart=False)
