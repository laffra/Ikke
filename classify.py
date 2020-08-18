import collections
import itertools
import logging
import storage

MOST_COMMON_COUNT = 41
ADD_CONTENT_LABELS = False

logger = logging.getLogger(__name__)


def shorten(label):
    if len(label) > 31:
        label = label[:13] + ' ... ' + label[-13:]
    return label


class Label(storage.Data):
    def __init__(self, name):
        super(Label, self).__init__(name)
        self.kind = 'label'
        self.color = '#888'
        self.font_size = 12

    def is_related_item(self, other):
        return self.label in other.words


class TooMuch(storage.Data):
    def __init__(self, count):
        super(TooMuch, self).__init__('Search is too broad: %d results not shown.' % count)
        self.kind = 'label'
        self.color = 'red'
        self.font_size = 48


def add_contact(contact, contacts):
    if contact.label in contacts:
        contact = contacts[contact.label]
    else:
        contacts[contact.label] = contact
    return contact


def get_persons(items):
    return [(contact, item) for item in items for contact in item.persons]


def adjacent(items):
    for index in range(len(items) - 2):
        yield (items[index], items[index + 1])


def add_related_items(items, me):
    # type(list, str) -> list
    related_items = [
        related_item
        for item in items
        for related_item in item.get_related_items()
        if related_item and not related_item.email == me
    ]
    edges = {
        (item1, item2)
        for item in items
        for item1, item2 in itertools.combinations([item] + item.get_related_items(), 2)
    }
    return edges, list(items) + related_items


def remove_duplicates(items, keep_duplicates):
    # type(list, bool) -> list
    duplicates = set()
    items = sorted(items, key=lambda item: not hasattr(item, 'keep'))
    results = [item for item in items if keep_duplicates or hasattr(item, 'keep') or not item.is_duplicate(duplicates)]
    logger.debug('Found %d duplicates, duplicates=%s', len(items) - len(results), duplicates)
    if len(results) > storage.MAX_NUMBER_OF_ITEMS:
        too_much = TooMuch(len(results) - storage.MAX_NUMBER_OF_ITEMS)
        results = results[:storage.MAX_NUMBER_OF_ITEMS]
        results.append(too_much)
    return results


def get_most_common_words(query, items):
    counter = collections.Counter()
    for item in items:
        item.update_words(items)
        counter.update([
            word
            for word in item.words
            if word and word != query
        ])
    for word in query.lower().split(' '):
        if word in counter:
            del counter[word]
    most_common = {key for key, count in counter.most_common(MOST_COMMON_COUNT)}
    return most_common


def get_edges(query, items, me='', add_words=False, keep_duplicates=False):
    # type(str, list, str, bool) -> (list, list)
    edges, items = add_related_items(items, me)
    logging.info("Create graph for %d edges and %d items" % (len(edges), len(items)))
    for n,item in enumerate(items, 1):
        logger.debug(" %d:  %s" % (n, item.label))
    if add_words:
        before = len(items)
        items.extend(Label(word) for word in get_most_common_words(query, items))
        logging.info("Added %d labels" % (len(items) - before))
    items = remove_duplicates(items, keep_duplicates)
    for item1, item2 in itertools.combinations(items, 2):
        if item1.is_related_item(item2) or item2.is_related_item(item1):
            if not item2.duplicate:
                edges.add((item1, item2))
    return list(edges), items


def debug_results(labels, items):
    show_details = False
    level = logging.get_level()
    logging.set_level(logging.DEBUG)
    logging.debug('found %d labels with %d items' % (len(labels), len(items)))
    logging.debug('Included:')

    def shorten(x):
        if isinstance(x, str): return x.replace('\n', ' ')
        return x

    for item in items:
        logging.debug('   %s %s %s' % (item.kind, repr(item.label), item.uid))
        if show_details:
            for var in vars(item):
                logging.debug('       %s: %s' % (var, shorten(getattr(item, var))))
    for k,v in labels.items():
        logging.debug(k.label)
        for item in v:
            logging.debug ('   %s %s' % (item.kind, item.label))
    logging.debug('Removed:')
    for item in set(all_items) - set(items):
        logging.debug('   %s %s %s' % (item.kind, repr(item.label), item.uid))
        if show_details:
            for var in vars(item):
                logging.debug('       %s: %s' % (var, shorten(getattr(item, var))))
    logging.set_level(level)


if __name__ == '__main__':
    level = logging.get_level()
    logging.set_level(logging.DEBUG)
    query = 'blockchain'
    items = storage.Storage.search(query, 3)
    logging.debug('Found %d items.' % len(items))
    edges, all_items = get_edges(items, 'laffra@gmail.com')
    logging.debug('Edges:')
    for item1, item2 in edges:
        logging.debug('   %s - %s' % (repr(item1.label), repr(item2.label)))
    logging.debug('Items:')
    for item in items:
        logging.debug('   %s' % repr(item.label))
