import datetime
from threading import TIMEOUT_MAX
import elasticsearch
from importlib import import_module
import json
import logging
import os
import pubsub
from settings import settings
import shutil
import stat
import utils
import time
from collections import defaultdict

ITEM_KINDS = [ 'contact', 'gmail', 'hangouts', 'calendar', 'git', 'browser', 'file' ]
SEARCH_KINDS = [ 'contact', 'gmail', 'hangouts', 'calendar', 'git', 'browser' ]
INDEX = "insights"
MAX_NUMBER_OF_ITEMS = 1000

logger = logging.getLogger(__name__)

item_handlers = { }



class Storage:
    stats = defaultdict(int)
    elastic_client = elasticsearch.Elasticsearch([{'host': 'localhost', 'port': '9200'}])
    elastic_logger = logging.getLogger('elasticsearch')
    elastic_logger.setLevel(logging.WARNING)

    @classmethod
    def get_data(cls, index, id):
        try:
            return cls.elastic_client.get(index=index, id=id)
        except:
            return None

    @classmethod
    def add_data(cls, data):
        if not data['timestamp']:
            logging.error("Cannot save data without a timestamp %s" % json.dumps(data))
            return
        cls.elastic_client.index(index=data["kind"], id=data["uid"], body=data, request_timeout=30)

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
    def search(cls, query, days=0):
        pubsub.notify("search", query, days)
        # type: (str,int) -> list
        assert isinstance(query, str)
        assert isinstance(days, int), 'unexpected type %s: %s' % (type(days), days)
        cls.stats = defaultdict(int)
        search_start = time.time()
        since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).timestamp()
        hits = cls.search_indexes(query, since)
        items = list(filter(None, [cls.resolve(hit) for hit in hits if cls.relevant(hit)]))
        cls.truncate_words(items, 5)
        items = cls.remove_negatives(query, items)
        items = items + cls.get_related_items(items)
        items = cls.remove_negatives(query, items)
        duration = time.time() - search_start
        logger.info("Found %d items for '%s' since %d days in %.2fms" % (len(items), query, days, duration))
        cls.record_search_stats(query, duration, len(items))
        return items

    @classmethod
    def truncate_words(cls, items, max_count):
        for item in items:
            item.words = item.words[:max_count]


    @classmethod
    def get_related_items(cls, items):
        return [
            related_item
            for item in items
            for related_item in item.get_related_items()
            if related_item 
        ]

    @classmethod
    def remove_negatives(cls, query, items):
        negatives = [word[1:] for word in query.split() if word.startswith("-")]
        return [item for item in items if not cls.match_negative(negatives, item)]

    @classmethod
    def search_indexes(cls, query, since):
        hits = cls.elastic_client.search(
            size=MAX_NUMBER_OF_ITEMS,
            body={
                "query": {
                    "bool": {
                        "must": {
                            "query_string": {
                                "query": cls.wildcard(query),
                                "fuzziness": "AUTO",
                                "default_operator": "OR" if " OR " in query else "AND",
                                "default_field": "*"
                            }
                        },
                        "filter": {
                            "range": {
                                "timestamp": {
                                    "gte": since
                                } 
                            }
                        }
                    }
                }
            }
        )["hits"]["hits"]
        return list(filter(None, [hit["_source"] for hit in hits]))

    @classmethod
    def load_stats(cls):
        result = cls.elastic_client.search(
            size=1,
            body={
                "size": 20,
                "aggregations": {
                    "byindex": {
                        "terms": {
                            "field": "_index",
                            "size": 20
                        },
                        "aggregations": {
                            "min": {
                                "min": {
                                    "field": "timestamp"
                                }
                            },
                            "max": {
                                "max": {
                                    "field": "timestamp"
                                }
                            }
                        }
                    }
                }
            }
        )
        if "aggregations" in result:
            for bucket in result["aggregations"]["byindex"]["buckets"]:
                kind = bucket["key"]
                settings["%s/youngest" % kind] = bucket["max"]["value"]
                settings["%s/oldest" % kind] = bucket["min"]["value"]
                settings["%s/count" % kind] = bucket["doc_count"]
        logger.debug("STATS: %s" % json.dumps(settings, indent=4))

    @classmethod
    def relevant(cls, obj):
        if obj["kind"] == "browser" and obj["url"].startswith("file:"):
            return False
        return True
    
    @classmethod
    def wildcard(cls, query):
        return " ".join(
            "*%s*^5" % word if not word.startswith('"') else word[1:-1]
            for word in query.split()
            if not word in ["AND, ""OR"] and not word.startswith("-")) 

    @classmethod
    def match_negative(cls, negatives, item):
        words = item.get("words", [])
        if not words:
            return False
        for negative in negatives:
            if negative in words:
                return True
        return False

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
        if not "kind" in obj or obj["kind"] == "file":
            return None
        handler = item_handlers[obj['kind']]
        return handler.deserialize(obj)

    @classmethod
    def get_day_month_year(cls, days):
        # type: (int) -> str
        dt = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        return '%s/%s/%s' % (dt.day, dt.month, dt.year)

    @classmethod
    def get_year_month_day(cls, days):
        # type: (int) -> str
        dt = datetime.datetime.utcnow() - datetime.timedelta(days=days)
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
            for key in [key for key in settings.keys() if key.startswith('%s/' % kind)]:
                del settings[key]
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
        cls.load_stats()
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
        self.duplicate_count = 0
        self.image = ''
        self.words = []
        self.timestamp = 0
        self.edges = 0
        self.timenode = None

        dict.update(self, vars(self))
        if obj:
            dict.update(self, obj)
            for k,v in obj.items():
                setattr(self, k, v)

    def __hash__(self):
        return hash(self.uid)

    def is_related_item(self, other):
        return other is self.timenode

    def get_related_items(self):
        self.timenode = TimeNode.get_timenode(self.timestamp)
        return list(filter(None, [ self.timenode ]))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.uid == other.uid

    def update(self, obj):
        obj['timestamp'] = self.timestamp

    def update_words(self, items):
        pass

    def is_duplicate(self, duplicates):
        return False

    def mark_duplicate(self):
        self.duplicate_count += 1

    def save(self):
        Storage.stats['writes'] += 1
        Storage.add_data(self)

    def __repr__(self):
        return "<%s %s %s>" % (self.__class__.__name__.replace("Node", ""), repr(self.uid), repr(self.label))


