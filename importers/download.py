import datetime
import os
import logging
from settings import settings
import storage
import time


DOWNLOADS_DIR = os.path.join(os.path.expanduser('~'), 'Downloads')

SKIP_CONTENT = {
    '.zip', '.dmg', '.exe', '.html', '.htm',
}

ONE_WEEK_SECONDS = 7 * 24 * 60 * 60


class Download:
    @classmethod
    def load(cls):
        last_check = settings['download/xlastcheck']
        now = time.time()
        try:
            for path, dirs, files in os.walk(DOWNLOADS_DIR):
                for filename in filter(lambda f: f[0] != '.', files):
                    if not settings['download/loading']:
                        return
                    name, extension = os.path.splitext(filename)
                    file_path = os.path.join(path, filename)
                    timestamp = os.path.getctime(file_path)
                    if timestamp > last_check:
                        if extension.lower() in SKIP_CONTENT:
                            logging.info('skip %s' % filename)
                            continue
                        with open(file_path, 'rb') as fin:
                            settings.increment('file/count')
                            storage.Storage.add_binary_data(fin.read(), {
                                'uid': filename,
                                'kind': 'file',
                                'timestamp': timestamp,
                            })
                        settings.increment('download/count')
                    if now - timestamp > ONE_WEEK_SECONDS:
                        logging.debug('DOWNLOAD: discard', filename)
                        # os.remove(file_path)
        finally:
            settings['download/lastcheck'] = now

    @classmethod
    def history(cls):
        timestamp = settings.get('download/xlastcheck', time.time())
        return datetime.datetime.fromtimestamp(timestamp).date()


def can_load_more():
    return True


load = Download.load
poll = Download.load
history = Download.history


def cleanup():
    pass


if __name__ == '__main__':
    poll()
