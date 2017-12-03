import os
from settings import settings
import stopwords
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
        last_check = settings.get('download/xlastcheck', 0)
        now = time.time()

        for path, dirs, files in os.walk(DOWNLOADS_DIR):
            for filename in filter(lambda f: f[0] != '.', files):
                name, extension = os.path.splitext(filename)
                file_path = os.path.join(path, filename)
                timestamp = os.path.getmtime(file_path)
                if timestamp > last_check:
                    if extension.lower() in SKIP_CONTENT:
                        print('DOWNLOAD: skip %s' % filename)
                        continue
                    with open(file_path, 'rb') as fin:
                        storage.Storage.add_binary_data(fin.read(), {
                            'uid': filename,
                            'kind': 'file',
                            'timestamp': timestamp,
                        })
                    print('DOWNLOAD: add %s' % filename)
                if now - timestamp > ONE_WEEK_SECONDS:
                    pass
                    # print('DOWNLOAD: discard', filename)
                    # os.remove(file_path)

        settings['download/lastcheck'] = now


load = Download.load
poll = Download.load


def cleanup():
    pass


if __name__ == '__main__':
    poll()
