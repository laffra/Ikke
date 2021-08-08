import datetime
from importers import Importer
import json
import logging
import os
from os.path import expanduser
import re
from settings import settings
import shutil
import sqlite3
from storage import Storage
import sys
import time
import utils
from urllib.parse import urlparse
import stopwords
import storage
from threadpool import ThreadPool

HISTORY_QUERY_URLS = 'select visit_count, last_visit_time, title, url from urls'

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
    '//search.ikke.io',
    '//file:',
    '//localhost:',
    '//127.0.0.1:',
}
META_DOMAINS_RE = re.compile('|'.join(META_DOMAINS))
CLEANUP_URL_PATH_RE = re.compile('\W+')
MAX_FILENAME_LENGTH = 76
MAX_FILENAME_FRACTION = 35

chrome_epoch = datetime.datetime(1601,1,1)
is_loading_items = False
logger = logging.getLogger(__name__)


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
            if not settings['browser/loading']:
                break
            visit_count, last_visit_time, title, url = row
            if n % 1000 == 0:
                logger.debug('Add %s %s' % (title, url))
            if title:
                save_image(url, title, '', get_favicon(url), '', adjust_chrome_timestamp(last_visit_time), force=True)


def get_favicon(url):
    url = urlparse(url)
    return '%s://%s/favicon.ico' % (url.scheme, url.netloc)


def save_image(url, title, image, favicon, selection, timestamp=0, force=False):
    if is_meta_site(url):
        return
    domain = urlparse(url).netloc
    timestamp = timestamp or utils.get_timestamp()
    title = ' '.join(stopwords.remove_stopwords(title))
    uid = '#'.join([domain, title])
    data = Storage.get_data("browser", uid)
    selection = "%s %s" % (selection, data.get("selection", "") if data else "")
    image = image or data.get("image", image) if data else ""
    selection = ' '.join(stopwords.remove_stopwords(selection))
    settings.increment('browser/added')
    settings.increment('browser/count')
    logger.info("Save browser image %s image=%s timestamp=%s selection=%s" % (url, image, timestamp, selection))
    Storage.add_data({
        'kind': 'browser',
        'uid': uid,
        'url': url,
        'domain': domain,
        'label': domain,
        'image': image,
        'icon': favicon,
        'selection': selection,
        'title': title,
        'timestamp': timestamp,
    })
    update_timestamp(timestamp)


def update_timestamp(timestamp):
    settings['browser/timestamp_before'] = max(timestamp, settings.get('browser/timestamp_before', 0))
    settings['browser/timestamp_after'] = min(timestamp, settings.get('browser/timestamp_after', sys.maxsize))


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
    logger.info('Loading browser history')
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
    logger.info('%d urls added with %d threads with chunksize %d.' % (count, thread_count, chunk_size))


def get_status():
    return Importer.get_status("browser", "site")


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


class BrowserNode(storage.Data):
    def __init__(self, obj):
        super(BrowserNode, self).__init__(obj.get('label','???'), obj)
        self.kind = 'browser'
        self.uid = obj['uid']
        self.image = obj.get('image','')
        self.url = obj.get('url', '')
        print("UID:", obj["uid"])
        self.domain, self.title = obj['uid'].split('#')
        self.timestamp = float(obj.get('timestamp', '0'))
        self.label = self.domain
        self.selection = obj.get('selection', '')
        words = (self.selection + ' ' + self.title).split(' ')
        self.words = list(set(word.lower() for word in words))
        self.color = 'navy'
        self.icon = obj['icon'] if ".google.com" in self.url else self.image or obj["icon"]
        self.icon_size = 24 if ".google.com" in self.url else 48 if self.image else 24
        self.font_size = 12
        self.zoomed_icon_size = 182
        self.node_size = 1
        dict.update(self, vars(self))

    @classmethod
    def deserialize(cls, obj):
        return BrowserNode(obj)

    def update(self, obj):
        super(BrowserNode, self).update(obj)
        if self.selection:
            obj['selection'] = '%s %s' % (obj.get('selection', ''), self.selection)
        obj['title'] = obj.get('title', self.title)
        obj['image'] = self.image or obj['image']
        if self.words:
            words = list(set(self.words + obj['words']))
            obj['words'] = ' '.join(stopwords.remove_stopwords(' '.join(words)))

    def is_related_item(self, other):
        return other.kind == 'browser' and self.domain == other.domain

    def __eq__(self, other):
        return other.kind == 'browser' and self.domain == other.domain and self.timestamp == other.timestamp and self.title == other.title

    def __hash__(self):
        return hash("%s-%s" % (self.domain, self.title))

    def is_duplicate(self, duplicates):
        if is_meta_site(self.url) or self.domain in duplicates:
            self.mark_duplicate()
            return True
        duplicates.add(self.domain)
        return False


def render(args):
    return '<script>document.location=\'%s\';</script>' % args.get("url", json.dumps(args))


def cleanup():
    pass


def poll():
    pass


settings['browser/can_load_more'] = True
settings['browser/can_delete'] = True

deserialize = BrowserNode.deserialize

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    load_history()
    for n,obj in enumerate(Storage.search('reddit', days=100000)):
        logger.info('Result %d: %s', n, json.dumps(obj, indent=4))

