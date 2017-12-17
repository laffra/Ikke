from collections import defaultdict
import logging
import json
from urllib.parse import unquote
import time
from importers import browser
from importers import contact
from importers import gmail
import classify
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
MY_EMAIL_ADDRESS = 'laffra@gmail.com'
LINE_COLORS = [ '#f4c950', '#ee4e5a', '#489ac9', '#41ba7d', '#fb7c54',] * 2

ALL_ITEM_KINDS = [ 'all', 'contact', 'gmail', 'browser', 'file', 'facebook', 'twitter', 'linkedin' ]
MY_ITEM_KINDS = [ 'contact', 'gmail', 'browser', 'file' ]
PREMIUM_ITEM_KINDS = { 'facebook', 'twitter', 'linkedin' }


class Graph:
    def __init__(self, query, duration_string):
        logging.info('GRAPH: init %s %s' % (repr(query), duration_string))
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
        logging.debug('found %d %s items' % (len(items), kind))

    def search(self, timestamp):
        start_time = time.time()
        all_items = Storage.search(unquote(self.query), timestamp)
        duration = time.time() - start_time
        self.add_result('all', len(all_items), all_items, duration)
        for kind in MY_ITEM_KINDS:
            items = [item for item in all_items if item.kind in ('label', kind)]
            self.add_result(kind, len(items), items, duration)

    def get_graph(self, kind, keep_duplicates):
        self.my_pool.wait_completion()
        found_items = self.search_results[kind]
        edges, items = classify.get_edges(found_items, MY_EMAIL_ADDRESS, keep_duplicates)
        removed_item_count = max(0, len(found_items) - len(items))

        nodes_index = dict((item.uid, n) for n, item in enumerate(items))
        nodes = [vars(item) for item in items]
        def get_color(contact):
            return LINE_COLORS[nodes_index[contact.uid] % len(LINE_COLORS)]
        links = [
            {
                'source': nodes_index[item1.uid],
                'target': nodes_index[item2.uid],
                'color': get_color(item1),
                'stroke': 1,
            }
            for item1, item2 in edges
            if item1.uid in nodes_index and item2.uid in nodes_index
        ]

        stats = {
            'found': len(found_items),
            'removed': removed_item_count,
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
            'stats': json.dumps(stats)
        }
