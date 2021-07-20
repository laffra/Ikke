import datetime
import os
import psutil
import sys
import re
import time


CLEANUP_FILENAME_RE = re.compile(r'[~#%&*{}:<>?+|"]')
INSTALL_FOLDER = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
HOME_DIR = os.path.join(os.path.expanduser('~'), 'IKKE')
HOME_DIR_SEGMENT_COUNT = len(HOME_DIR.split(os.path.pathsep))
ITEMS_DIR = os.path.join(HOME_DIR, 'items')
FILE_DIR = os.path.join(ITEMS_DIR, 'file')
CONTACT_DIR = os.path.join(ITEMS_DIR, 'contact')

os.chdir(INSTALL_FOLDER)

def get_timestamp(dt=None):
    try:
        return float(time.mktime(dt.timetuple()))
    except:
        return float(time.mktime(datetime.datetime.utcnow().timetuple()))

KB = 1024
MB = 1024 * KB
GB = 1024 * MB
TB = 1024 * GB

def get_memory():
    process = psutil.Process(os.getpid())
    memory = process.memory_full_info()
    # rss vms shared text lib data dirty uss pss swap
    total = memory.rss
    if total < KB: return '%d' % total
    if total < MB: return '%.1dKB' % (total / KB)
    if total < GB: return '%.1dMB' % (total / MB)
    if total < TB: return '%.1dGB' % (total / GB)
    return '%d' % total

def cleanup_filename(filename):
    return re.sub(CLEANUP_FILENAME_RE, '_', filename)

