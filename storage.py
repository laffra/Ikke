import cache
import datetime
import elasticsearch
from importlib import import_module
import itertools
import json
import logging
import os
import requests
from settings import settings
import shutil
import stat
import stopwords
import subprocess
import traceback
import utils
import time
from collections import defaultdict

FILE_FORMAT_ICONS = {
    'pdf': 'icons/pdf-icon.png',
    'rtf': 'icons/rtf-icon.png',
    'doc': 'icons/word-doc-icon.png',
    'docx': 'icons/word-doc-icon.png',
    'ics': 'icons/calendar-icon.png',
    'xls': 'icons/excel-xls-icon.png',
    'xlsx': 'icons/excel-xls-icon.png',
    'pages': 'icons/keynote-icon.png',
    'ppt': 'icons/ppt-icon.png',
    'ico': 'icons/ico.png',
    'tiff': 'icons/tiff-icon.png',
    'pptx': 'icons/ppt-icon.png',
    'www': 'icons/browser-web-icon.png',
    'txt': 'icons/text-icon.png',
    'file': 'icons/file-icon.png',
}
FILE_FORMAT_IMAGE_EXTENSIONS = { 'png', 'ico', 'jpg', 'jpeg', 'gif', 'pnm' }
ITEM_KINDS = [ 'contact', 'gmail', 'hangouts', 'git', 'browser', 'file' ]
INDEX = "insights"
MAX_NUMBER_OF_ITEMS = 1000

logger = logging.getLogger(__name__)

item_handlers = { }



