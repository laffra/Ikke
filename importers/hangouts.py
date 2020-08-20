import logging
from settings import settings
import storage
from importers import gmail
import urllib

keys = ('uid', 'timestamp')
logger = logging.getLogger(__name__)

def deserialize(obj):
    return HangoutNode(obj)

def get_status():
    return '%d hangouts messages were loaded' % settings['hangouts/count']


def delete_all():
    pass


def poll():
    pass


def can_load_more():
    return False


def load():
    pass


class HangoutNode(gmail.GMailNode):
    def __init__(self, obj):
        super(HangoutNode, self).__init__(obj)
        self.kind = 'hangouts'
        self.color = 'green'
        self.icon = 'get?path=icons/hangouts-icon.png'
        dict.update(self, vars(self))

    @classmethod
    def deserialize(cls, obj):
        return HangoutNode(obj)

    def is_related_item(self, other):
        return False

    def get_related_items(self):
        return []

    def render(self, query):
        return '<script>window.alert(\'%s\');</script>' % self.label


def cleanup():
    pass


def render(args):
    import re
    words = list(filter(lambda word: re.match("^[a-zA-Z]*$", word), args["subject"].split()))[:10]
    url = 'https://mail.google.com/mail/u/0/#search/in:chats %s' % urllib.parse.quote(' '.join(words))
    return '<script>document.location=\'%s\';</script>' % url


settings['hangouts/can_load_more'] = True
settings['hangouts/can_delete'] = True

deserialize = HangoutNode.deserialize
