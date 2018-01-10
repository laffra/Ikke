from settings import settings
import storage

keys = ('uid', 'timestamp')
path_keys = ('label', 'uid', 'icon', 'image', 'words')


def deserialize(obj):
    return obj if isinstance(obj, storage.File) else storage.File(obj['path'])


def get_status():
    return '%d files were loaded as attachments for gmail messages' % settings['file/count']


def delete_all():
    pass


def poll():
    pass


def can_load_more():
    return False


def load():
    pass
