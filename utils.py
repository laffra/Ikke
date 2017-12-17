import datetime
import re
import time


CLEANUP_FILENAME_RE = re.compile(r'[~#%&*{}:<>?+|"]')


def get_timestamp(dt=None):
    try:
        return float(time.mktime(dt.timetuple()))
    except:
        return float(time.mktime(datetime.datetime.now().timetuple()))


def cleanup_filename(filename):
    return re.sub(CLEANUP_FILENAME_RE, '_', filename)

