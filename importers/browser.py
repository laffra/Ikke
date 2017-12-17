import datetime
import logging
import os
from os.path import expanduser
import re
from settings import settings
import shutil
import sqlite3
from storage import Storage
import time
import utils
from urllib.parse import urlparse
import stopwords
import storage
from threadpool import ThreadPool

HISTORY_QUERY_URLS = 'select visit_count, last_visit_time, title, url from urls'
PATH_ATTRIBUTES = {
    'kind',
    'uid',
    'url',
    'domain',
    'image',
    'favicon',
    'selection',
    'label',
    'timestamp',
}

META_DOMAINS = {
    '//www.google.nl',
    '//www.google.com',
    '//mail.google.com',
    '//maps.google.com',
    '//maps.google.com',
    '//ad.doubleclick.net',
    '//rfihub.com',
    '//adnxs.com',
    '//photos.google.com/search',
    '//linkedin.com/search',
    '//localhost:',
}
META_DOMAINS_RE = re.compile('|'.join(META_DOMAINS))
CLEANUP_URL_PATH_RE = re.compile('\W+')
MAX_FILENAME_LENGTH = 76
MAX_FILENAME_FRACTION = 35

chrome_epoch = datetime.datetime(1601,1,1)
is_loading_items = False


def get_history_path():
    if os.name == 'nt':
        return ['AppData', 'Local', 'Google', 'Chrome', 'User Data', 'Default', 'history']
    else:
        return ['Library', 'Application Support', 'Google', 'Chrome', 'Default', 'History']

def is_meta_site(url):
    return META_DOMAINS_RE.search(url)


def adjust_chrome_timestamp(chrome_timestamp):
    delta = datetime.timedelta(microseconds=int(chrome_timestamp))
    return utils.get_timestamp(chrome_epoch + delta)


def process_url(rows):
    if rows:
        for n,row in enumerate(rows):
            visit_count, last_visit_time, title, url = row
            if n % 1000 == 0:
                logging.debug('Add %s %s' % (title, url))
            if title:
                track(url, title, '', get_favicon(url), '', adjust_chrome_timestamp(last_visit_time), force=True)


def get_favicon(url):
    url = urlparse(url)
    return '%s://%s/favicon.ico' % (url.scheme, url.netloc)


def track(url, title, image, favicon, selection, timestamp=0, force=False):
    url = normalize_url(url)
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    filename = re.sub(CLEANUP_URL_PATH_RE, '+', parsed_url.path[1:])
    if len(filename) > MAX_FILENAME_LENGTH:
        filename = filename[:MAX_FILENAME_FRACTION] + '+++' + filename[-MAX_FILENAME_FRACTION:]
    uid = os.path.join(utils.cleanup_filename(domain), utils.cleanup_filename(filename))
    if not force and (is_meta_site(url) or not image and not selection):
        return

    logging.debug('Track %s %s' % (url, image))
    settings.increment('browser/added', 1)
    Storage.add_data({
        'kind': 'browser',
        'uid': uid,
        'url': url,
        'domain': domain,
        'label': title,
        'image': image,
        'favicon': favicon,
        'selection': selection,
        'title': title,
        'words': list(set(word.lower() for word in stopwords.remove_stopwords('%s %s' % (selection, title)))),
        'timestamp': timestamp or utils.get_timestamp()
    })


def load_history():
    home = expanduser("~")
    history_path = os.path.join(home, *get_history_path())
    copy_path = history_path + '_copy'
    shutil.copy(history_path, copy_path)
    connection = sqlite3.connect(copy_path)
    cursor = connection.cursor()
    query = HISTORY_QUERY_URLS
    cursor.execute(query)
    thread_count = 64
    pool = ThreadPool(thread_count)
    logging.info('Loading browser history')
    settings['browser/added'] = 0
    settings['browser/when'] = time.time()
    seen = set()
    rows = []
    for row in cursor.fetchall():
        url = row[-1]
        if not is_meta_site(url) and not url in seen:
            rows.append(row)
        seen.add(url)
    chunk_size = 2 * int(len(rows) / thread_count)
    for n in range(thread_count + 1):
        start, end = n*chunk_size, (n+1)*chunk_size
        pool.add_task(process_url, rows[start: end])
    count = settings['browser/added']
    pool.wait_completion()
    logging.info('%d urls added with %d threads with chunksize %d.' % (count, thread_count, chunk_size))
    logging.info(history())


def history():
    count = Storage.get_item_count('browser')
    if count > 0:
        try:
            dt = datetime.datetime.fromtimestamp(settings.get('browser/when'))
        except:
            dt = datetime.datetime.now()
        when = dt.date()
        return '%d sites loaded from your browser history on %s' % (count, when)
    return 'Nothing loaded yet.'


def can_load_more():
    return True


def delete_all():
    return storage.Storage.clear('browser')


def load():
    global is_loading_items
    is_loading_items = True
    try:
        load_history()
    finally:
        is_loading_items = False


def stop_loading():
    global is_loading_items
    is_loading_items = False


def is_loading():
    return is_loading_items


class BrowserItem(storage.Data):
    def __init__(self, obj):
        super(BrowserItem, self).__init__(obj['label'], obj)
        self.kind = obj.get('kind', 'browser')
        self.color = 'navy'
        self.title = self.label = obj.get('label', '')
        self.uid = obj.get('uid', self.title)
        self.url = obj['url']
        self.domain = obj.get('domain', '').replace('www.', '')
        if self.domain:
            self.label = self.domain
        self.image = obj.get('image', '')
        self.selection = obj.get('selection', '')
        self.icon = self.image or obj.get('favicon', '')
        self.icon_size = 32 if self.image else 24
        self.font_size = 12
        self.zoomed_icon_size = 256 if self.image else 24
        words = '%s %s %s' % (self.title, self.selection, self.url)
        self.timestamp = obj['timestamp']
        self.node_size = 1
        dict.update(self, vars(self))

    @classmethod
    def deserialize(cls, obj):
        return BrowserItem(obj)

    def update(self, obj):
        super(BrowserItem, self).update(obj)
        if self.selection:
            obj['selection'] = '%s %s' % (obj.get('selection', ''), self.selection)
        obj['title'] = obj.get('title', self.title)
        obj['image'] = self.image or obj['image']
        if self.words:
            obj['words'] = list(set(self.words + obj['words']))

    def is_duplicate(self, duplicates):
        if is_meta_site(self.url):
            return True
        if self.domain in duplicates:
            return True
        duplicates.add(self.domain)
        return False


def normalize_url(url):
    while url and url[-1] == '/':
        url = url[:-1]
    return url


def cleanup():
    pass


def poll():
    pass

deserialize = BrowserItem.deserialize


if __name__ == '__main__':
    print(history())
    # load_history()

