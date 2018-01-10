import os
from settings import settings
import time
import utils


def install():
    if os.name == 'posix':
        plist_path = os.path.join(utils.INSTALL_FOLDER, 'installation', 'ikke.plist')
        library_path = os.path.expanduser('~/Library/LaunchAgents/ikke.plist')
        with open(library_path, 'w') as fout:
            fout.write(open(plist_path).read())
        os.system('launchctl load -w %s' % library_path)
    settings['installed'] = time.time()


if __name__ == '__main__':
    install()