from settings import settings
import storage
from importers import gmail

keys = ('uid', 'timestamp')

def deserialize(obj):
    return HangoutsItem(obj)

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


class HangoutsItem(gmail.GMailNode):
    def __init__(self, obj):
        super(HangoutsItem, self).__init__(obj)
        self.kind = 'hangouts'
        self.icon = 'get?path=icons/hangouts-icon.png'
        dict.update(self, vars(self))

    @classmethod
    def deserialize(cls, obj):
        return HangoutsItem(obj)

    def render(self, query):
        return '<script>window.alert(\'%s\');</script>' % self.label


def cleanup():
    pass


settings['hangouts/can_load_more'] = True
settings['hangouts/can_delete'] = True

deserialize = HangoutsItem.deserialize
