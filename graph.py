import datetime
from collections import defaultdict
import logging
from re import I
from urllib.parse import unquote
import json
import time
from importers import browser
from importers import contact
from importers import gmail
import classify
from preferences import ChromePreferences
import os
import utils
from threadpool import ThreadPool
from storage import Data, Storage

days = {
    'day': 1,
    'week': 7,
    'month': 31,
    'month3': 92,
    'month6': 182,
    'year': 365,
    'forever': 3650,
}
MY_EMAIL_ADDRESS = ChromePreferences().get_email()
LINE_COLORS = [ '#f4c950', '#ee4e5a', '#489ac9', '#41ba7d', '#fb7c54',] * 2

ALL_ITEM_KINDS = [ 'all', 'contact', 'gmail', 'calendar', 'git', 'hangouts', 'browser', 'file', ]
MY_ITEM_KINDS = [ 'contact', 'gmail', 'calendar', 'git', 'hangouts', 'browser', 'file' ]

MAX_LABEL_LENGTH = 42
ADD_WORDS_MINIMUM_COUNT = 100
REDUCE_GRAPH_SIZE = False

IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'tiff', 'png', 'raw']

TIME_COUNT = 7

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Graph:
    def __init__(self, email, query, duration_string):
        logger.info('GRAPH: init %s %s' % (repr(query), duration_string))
        self.email = email
        self.query = query
        self.duration_string = duration_string
        self.search_count = {}
        self.search_results = defaultdict(list)
        self.search_duration = defaultdict(list)
        self.my_pool = ThreadPool(1, [
            (self.search, days[duration_string])
        ])

    def add_result(self, kind, count, items, duration):
        self.search_results[kind] = set(filter(None, self.search_results[kind] + list(items)))
        self.search_count[kind] = count
        self.search_duration[kind].append(duration)
        logger.debug('found %d of %s items' % (len(items), kind))

    def search(self, days):
        start_time = time.time()
        all_items = list(filter(None, Storage.search(unquote(self.query), days)))
        duration = time.time() - start_time

        self.add_result('all', len(all_items), all_items, duration)
        for kind in MY_ITEM_KINDS:
            items = [item for item in all_items if item.kind in ('label', kind)]
            self.add_result(kind, len(items), items, duration)

    def get_graph(self, kind, keep_duplicates):
        self.my_pool.wait_completion()
        all_found_items = self.search_results['all' if kind in ['contact', 'file'] else kind]
        found_items = [item for item in all_found_items if item.kind != 'contact' or item.label != self.email]
        add_words = True
        edges, items = classify.get_edges(self.query, found_items, add_words, keep_duplicates)
        removed_item_count = 0
        for item in found_items:
            if not item in items:
                removed_item_count += 1
        if kind in ['contact', 'file']:
            items = [item for item in items if item.kind == kind]
        if REDUCE_GRAPH_SIZE:
            items = self.remove_lonely_images(items)
            items = self.remove_lonely_labels(items)
            # items = self.remove_labels(items)

        for item in items:
            if len(item.label) > MAX_LABEL_LENGTH:
                cutoff = round(MAX_LABEL_LENGTH / 2)
                head = item.label[:cutoff]
                tail = item.label[-cutoff:] 
                item.label = "%s...%s" % (head, tail)
            item.date = str(datetime.datetime.fromtimestamp(float(item.timestamp))) if item.timestamp else ""

        nodes_index = dict((item.uid, n) for n, item in enumerate(items))
        label_index = dict((item.label, n) for n, item in enumerate(items))
        nodes = [vars(item) for item in items]
        def get_color(item):
            return LINE_COLORS[label_index.get(item.label, 0) % len(LINE_COLORS)]
        links = [
            {
                'source': nodes_index[item1.uid],
                'target': nodes_index[item2.uid],
                'color': get_color(item2),
                'stroke': 1,
            }
            for item1, item2 in edges
            if item1 and item1.uid in nodes_index and item2 and item2.uid in nodes_index
        ]

        timestamps = [item["timestamp"] for item in items if item["timestamp"]]
        if timestamps:
            min_timestamp = min(timestamps)
            max_timestamp = max(timestamps)
            time_increment = (max_timestamp - min_timestamp) / TIME_COUNT 
            most_recent = datetime.datetime.fromtimestamp(max_timestamp)

            print("### min:", datetime.datetime.fromtimestamp(min_timestamp))
            print("### max:", datetime.datetime.fromtimestamp(max_timestamp))

            def time_label(time_ms):
                timestamp = min_timestamp + time_ms
                then = datetime.datetime.fromtimestamp(timestamp)
                diff = most_recent - then
                if self.duration_string == "day":
                    hours = int(diff.seconds / 3600)
                    if hours:
                        return "%d hour%s ago" % (hours, "s" if hours > 1 else "")
                else:
                    if diff.days:
                        return "%d day%s ago" % (diff.days, "s" if diff.days > 1 else "")
                if diff.seconds:
                    return "recently"
                return "now"

            times = [
                TimeNode(n, time_label(n * time_increment))
                for n in range(TIME_COUNT)
            ]

            def time_index(item):
                if time_increment:
                    index = int((item["timestamp"] - min_timestamp) / time_increment)
                    return min(TIME_COUNT -1, max(0, index))
                return 0

            for n in range(3):
                links += [
                    {
                        'source': nodes_index[item.uid],
                        'target': len(nodes_index) + time_index(item),
                        'color': "#EEE",
                        'stroke': 1,
                    }
                    for item in items
                    if item["timestamp"] and item['kind'] != 'contact'
                ]
            nodes += times
                        
        logger.info("Found %d nodes" % len(nodes))
        logger.info("Found %d links" % len(links))

        stats = {
            'found': len(found_items),
            'removed': removed_item_count,
            'memory': utils.get_memory()
        }
        stats.update(Storage.stats)
        logger.info("Graph stats: %s" % json.dumps(stats))
        if kind == 'all':
            browser.cleanup()
            gmail.cleanup()
            contact.cleanup()
            Storage.stats.clear()

        return {
            'graph': [],
            'links': links,
            'nodes': nodes,
            'directed': False,
            'stats': stats
        }

    def remove_labels(self, items):
        return [item for item in items if item.kind != 'label']


    def remove_lonely_images(self, items):
        return [item for item in items if not self.is_lonely_image(item)]


    def remove_lonely_labels(self, items):
        return [item for item in items if not self.is_lonely_label(item)]


    def is_lonely_image(self, item):
        if item.kind != "file":
            return False
        _, extension = os.path.splitext(item.path)
        return extension[1:].lower() in IMAGE_EXTENSIONS


    def is_lonely_label(self, item):
        return item.kind == "label" and item.edges == 0


class TimeNode(Data):
    def __init__(self, index, label):
        super(TimeNode, self).__init__(label)
        self.uid = "time-%d" % index
        self.index = index
        self.kind = 'time'
        self.color = 'purple'
        self.icon_size = 12
        self.zoomed_icon_size = 24
        self.font_size = 10
        self.icon = 'get?path=icons/time-icon.png'
        dict.update(self, vars(self))