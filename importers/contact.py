import base64
import logging
import quopri
import re
import storage
import time


NAME_CLEANUP_RE = re.compile('\'')

contacts_cache = {}
save_queue = set()


def decode(encoded_string):
    encoded_word_regex = r'=\?{1}(.+)\?{1}([B|Q])\?{1}(.+)\?{1}='
    match = re.match(encoded_word_regex, encoded_string)
    if match:
        charset, encoding, encoded_text = match.groups()
        byte_string = base64.b64decode(encoded_text) if encoding is 'B' else quopri.decodestring(encoded_text)
        return byte_string.decode(charset)
    return encoded_string


def remove_quotes(name):
    return ' '.join(re.sub(NAME_CLEANUP_RE, '', decode(name)).split(', '))

PATH_ATTRIBUTES = {
    'uid',
    'email',
    'label',
    'names',
    'phones',
    'timestamp',
}

def find_contact(email, name='', phones=None, timestamp=None):
    assert email, 'Email missing'
    name = remove_quotes(name)
    email = remove_quotes(email)
    contact = contacts_cache.get(email)
    if not contact:
        contact = Contact({
            'kind': 'contact',
            'uid': email,
            'email': email,
            'label': name,
            'names': [name] if name else [],
            'phones': phones or [],
        })
        logging.debug('CONTACT: new contact ==> %s %s' % (email, contact.names))
        save_queue.add(contact)
    contacts_cache[email] = contact
    contact.timestamp = timestamp
    return contact


class Contact(storage.Data):
    def __init__(self, obj):
        super(Contact, self).__init__(obj['email'], obj)
        self.uid = obj['uid'] or obj['email']
        self.email = obj['email']
        self.names = obj.get('names', [])
        self.phones = obj.get('phones',[])
        self.label = self.names[0] if self.names else self.email
        self.color = 'purple'
        self.font_size = 14
        self.name = self.label
        self.timestamp = time.time()
        assert self.email, 'Email missing for %s\nin %s' % (self, obj)
        assert self.label, 'Label missing for %s\nin %s' % (self, obj)
        assert self.uid, 'UID missing for %s in\n%s' % (self, obj)
        dict.update(self, vars(self))

    @classmethod
    def deserialize(cls, obj):
        # type (dict) -> dict
        return Contact(obj)

    def update(self, obj):
        super(Contact, self).update(obj)
        obj['email'] = obj['email'] or self.email
        obj['names'] = list(set(obj['names'] + self.names))
        obj['phones'] = list(set(obj['phones'] + self.phones))

    def is_duplicate(self, duplicates):
        if self.email in duplicates:
            return True
        duplicates.add(self.email)
        logging.info('Unique contact: %s - %s' % (self.name, self.email))
        return False

    def __hash__(self):
        return hash(self.uid)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.uid == other.uid


deserialize = Contact.deserialize


def delete_all():
    return storage.Storage.clear('contact')


def can_load_more():
    return False


def poll():
    pass


def history():
    msg = 'Nothing loaded yet.'
    count = storage.Storage.get_item_count('contact')
    if count > 0:
        msg = '%d contacts were loaded as senders/receivers for gmail messages' % count
    return msg


def cleanup():
    if save_queue:
        logging.debug('CONTACT: cleanup, save %d contacts' % len(save_queue))
    for n, contact in enumerate(save_queue.copy()):
        contact.save()
    save_queue.clear()


def test():
    logging.set_level(logging.DEBUG)
    def test(n, name, email, expected_name, check_name):
        logging.debug('Test', n, repr(name), email, repr(expected_name))
        for k,v in contacts_cache.items():
            logging.debug('   cached:', k, v.names)
        contact = find_contact(email, name)
        logging.debug('   Contact names are %s %s' % (contact.name, contact.names))
        if check_name:
            assert expected_name in contact.names, 'Name %s not in %s' % (expected_name, contact.names)
            logging.debug('   Found the right name')
        import json
        json.dumps(contact)
        logging.debug()
        return contact

    email = 'laffra@gmail.com'

    c1 = test(1, '', email, 'Chris Laffra', False)
    c2 = test(2, 'Johannes Laffra', email, 'Johannes Laffra', True)
    c3 = test(3, 'Chris Laffra', email, 'Chris Laffra', True)
    c4 = test(4, '', email, 'Chris Laffra', True)

    assert hash(c1) == hash(c2), 'c1 and c2 are not equal'
    assert c1 == c2, 'c1 and c2 are not equal'

    logging.debug('cache:', len(contacts_cache))
    logging.debug('save queue:', len(save_queue))
    logging.debug(storage.Storage.stats.items())

    cleanup()

    logging.debug('cache:', len(contacts_cache))
    logging.debug('save queue:', len(save_queue))
    logging.debug(storage.Storage.stats.items())


if __name__ == '__main__':
    test()
