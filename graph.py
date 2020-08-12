from collections import defaultdict
from importers import facebook
import logging
from urllib.parse import unquote
import time
from importers import browser
from importers import contact
from importers import gmail
import classify
from preferences import ChromePreferences
import utils
from threadpool import ThreadPool
from storage import Storage

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

ALL_ITEM_KINDS = [ 'all', 'contact', 'gmail', 'hangouts', 'browser', 'file', 'facebook', ]
MY_ITEM_KINDS = [ 'contact', 'gmail', 'browser', 'file', 'facebook' ]

ADD_WORDS_MINIMUM_COUNT = 50

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Graph:
    def __init__(self, query, duration_string):
        logger.info('GRAPH: init %s %s' % (repr(query), duration_string))
        self.query = query
        self.search_count = {}
        self.search_results = defaultdict(list)
        self.search_duration = defaultdict(list)
        self.my_pool = ThreadPool(1, [
            (self.search, days[duration_string])
        ])

    def add_result(self, kind, count, items, duration):
        self.search_results[kind] = set(self.search_results[kind] + list(items))
        self.search_count[kind] = count
        self.search_duration[kind].append(duration)
        logger.debug('found %d of %s items' % (len(items), kind))
        for n,item in enumerate(items):
            logger.debug('  %d: %s %s uid=%s', n, item.kind, repr(item.label), repr(item.uid))

    def search(self, timestamp):
        start_time = time.time()
        all_items = Storage.search(unquote(self.query), timestamp)

        duration = time.time() - start_time
        self.add_result('all', len(all_items), all_items, duration)
        for kind in MY_ITEM_KINDS:
            items = [item for item in all_items if item.kind in ('label', kind)]
            if kind == 'facebook':
                items.extend([
                    item
                    for item in all_items
                    if item.get('domain','') in facebook.DOMAINS
                ])
            self.add_result(kind, len(items), items, duration)

    def get_graph(self, kind, keep_duplicates):
        self.my_pool.wait_completion()
        found_items = self.search_results['all' if kind in ['contact', 'file'] else kind]
        add_words = len(found_items) < ADD_WORDS_MINIMUM_COUNT or kind in ['browser', 'facebook']
        edges, items = classify.get_edges(self.query, found_items, MY_EMAIL_ADDRESS, add_words, keep_duplicates)
        if kind in ['contact', 'file']:
            items = [item for item in items if item.kind == kind]
        removed_item_count = max(0, len(found_items) - len(items))

        if Storage.stats['search_time'] > 10:
            msg = 'Searching took %.1fs. Reboot may make it faster.' % Storage.stats['search_time']
            label = classify.Label(msg)
            label.font_size = 24
            label.color = 'red'
            items.append(label)

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
            if item1.uid in nodes_index and item2.uid in nodes_index
        ]

        stats = {
            'found': len(found_items),
            'removed': removed_item_count,
            'memory': utils.get_memory()
        }
        stats.update(Storage.stats)
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
