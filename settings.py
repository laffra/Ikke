import json
import os
import time
import utils
import threading


SETTINGS_PATH = os.path.join(utils.HOME_DIR, 'settings.json')


class Settings(dict):
    def __init__(self, path, *args, **kwds):
        self.path = path
        self.lock = threading.Lock()

        if os.path.exists(self.path):
            with open(path, 'r') as f:
                try:
                    self.update(json.load(f))
                except:
                    logging.error('could not load settings.')
        dict.__init__(self, *args, **kwds)

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self.save()

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key) or 0
        except KeyError:
            return 0

    def clear(self):
        with self.lock:
            dict.clear(self)
            self.save()

    def increment(self, key, value=1):
        with self.lock:
            self[key] += value

    def save(self):
        tmp = '%s_%s' % (self.path, time.time())
        with open(tmp, 'w') as f:
            json.dump(self, f, separators=(',', ':'))
        os.replace(tmp, self.path)



settings = Settings(SETTINGS_PATH)


if False:
    print('Settings:')
    for k,v in sorted(settings.items()): print('   ', k, repr(v))

if __name__ == '__main__':
    # settings.clear()

    import random
    import logging
    logging.set_level(logging.DEBUG)
    logging.debug(settings)
    settings['abc'] = random.randint(0, 100)
    settings['xyz'] = random.randint(0, 100)
    logging.debug(settings)
