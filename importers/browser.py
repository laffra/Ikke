import datetime
import os
from os.path import expanduser
import re
import shutil
import sqlite3
from storage import Storage
import sys

if sys.version_info >= (3,):
    import urllib.parse as urlparse
else:
    from urlparse import urlparse

import stopwords
import storage
from threadpool import ThreadPool
import time

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

chrome_epoch = datetime.datetime(1601,1,1)


def get_history_path():
    if os.name == 'nt':
        return ['AppData', 'Local', 'Google', 'Chrome', 'User Data', 'Default', 'history']
    else:
        return ['Library', 'Application Support', 'Google', 'Chrome', 'Default', 'History']

def is_meta_site(url):
    return META_DOMAINS_RE.search(url)


def adjust_chrome_timestamp(chrome_timestamp):
    try:
        delta = datetime.timedelta(microseconds=int(chrome_timestamp))
        return int((chrome_epoch + delta).timestamp())
    except:
        return int(datetime.datetime.now().time())


def process_url(rows):
    for row in rows:
        visit_count, last_visit_time, title, url = row
        if title:
            track(url, title, '', get_favicon(url), '', adjust_chrome_timestamp(last_visit_time), force=True)


def get_favicon(url):
    url = urlparse(url)
    return '%s://%s/favicon.ico' % (url.scheme, url.netloc)


def track(url, title, image, favicon, selection, timestamp=0, force=False):
    url = normalize_url(url)
    domain = urlparse(url).netloc
    if is_meta_site(url):
        return
    if not force and not image and not selection:
        return

    # print('BROWSER: Track %s' % url)
    timestamp = timestamp or datetime.datetime.now().time()
    Storage.add_data({
        'kind': 'browser',
        'uid': url,
        'url': url,
        'domain': domain,
        'label': title,
        'image': image,
        'favicon': favicon,
        'selection': selection,
        'title': title,
        'timestamp': timestamp or datetime.datetime.now().time()
    })


def load_history():
    home = expanduser("~")
    history_path = os.path.join(home, *get_history_path())
    copy_path = history_path + '_copy'
    shutil.copy(history_path, copy_path)
    connection = sqlite3.connect(copy_path)
    cursor = connection.cursor()
    load(cursor, HISTORY_QUERY_URLS, process_url)


def load(cursor, query, processor):
    cursor.execute(query)
    thread_count = 64
    pool = ThreadPool(thread_count)
    print('BROWSER: Loading browser history')
    rows = cursor.fetchall()
    chunk_size = 2 * int(len(rows) / thread_count)
    for n in range(thread_count + 1):
        start, end = n*chunk_size, (n+1)*chunk_size
        pool.add_task(processor, rows[start: end])
    pool.wait_completion()
    print('BROWSER: %d urls added with %d threads with chunksize %d.' % (len(rows), thread_count, chunk_size))


class BrowserItem(storage.Data):
    def __init__(self, obj):
        super(BrowserItem, self).__init__(obj['label'], obj)
        self.kind = obj.get('kind', 'browser')
        self.color = 'navy'
        self.title = self.label = obj.get('label', '')
        self.uid = self.url = obj.get('uid', self.title)
        self.domain = obj.get('domain', '').replace('www.', '')
        if self.domain:
            self.label = self.domain
        self.image = obj.get('image', '')
        self.selection = obj.get('selection', '')
        self.icon = self.image or obj.get('favicon', '')
        self.icon_size = 48 if self.image else 24
        self.font_size = 12 if self.image else 12
        self.zoomed_icon_size = 256 if self.image else 24
        words = '%s %s %s' % (self.title, self.selection, self.url)
        self.words = list(set(stopwords.remove_stopwords(words.replace('+', ' '))))
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
    while url[-1] == '/':
        url = url[:-1]
    return url


def cleanup():
    pass


def poll():
    pass

deserialize = BrowserItem.deserialize


if __name__ == '__main__':
    load_history()