class Storage:
    stats = defaultdict(int)
    search_cache = cache.Cache(60)
    file_cache = cache.Cache(60)
    history_cache = cache.Cache(60)
    elastic_client = elasticsearch.Elasticsearch([{'host': 'localhost', 'port': '9200'}])

    @classmethod
    def add_data(cls, data):
        cls.elastic_client.index(index=data["kind"], id=data["uid"], body=data)

    @classmethod
    def get_local_path(cls, file):
        # type: (dict) -> str
        local_path = os.path.join(utils.ITEMS_DIR, 'file', file['uid'])
        try:
            os.makedirs(os.path.dirname(local_path))
        except:
            pass # allow multiple threads to create the dir at the same time
        return local_path

    @classmethod
    def add_binary_data(cls, content, data):
        assert 'kind' in data, "Kind needed"
        assert 'uid' in data, "UID needed"
        assert 'timestamp' in data, "Timestamp needed"
        assert type(data['timestamp']) in (int,float), "Number timestamp needed, not %s" % type(data['timestamp'])
        path = cls.get_local_path(data)
        logger.debug('write %s' % path)
        for k,v in data.items():
            logger.debug('     %09s %s' % (k, v))
        try:
            with open(path, "wb") as fout:
                cls.stats['writes'] += 1
                fout.write(content)
            os.utime(path, (data['timestamp'], data['timestamp']))
            if path in cls.file_cache:
                del cls.file_cache[path]
        except IOError as e:
            logger.error('Cannot add file. Path len = %d: %s' % (len(path), e))
            raise

    @classmethod
    def search(cls, query, days=1, doc_type=None):
        # type: (str,int,str) -> list
        assert isinstance(query, str)
        assert isinstance(days, int), 'unexpected type %s: %s' % (type(days), days)
        cls.stats = defaultdict(int)
        search_start = time.time()
        hits = list(itertools.chain(*[
            cls.elastic_client.search(
                index=index,
                doc_type=doc_type,
                size=MAX_NUMBER_OF_ITEMS,
                body={
                    "query": {
                        "query_string": {
                            "query": cls.wildcard(query),
                            "fuzziness": "2",
                            "default_field": "*"
                        }
                    }
                }
            )["hits"]["hits"]
            for index in ITEM_KINDS
            if index != "file"
        ]))
        since = (datetime.datetime.now() - datetime.timedelta(days=days)).timestamp()
        sources = list(filter(None, [hit["_source"] for hit in hits]))
        results = [cls.resolve(source) for source in sources if cls.after(source, since)]
        logger.info("Found %d results for '%s' since %s" % (len(results), query, since))
        cls.record_search_stats(query, time.time() - search_start, len(results))
        return results

    @classmethod
    def after(cls, obj, after_timestamp):
        when = int(obj["timestamp"])
        if obj["kind"] == "git":
            logger.info("     %12s %s  %s %s %s" % (obj["kind"], when, after_timestamp, when-after_timestamp, when > after_timestamp))
        return when > after_timestamp
    
    @classmethod
    def wildcard(cls, query):
        return " ".join("*%s*^5" % word for word in query.split())

    @classmethod
    def resolve(cls, obj):
        return cls.to_item(obj)

    @classmethod
    def get_handler(cls, kind):
        return item_handlers[kind]

    @classmethod
    def record_search_stats(cls, query, duration, count):
        cls.stats['searches'] += 1
        cls.stats['duration'] += duration
        cls.stats['results'] = count
        cls.log_search_stats(query)

    @classmethod
    def log_search_stats(cls, query=None):
        logger.debug('Storage Statistics:')
        if query:
            logger.debug('    query: "%s"' % query)
        for k,v in cls.stats.items():
            logger.debug('    %s: %s' % (k, v))

    @classmethod
    def search_contact(cls, email):
        # type: (str) -> dict
        person = cls.search_cache.get(email)
        if not person:
            cls.search_cache[email] = person
        return person

    @classmethod
    def search_file(cls, filename):
        # type: (str) -> list
        return cls.search(filename, 0)

    @classmethod
    def can_load_more(cls, kind):
        return settings['%s/can_load_more' % kind]

    @classmethod
    def can_delete(cls, kind):
        return settings['%s/count' % kind] > 0

    @classmethod
    def to_item(cls, obj):
        if not "kind" in obj:
            return None
        handler = item_handlers[obj['kind']]
        return handler.deserialize(obj)

    @classmethod
    def get_day_month_year(cls, days):
        # type: (int) -> str
        dt = datetime.datetime.now() - datetime.timedelta(days=days)
        return '%s/%s/%s' % (dt.day, dt.month, dt.year)

    @classmethod
    def get_year_month_day(cls, days):
        # type: (int) -> str
        dt = datetime.datetime.now() - datetime.timedelta(days=days)
        return '%4d-%02d-%02d' % (dt.year, dt.month, dt.day)

    @classmethod
    def setup(cls):
        if not os.path.exists(utils.HOME_DIR):
            os.mkdir(utils.HOME_DIR)
            os.chmod(utils.HOME_DIR, stat.S_IEXEC)

    @classmethod
    def get_item_count(cls, kind):
        path = os.path.join(utils.HOME_DIR, 'items', kind)
        count = sum(len(files) for _,_,files in os.walk(path))
        return count

    @classmethod
    def load(cls, kind):
        if settings['%s/loading' % kind]:
            logger.info('Already loading %s' % kind)
            return
        logger.info('Load %s' % kind)
        try:
            settings['%s/loading' % kind] = True
            item_handlers[kind].load()
        except Exception as e:
            logger.error('Could not load %s: %s' % (kind, e))
        finally:
            settings['%s/loading' % kind] = False

    @classmethod
    def stop_loading(cls, kind):
        settings['%s/loading' % kind] = False

    @classmethod
    def loading(cls, kind):
        return settings['%s/loading' % kind]

    @classmethod
    def delete_all(cls, kind):
        if settings['%s/deleting' % kind]:
            logger.info('Already loading %s' % kind)
            return
        try:
            settings['%s/deleting' % kind] = True
            cls.elastic_client.delete_by_query(index = kind, body = {
                "query": {
                    "match_all": {}
                }
            })
            item_handlers[kind].delete_all()
            cls.clear(kind)
        except Exception as e:
            logger.error('Could not stop delete all %s: %s' % (kind, e))
        finally:
            settings['%s/deleting' % kind] = False
            settings['%s/count' % kind] = 0

    @classmethod
    def stop_deleting(cls, kind):
        settings['%s/deleting' % kind] = False

    @classmethod
    def deleting(cls, kind):
        return settings['%s/deleting' % kind]

    @classmethod
    def refresh_status(cls):
        for kind in ITEM_KINDS:
            settings['%s/count'] = cls.get_item_count(kind)

    @classmethod
    def poll(cls):
        cls.refresh_status()

    @classmethod
    def reset(cls):
        for kind in ITEM_KINDS:
            cls.delete_all(kind)

    @classmethod
    def get_status(cls):
        status = {}
        start = time.time()
        for kind in ITEM_KINDS:
            if time.time()-start>0.1: logger.info('%.1fs: getting status for %s' % (time.time() - start, kind))
            status[kind] = {
                'pending': settings['%s/pending' % kind],
                'loading': cls.loading(kind),
                'deleting': cls.deleting(kind),
                'count': settings['%s/count' % kind],
                'history': item_handlers[kind].get_status(),
            }
            start = time.time()
        return status

    @classmethod
    def clear(cls, kind):
        path = os.path.realpath(os.path.join(utils.HOME_DIR, 'items', kind))
        import tempfile
        import threading
        if os.path.exists(path) and path.startswith(utils.ITEMS_DIR):
            tmpdir = tempfile.mkdtemp()
            print('mv to tmpdir: ' + tmpdir)
            shutil.move(path, tmpdir)
            threading.Thread(target=lambda: shutil.rmtree(tmpdir)).start()
        time.sleep(0.5)
        logger.info('Cleared all data for "%s"' % path)

    @classmethod
    def get_all(cls, kind):
        return cls.elastic_client.search(index = kind, body = {
            "query": {
                "match_all": {}
            }
        })


