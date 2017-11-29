import base64
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
    print('find_contact', email)
    if not contact:
        contact = Contact({
            'kind': 'contact',
            'uid': email,
            'email': email,
            'label': name,
            'names': [name] if name else [],
            'phones': phones or [],
        })
        print('   new contact ==> %s %s' % (email, contact.names))
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
        return Contact(obj)

    def update(self, obj):
        super(Contact, self).update(obj)
        obj['email'] = obj['email'] or self.email
        obj['names'] = list(set(obj['names'] + self.names))
        obj['phones'] = list(set(obj['phones'] + self.phones))

    def __hash__(self):
        return hash(self.uid)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.uid == other.uid


deserialize = Contact.deserialize

def poll():
    pass



def cleanup():
    if save_queue:
        print('CONTACT: cleanup, save ', len(save_queue), 'contacts.')
    for n, contact in enumerate(save_queue.copy()):
        contact.save()
    save_queue.clear()


def test():
    def test(n, name, email, expected_name, check_name):
        print('Test', n, repr(name), email, repr(expected_name))
        for k,v in contacts_cache.items():
            print('   cached:', k, v.names)
        contact = find_contact(email, name)
        print('   Contact names are', contact.name, contact.names)
        if check_name:
            assert expected_name in contact.names, 'Name %s not in %s' % (expected_name, contact.names)
            print('   Found the right name')
        import json
        json.dumps(contact)
        print()
        return contact

    email = 'laffra@gmail.com'

    c1 = test(1, '', email, 'Chris Laffra', False)
    c2 = test(2, 'Johannes Laffra', email, 'Johannes Laffra', True)
    c3 = test(3, 'Chris Laffra', email, 'Chris Laffra', True)
    c4 = test(4, '', email, 'Chris Laffra', True)

    assert hash(c1) == hash(c2), 'c1 and c2 are not equal'
    assert c1 == c2, 'c1 and c2 are not equal'

    print('cache:', len(contacts_cache))
    print('save queue:', len(save_queue))
    print(storage.Storage.stats.items())

    cleanup()

    print('cache:', len(contacts_cache))
    print('save queue:', len(save_queue))
    print(storage.Storage.stats.items())


if __name__ == '__main__':
    test()
