import time

class Cache(dict):
    def __init__(self, expiration, *args, **kwargs):
        # type (int,*,*) -> None
        dict.__init__(self)
        self._expiration = expiration
        self._last_cleanup = time.time()
        self.update(*args, **kwargs)

    def get(self, key, default=None):
        self.expire_old_entries()
        existing = dict.get(self, key)
        if existing:
            last_access, val = existing
            if self._has_expired(last_access):
                dict.__delitem__(self, key)
                return default
            return val
        return default

    def __getitem__(self, key):
        self.expire_old_entries()
        try:
            last_access, val = dict.__getitem__(self, key)
            if self._has_expired(last_access):
                dict.__delitem__(self, key)
                return None
            return val
        except KeyError:
            return None

    def _has_expired(self, timestamp, now=0):
        return (now or time.time()) - timestamp > self._expiration

    def expire_old_entries(self):
        now = time.time()
        if self._has_expired(self._last_cleanup):
            for expired_key in filter(None, [k if self._has_expired(v[0], now) else None for k,v in self.items()]):
                del self[expired_key]
            self._last_cleanup = now


    def __setitem__(self, key, val):
        dict.__setitem__(self, key, (time.time(), val))

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def __str__(self):
        self.expire_old_entries()
        return dict.__str__(self)

    def __contains__(self, key):
        self.expire_old_entries()
        if dict.__contains__(self, key):
            self.get(key) # trigger expiration on this key, if needed
            return dict.__contains__(self, key)
        return False


if __name__ == '__main__':
    import logging
    logging.set_level(logging.DEBUG)
    cache = Cache(2, foo=1, bar=2)
    logging.debug(cache)
    assert cache['foo']
    assert cache.get('foo')
    time.sleep(1)
    cache['a1'] = 0
    time.sleep(1)
    cache['a2'] = 0
    time.sleep(1)
    cache['a3'] = 0
    assert cache.get('foo') is None
    logging.debug(cache)
    assert cache['foo'] is None
    assert cache.get('foo') is None
    logging.debug(cache)
    time.sleep(1)
    cache['a4'] = 0
    logging.debug(cache)
    logging.debug('a4' in cache)
    time.sleep(1)
    logging.debug(cache)
    logging.debug('a4' in cache)
    time.sleep(1)
    logging.debug(cache)
    logging.debug('a4' in cache)
    time.sleep(1)
    logging.debug(cache)
    logging.debug('a4' in cache)
