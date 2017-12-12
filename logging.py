import inspect
import os


ERROR = 0
WARNING = 1
INFO = 2
DEBUG = 3

KINDS = ['ERROR', 'WARNING', 'INFO', 'DEBUG']

LINE = '=' * 120

LOG_LEVEL = INFO


def log_impl(msg):
    print(msg)


def log(level, msg):
    # type(int, str) -> None
    if level <= LOG_LEVEL:
        log_impl('%s %s: %s' % (caller_info(), KINDS[level], msg))


def warning(msg=''):
    # type(str) -> None
    log(WARNING, msg)


def error(msg=''):
    # type(str) -> None
    log(ERROR, msg)


def info(msg=''):
    # type(str) -> None
    log(INFO, msg)


def debug(msg=''):
    # type(str) -> None
    log(DEBUG, msg)


def caller_info(skip=3):
    frame = inspect.stack()[skip][0]
    path = inspect.getfile(frame)
    base = os.path.dirname(__file__)
    return '%s:%d' % (path[len(base) + 1:], inspect.getlineno(frame))


def set_level(level):
    global LOG_LEVEL
    LOG_LEVEL = level


def get_level():
    return LOG_LEVEL


if __name__ == '__main__':
    set_level(WARNING)
    warning('Tell the user about something potentially harmful.')

    set_level(DEBUG)
    debug('Show a highly verbose internal debugging message.')

    set_level(INFO)
    info('Report end-user level events.')

    set_level(ERROR)
    error('Something seriously wrong happened, execution probably ends now.')
