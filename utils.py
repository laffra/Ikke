import datetime
import time


def get_timestamp(dt=None):
    try:
        return float(time.mktime(dt.timetuple()))
    except:
        return float(time.mktime(datetime.datetime.now().timetuple()))
