import os
import storage
import json


SETTINGS_PATH = os.path.join(storage.HOME_DIR, 'settings.json')


class Settings(dict):
    def __init__(self, path, *args, **kwds):
        self.path = path
        if os.path.exists(self.path):
            with open(path, 'r') as f:
                self.update(json.load(f))
        dict.__init__(self, *args, **kwds)

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self.save()

    def clear(self):
        dict.clear(self)
        self.save()

    def save(self):
        with open(self.path, 'w') as f:
            json.dump(self, f, separators=(',', ':'))


settings = Settings(SETTINGS_PATH)


if __name__ == '__main__':
    # settings.clear()

    import random
    print(settings)
    settings['abc'] = random.randint(0, 100)
    settings['xyz'] = random.randint(0, 100)
    print(settings)
