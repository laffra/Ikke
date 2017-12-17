import collections
import itertools
import logging
import storage
import stopwords

MOST_COMMON_COUNT = 2
ITEMS_PER_DOMAIN = 21
ADD_CONTENT_LABELS = False


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


def add_related_items(items, me):
    # type(list, str) -> list
    related_items = [
        related_item
        for item in items
        for related_item in item.get_related_items()
        if not related_item.email == me
    ]
    return list(set(list(items) + related_items))


def remove_duplicates(items, keep_duplicates):
    # type(list, bool) -> list
    duplicates = set()
    items = sorted(items, key=lambda item: item.image)
    results = [item for item in items if keep_duplicates or not item.is_duplicate(duplicates)]
    if len(results) > storage.MAX_NUMBER_OF_ITEMS:
        too_much = TooMuch(len(results) - storage.MAX_NUMBER_OF_ITEMS)
        results = results[:storage.MAX_NUMBER_OF_ITEMS]
        results.append(too_much)
    return results


def get_most_common_words(items):
    counter = collections.Counter()
    for item in items:
        item.update_words(items)
        counter.update([
            word.lower()
            for word in map(lambda w: filter(type(w).isalnum, w), item.words)
            if len(word) < 21 and not stopwords.is_stopword(word)
        ])
    most_common = {key for key, count in counter.most_common(MOST_COMMON_COUNT)}
    return most_common


def merge_repetitive_labels(labels):
    new_names = {}
    # find labels that have similar items and merge them
    for label1,items1 in labels.items():
        for label2,items2 in labels.items():
            if label1.kind == 'label' and label1 != label2:
                intersection = items1 & items2
                if len(items2) > 5 and intersection and len(intersection) / len(items1) > 0.8:
                    new_names[label1] = label1.label + ' ' + label2.label
                    for item in items1:
                        if item in items2:
                            items2.remove(item)
    for label, new_name in new_names.items():
        label.label = new_name
    return {label: items for label, items in labels.items() if items}


def get_edges(items, me='', keep_duplicates=False):
    # type(list, str, bool) -> (list, list)
    items = add_related_items(items, me)
    items = remove_duplicates(items, keep_duplicates)
    edges = set()
    def add_related_edge(item1, item2):
        if item1.is_related_item(item2):
            edges.add((item1, item2))
    for item1, item2 in itertools.combinations(items, 2):
        add_related_edge(item1, item2)
        add_related_edge(item2, item1)
    # debug_results(labels, items)
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
