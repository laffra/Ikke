import base64
import logging
import quopri
import re
from settings import settings
import stopwords
import storage
import time
from urllib.parse import quote


NAME_CLEANUP_RE = re.compile('\'')

contacts_cache = {}
save_queue = set()


def decode(encoded_string):
    encoded_word_regex = r'=\?{1}(.+)\?{1}([B|Q])\?{1}(.+)\?{1}='
    match = re.match(encoded_word_regex, encoded_string)
    if match:
        charset, encoding, encoded_text = match.groups()
        byte_string = base64.b64decode(encoded_text) if encoding == 'B' else quopri.decodestring(encoded_text)
        return byte_string.decode(charset)
    return encoded_string


def remove_quotes(name):
    return ' '.join(re.sub(NAME_CLEANUP_RE, '', decode(name)).split(', '))


keys = ('uid', 'email', 'label', 'names', 'phones', 'timestamp')
path_keys = ('label', 'uid', 'icon', 'image', 'words')

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
            'words': stopwords.remove_stopwords(name),
            'names': [name] if name else [],
            'timestamp': timestamp,
            'phones': phones or [],
        })
        logging.debug('CONTACT: new contact ==> %s %s' % (email, contact.names))
        save_queue.add(contact)
    if name and not name in contact.names:
        contact.names.append(name)
        save_queue.add(contact)
    contacts_cache[email] = contact
    return contact


class Contact(storage.Data):
    def __init__(self, obj):
        super(Contact, self).__init__(obj.get('email') or obj.get('label'), obj)
        self.kind = 'contact'
        self.uid = obj['uid'] or obj['email']
        self.email = obj.get('email')
        self.names = obj.get('names', [])
        self.phones = obj.get('phones',[])
        if len(self.names) > 1:
            import collections
            counter = collections.Counter()
            counter.update(' '.join(self.names).split(' '))
            self.name = '%s %s' % (counter.most_common(1)[0][0], self.email.split('@')[1])
        else:
            self.name = self.names and self.names[0] or self.email
        self.name = self.name or self.label or self.email
        self.label = self.name
        self.color = 'purple'
        self.icon = 'get?path=icons/person-icon.png'
        self.font_size = 14
        self.timestamp = obj.get('timestamp', 0)
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
            self.mark_duplicate()
            return True
        duplicates.add(self.email)
        return False

    def __hash__(self):
        return hash(self.uid)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.uid == other.uid

    def render(self, query):
        url = '/?q=%s' % quote(self.label)
        return '<html><a href="%s">Search in Ikke</a>' % url

    def __repr__(self):
        return "<Contact %s>" % self.email



deserialize = Contact.deserialize


def delete_all():
    storage.Storage.clear('contact')
    settings['contact/count'] = 0


def can_load_more():
    return False


def poll():
    pass


def get_status():
    count = settings['contact/count']
    return '%d contacts' % count


def is_loading():
    return False


def stop_loading():
    pass


def cleanup():
    if save_queue:
        logging.debug('CONTACT: cleanup, save %d contacts' % len(save_queue))
    for _, contact in enumerate(save_queue.copy()):
        settings.increment('contact/count')
        contact.save()
    save_queue.clear()


def render(args):
    return ""

if __name__ == '__main__':
    import os
    import utils
    for _,_,files in os.walk(utils.CONTACT_DIR):
        for n,file in enumerate(files):
            item = storage.Storage.resolve_path(os.path.join(utils.CONTACT_DIR, file))
            item.words = stopwords.remove_stopwords(item.name)
            if n%100==0: print(n, item.words)
    #test()