class TimeNode(Data):
    TIME_COUNT = 7
    min_timestamp = 0
    max_timestamp = 0
    timenodes = [None] * TIME_COUNT

    def __init__(self, index, timestamp):
        super(TimeNode, self).__init__("")
        self.uid = "time-%d" % index
        self.kind = 'time'
        self.color = 'darkgreen'
        self.icon_size = 27
        self.zoomed_icon_size = 42
        self.font_size = 10
        self.index = index
        self.timestamp = timestamp
        self.label = self.get_label(timestamp)
        self.icon = 'get?path=icons/rainbow-circle.png'
        dict.update(self, vars(self))
    
    def __hash__(self):
        return self.label.__hash__()

    def __eq__(self, other):
        return isinstance(other, TimeNode) and other.index == self.index

    def get_related_items(self):
        return []

    def get_label(self, timestamp):
        last = datetime.datetime.fromtimestamp(self.max_timestamp)
        then = datetime.datetime.fromtimestamp(timestamp)
        diff = last - then
        if diff.days:
            return "%s day%s ago" % (diff.days, "s" if diff.days > 1 else "")
        hours = int(diff.seconds / 3600)
        return "%s hour%s ago" % (hours, "s" if hours > 1 else "")
    
    @classmethod
    def set_timerange(cls, min_timestamp, max_timestamp):
        cls.min_timestamp = min_timestamp
        cls.max_timestamp = max_timestamp

    @classmethod
    def get_timenode(cls, timestamp):
        range = cls.max_timestamp - cls.min_timestamp
        increment = range / cls.TIME_COUNT
        if not timestamp or not increment:
            return None
        diff = timestamp - cls.min_timestamp
        index = max(0, min(int(diff / increment), cls.TIME_COUNT - 1))
        if not cls.timenodes[index]:
            timestamp = int(cls.min_timestamp + index * increment)
            cls.timenodes[index] = TimeNode(index, timestamp)
        return cls.timenodes[index]


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
