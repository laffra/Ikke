from collections import defaultdict
import json

import sys
if sys.version_info >= (3,):
    from urllib.parse import unquote
else:
    from urllib import url2pathname as unquote


import time

from importers import browser
from importers import contact
from importers import gmail
import google
import classify
from threadpool import ThreadPool
from storage import Storage

timestamps = {
    'day': 86400,
    'week': 604800,
    'month': 2678400,
    'month3': 3 * 2678400,
    'month6': 6 * 2678400,
    'year': 31536000,
    'forever': 3153600000,
}
MY_EMAIL_ADDRESS = 'laffra@gmail.com'
LINE_COLORS = [ '#f4c950', '#ee4e5a', '#489ac9', '#41ba7d', '#fb7c54',] * 2

ALL_ITEM_KINDS = [ 'all', 'contact', 'gmail', 'browser', 'file', 'facebook', 'twitter', 'linkedin' ]
MY_ITEM_KINDS = [ 'contact', 'gmail', 'browser', 'file' ]
PREMIUM_ITEM_KINDS = { 'facebook', 'twitter', 'linkedin' }


class Graph:
    def __init__(self, query, duration_string):
        print('GRAPH: init %s %s' % (repr(query), duration_string))
        self.query = query
        self.search_results = defaultdict(list)
        self.search_duration = defaultdict(list)
        after_timestamp = time.time() - timestamps[duration_string]
        #self.google_pool = ThreadPool([
            # (self.search_google, (1,)),
            # (self.search_google, (11,)),
        #])
        self.my_pool = ThreadPool(1, [
            (self.search_me, after_timestamp),
        ])

    def add_result(self, kind, items, duration):
        self.search_results[kind] = set(self.search_results[kind] + list(items))
        self.search_duration[kind].append(duration)

    def search_all(self):
        start_time = time.time()
        self.my_pool.wait_completion()
        items = self.search_results['me']
        self.add_result('all', items, time.time() - start_time)

    def search_google(self, start_position):
        google.search(self.query, start_position)

    def search_me(self, timestamp):
        start_time = time.time()
        all_items = Storage.search(unquote(self.query), timestamp)
        duration = time.time() - start_time
        self.add_result('all', all_items, duration)
        for kind in MY_ITEM_KINDS:
            items = [item for item in all_items if item.kind in ('label', kind)]
            self.add_result(kind, items, duration)

    def get_graph(self, kind, keep_duplicates):
        self.my_pool.wait_completion()
        found_items = self.search_results['gmail' if kind == 'contact' else kind]
        labels, items = classify.get_labels(found_items, self.query, MY_EMAIL_ADDRESS, keep_duplicates)
        if kind == 'contact':
            labels = {}
            items = [item for item in items if item.kind == 'contact']
        print('GRAPH: found %d items for %s' % (len(items), kind))
        removed_item_count = max(0, len(found_items) - len(items))
        items = list(set(items + list(labels.keys())))

        label_counts = ((label.label, len(items)) for label, items in labels.items())
        most_common_labels = sorted(label_counts, key=lambda pair: -pair[1])
        for n in range(len(most_common_labels)):
            label, count = most_common_labels[n]
            most_common_labels[n] = (label, LINE_COLORS[n] if n < len(LINE_COLORS) else '#DDD')
        link_colors = dict(most_common_labels)
        link_strokes = dict((label, 2 if color == '#DDD' else 2) for label, color in most_common_labels)

        nodes_index = dict((item, n) for n, item in enumerate(items))
        nodes = [vars(item) for item in items]
        links = [
            {
                'source': nodes_index[label],
                'target': nodes_index[item],
                'color': link_colors[label.label],
                'stroke': link_strokes[label.label],
            }
            for label, sub_items in labels.items() if label in nodes_index
            for item in sub_items if item in nodes_index
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
