import storage


PATH_ATTRIBUTES = {
    'kind',
    'uid',
    'timestamp',
}


def deserialize(obj):
    return obj if isinstance(obj, storage.File) else storage.File(obj['path'])


def history():
    msg = 'Nothing loaded yet.'
    count = storage.Storage.get_item_count('file')
    if count > 0:
        msg = '%d files were loaded as attachments for gmail messages' % count
    return msg


def delete_all():
    return storage.Storage.clear('file')


def poll():
    pass


def can_load_more():
    return False


def load():
    pass
