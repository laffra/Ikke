import time

class Cache(dict):
    def __init__(self, expiration, *args, **kwargs):
        # type (int,*,*) -> None
        dict.__init__(self)
        self.expiration = expiration
        self.update(*args, **kwargs)

    def get(self, key, default=None):
        existing = dict.get(self, key, default)
        if existing:
            last_access,val = existing
            if time.time() - last_access > self.expiration:
                dict.__delitem__(self, key)
                val = None
            return val

    def __getitem__(self, key):
        last_access,val = dict.__getitem__(self, key)
        if time.time() - last_access > self.expiration:
            dict.__delitem__(self, key)
            val = None
        return val

    def __setitem__(self, key, val):
        dict.__setitem__(self, key, (time.time(), val))

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v


if __name__ == '__main__':
    import logging
    logging.set_level(logging.DEBUG)
    cache = Cache(2, foo=1, bar=2)
    logging.debug(cache)
    assert cache['foo']
    assert cache.get('foo')
    time.sleep(3)
    assert cache['foo'] is None
    assert cache.get('foo') is None
    logging.debug(cache)
