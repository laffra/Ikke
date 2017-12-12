import collections
import logging
import storage
import stopwords

MOST_COMMON_COUNT = 25
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


def get_persons(items, contacts):
    merged_contacts = [
        (add_contact(contact, contacts), item)
        for item in items
        for contact in item.persons
    ]
    return merged_contacts


def add_persons(items, labels, me):
    contacts = {}
    non_contacts = [item for item in items if item.kind != 'contact']
    for person, item in get_persons(items, contacts):
        if person.email == me:
            continue
        labels[person].add(item)
    return non_contacts + list(contacts.values())


def remove_duplicates(count, items, keep_duplicates):
    duplicates = set()
    items = sorted(items, key=lambda item: item.image)
    results = [item for item in items if keep_duplicates or not item.is_duplicate(duplicates)]
    if count > storage.MAX_NUMBER_OF_ITEMS:
        too_much = TooMuch(count - storage.MAX_NUMBER_OF_ITEMS)
        results = results[:storage.MAX_NUMBER_OF_ITEMS]
        results.append(too_much)
    return results


def get_most_common_words(items, query):
    counter = collections.Counter()
    for item in items:
        item.update_words(items)
        counter.update([
            word.lower()
            for word in map(lambda(w): filter(type(w).isalnum, w), item.words)
            if len(word) < 21 and not stopwords.is_stopword(word)
        ])
    most_common = {key for key, count in counter.most_common(MOST_COMMON_COUNT)}
    if ' ' in query:
        pass # most_common.update(stopwords.remove_stopwords(query))
    if query in most_common:
        most_common.remove(query)
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


def get_labels(count, all_items, query='', me='', keep_duplicates=False):
    labels = collections.defaultdict(set)
    items = remove_duplicates(count, add_persons(all_items, labels, me), keep_duplicates)
    default_label = Label(query)
    if ADD_CONTENT_LABELS:
        most_common_words = get_most_common_words(items, query)
        for item in items:
            intersection = set(item.words) & most_common_words
            for key in intersection:
                labels[Label(key)].add(item) # add item to a given label
            if not intersection:
                labels[default_label].add(item) # avoid "orphan" items
        labels = merge_repetitive_labels(labels)
    else:
        contacts = [item for item in all_items if item.kind == 'contact']
        contacts = remove_duplicates(count, contacts, keep_duplicates)
        labels[default_label].update(contacts)
        items.extend(contacts)
    # debug_results(labels, all_items, items)
    return labels, items


def debug_results(labels, all_items, items):
    show_details = False
    level = logging.get_level()
    logging.set_level(logging.DEBUG)
    logging.debug('found %d labels with %d items, for %d total items' % (len(labels), len(items), len(all_items)))
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
    import time
    start = time.time()
    query = 'funda'
    items = storage.Storage.search(query, 5)
    end = time.time()
    logging.debug('search results in %d (%s) items in %d sec.' % (len(items), type(items[0]), end-start))
    labels, all_items = get_labels(len(items), items, query)
    for key, items in labels.items():
        logging.debug('   label %s has %d items' % (repr(key.label), len(items)))
    logging.debug('found %d labels for %d items' % (len(labels), len(all_items)))
    logging.set_level(level)
