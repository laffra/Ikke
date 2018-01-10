import logging
import os
import sys


def get_etc_host_path():
    if os.name == 'nt':
        return os.path.join(os.path.sep, 'etc', 'hosts')
    else:
        return os.path.join(os.path.sep, 'etc', 'hosts')


def setup(remote_url, local_url):
    with open(get_etc_host_path()) as fin:
        contents = fin.read()
        rule = '%s %s' % (local_url, remote_url)
        if rule not in contents:
            logging.info('Adding rule to map %s to %s' % (remote_url, local_url))
            with open(get_etc_host_path(), 'a') as fout:
                fout.write('\n')
                fout.write(rule)
                fout.write('\n')
        else:
            logging.info('Rule to map %s to %s already present' % (remote_url, local_url))
        clear_DNS()


def clear_DNS():
    if os.name == 'nt':
        pass
    else:
        logging.info('killall -HUP mDNSResponder')
        os.system('sudo dscacheutil -flushcache')
        os.system('sudo killall -HUP mDNSResponder')
        # send user to chrome://net-internals/#dns and clear the cache?


def setup_as_administrator():
    if os.name == 'nt':
        pass
    else:
        command = 'sudo %s %s' % (sys.executable, __file__)
        os.system('osascript -e \'tell application "Terminal" to do script "%s"\'' % command)


if __name__ == '__main__':
    logging.set_level(logging.INFO)
    logging.info('Setting up etc/hosts rule for Ikke')
    setup('search.ikke.io', 'localhost')
