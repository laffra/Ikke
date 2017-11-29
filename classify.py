import collections
from importers import contact
import storage
import stopwords

MAX_NUMBER_OF_ITEMS = 150
ITEMS_PER_DOMAIN = 21


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
        self.font_size = 32


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


def remove_duplicates(items, keep_duplicates):
    if len(items) < 100 or keep_duplicates:
        return items
    duplicates = set()
    items = sorted(items, key=lambda item: item.image)
    results = [item for item in items if not item.is_duplicate(duplicates)]
    if len(results) > 500:
        too_much = TooMuch(len(results) - 500)
        results.append(too_much)
    return results


def get_most_common_words(items, query):
    counter = collections.Counter()
    for item in items:
        counter.update([word for word in item.words if len(word) < 21 and not stopwords.is_stopword(word)])
    most_common_count = max(25, min(50, int(len(items) / 3)))
    most_common = {key for key, count in counter.most_common(most_common_count)}
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


def get_labels(all_items, query='', me='', keep_duplicates=False):
    labels = collections.defaultdict(set)
    items = remove_duplicates(add_persons(all_items, labels, me), keep_duplicates)
    most_common_words = get_most_common_words(items, query)
    default_label = Label(query)
    for item in items:
        intersection = set(item.words) & most_common_words
        for key in intersection:
            labels[Label(key)].add(item) # add item to a given label
        if not intersection:
            labels[default_label].add(item) # avoid "orphan" items
    labels = merge_repetitive_labels(labels)
    # debug_results(labels, all_items, items)
    return labels, items


def debug_results(labels, all_items, items):
    show_details = False
    print('found', len(labels), 'labels with', len(items), 'items, for ', len(all_items), 'items.')
    print('Included:')

    def shorten(x):
        if isinstance(x, str): return x.replace('\n', ' ')
        return x

    for item in items:
        print('   ', item.kind, repr(item.label), item.uid)
        if show_details:
            for var in vars(item):
                print('       ', var, ':', shorten(getattr(item, var)))
    for k,v in labels.items():
        print(k.label)
        for item in v:
            print ('   ', item.kind, item.label)
    print('Removed:')
    for item in set(all_items) - set(items):
        print('   ', item.kind, repr(item.label), item.uid)
        if show_details:
            for var in vars(item):
                print('       ', var, ':', shorten(getattr(item, var)))


if __name__ == '__main__':
    import time
    start = time.time()
    query = 'funda'
    items = storage.Storage.search(query)
    end = time.time()
    print('search results in ', len(items), 'items in', end-start, 'sec.')
    labels, all_items = get_labels(items, query)
    for key, items in labels.items():
        print('label ', repr(key.label), 'has', len(items), 'items')
    print('found', len(labels), 'labels for', len(all_items), 'items')
