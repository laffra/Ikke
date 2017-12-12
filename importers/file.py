import storage


PATH_ATTRIBUTES = {
    'kind',
    'uid',
    'timestamp',
}


def deserialize(obj):
    return obj if isinstance(obj, storage.File) else storage.File(obj['path'])


def history():
    return 'Files are loaded as attachments for gmail messages'


def poll():
    pass


def load():
    pass
