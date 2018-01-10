import base64
import json
import logging
import os
from functools import lru_cache

CHUNK_SIZE = 64
MAX_CHUNK_COUNT = int(1024 / CHUNK_SIZE) - 2
logger = logging.getLogger(__name__)


def chunks(s: str, n: int):
    count = 1
    for i in range(0, len(s), n):
        count += 1
        yield s[i:i + n]
        if count == MAX_CHUNK_COUNT:
            break


def encode(obj: dict, path_keys=None) -> str:
    if not path_keys:
        path_keys = ('label', 'uid', 'icon', 'image', 'words')
    obj = { k:v for k,v in obj.items() if k in path_keys}
    s = base64.urlsafe_b64encode(serialize(obj).encode()).decode()
    logger.debug('encode %s %s ==> %s', path_keys, json.dumps(obj, indent=4), s)
    return os.path.sep.join(chunks(s, CHUNK_SIZE))


def decode(encoded_string: str) -> dict:
    s = base64.urlsafe_b64decode(encoded_string.replace('/', '')).decode()
    obj = deserialize(s)
    obj['path'] = encoded_string
    logger.debug('decode %s ==> %s', encoded_string, json.dumps(obj, indent=4))
    return obj


@lru_cache(1)
def short_key_names():
    from importers import browser
    from importers import contact
    from importers import facebook
    from importers import file
    from importers import gmail
    return browser.keys + contact.keys + facebook.keys + file.keys + gmail.keys


@lru_cache(1)
def short_keys():
    return {k: chr(n + ord('a')) for n, k in enumerate(short_key_names())}


@lru_cache(1)
def long_keys():
    return {v: k for k, v in short_keys().items()}


def serialize(obj):
    keys = short_keys()
    return json.dumps({ keys[k]: v for k, v in obj.items() if v and (k in keys)})


def deserialize(s):
    keys = long_keys()
    obj = { keys[k]: v for k, v in json.loads(s).items() }
    logger.debug('deserialize %s, %s, %s', obj['uid'], obj.get('label', '??????'), list(obj.keys()))
    return obj


if __name__ == '__main__':
    obj1 = {
        'uid': 1,
        'label': ['x', 'y'],
        'emails': ['e1', 'e2'],
        'image': (True, False, True),
    }

    keys = list(obj1.keys())
    obj2 = decode(encode(obj1, path_keys=keys))
    json1 = json.dumps(obj1)
    del obj2['path']
    json2 = json.dumps(obj2)
    assert json1 == json2