class Data(dict):
    def __init__(self, label, obj=None):
        dict.__init__(self)
        self.kind = '<none>'
        self.color = '#888'
        self.email = ''
        self.persons = []
        self.receiver = ''
        self.uid = label
        self.label = label
        self.body = ''
        self.icon = 'get?path=icons/white_pixel.png'
        self.icon_size = 0
        self.font_size = 0
        self.border = 'none'
        self.zoomed_icon_size = 0
        self.image = ''
        self.words = []
        self.timestamp = 0
        self.related_items = []
        self.duplicate = False

        dict.update(self, vars(self))
        if obj:
            dict.update(self, obj)
            for k,v in obj.items():
                setattr(self, k, v)

    def __hash__(self):
        return hash(self.uid)

    def matches(self, query_words):
        return True

    def is_related_item(self, other):
        return other in self.related_items

    def get_related_items(self):
        return self.related_items

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.uid == other.uid

    def update(self, obj):
        obj['timestamp'] = self.timestamp

    def update_words(self, items):
        pass

    def add_related(self, other):
        self.related_items.append(other)

    def is_duplicate(self, duplicates):
        return False

    def save(self):
        Storage.stats['writes'] += 1
        Storage.add_data(self)


class File(Data):
    def __init__(self, path):
        super(File, self).__init__(path)
        self.kind = 'file'
        self.color = 'blue'
        self.path = path
        filename = os.path.basename(path)
        self.words = stopwords.remove_stopwords(filename.replace('+', ' '))
        self.filename = filename
        self.uid = filename
        self.label = filename.replace('%20', ' ')
        self.timestamp = os.path.getmtime(path)
        extension = os.path.splitext(path)[1][1:].lower()
        self.icon_size = 32
        self.zoomed_icon_size = 128
        icon = FILE_FORMAT_ICONS.get(extension, 'icons/file-icon.png')
        if extension in FILE_FORMAT_IMAGE_EXTENSIONS:
            icon = path
            self.icon_size = 64;
            self.zoomed_icon_size = 256
        self.icon = 'get?path=%s' % icon
        dict.update(self, vars(self))
        self.set_message_id(path)

    def matches(self, query_words):
        for word in query_words:
            if not word in self.filename:
                return False
        return True

    def same_path(self, path):
        logger.debug('Same path?', self.path[:len(utils.FILE_DIR)], path)
        return self.path[:len(utils.FILE_DIR)] == path

    def set_message_id(self, path):
        self.message_id = os.path.basename(os.path.dirname(path))

    def update_words(self, items):
        for item in items:
            if item.kind == 'gmail' and item.message_id == self.message_id:
                self.words = item.words


item_handlers.update({
    kind: import_module('importers.%s' % kind) for kind in ITEM_KINDS
})
Storage.setup()

if __name__ == '__main__':
    if False:
        import cProfile
        cProfile.run('Storage.search("laffra", 10000)', sort="cumulative")

    if False:
        for kind in ['browser','file','gmail','contact']:
            logger.debug('%s: %d' % (kind, Storage.get_item_count(kind)))

    if False:
        for k,v in Storage.search_contact('messaging-digest-noreply@linkedin.com').items():
            if v:
                logger.info('%s=%s' % (k, v))

    if True:
        print(json.dumps(Storage.get_all('browser'), indent=4))
        print(Storage.search('insights'))
