import os
import sys


def get_etc_host_path():
    if os.name == 'nt':
        return os.path.join(os.path.sep, 'etc', 'hosts')
    else:
        return os.path.join(os.path.sep, 'private', 'etc', 'hosts')


def setup(remote_url, local_url):
    with open(get_etc_host_path()) as fin:
        contents = fin.read()
        rule = '%s %s' % (local_url, remote_url)
        if rule not in contents:
            print('Adding rule to map %s to %s' % (remote_url, local_url))
            with open(get_etc_host_path(), 'a') as fout:
                fout.write('\n')
                fout.write(rule)
                fout.write('\n')
            clear_DNS()
        else:
            print('Rule to map %s to %s already present' % (remote_url, local_url))


def clear_DNS():
    if os.name == 'nt':
        pass
    else:
        print('killall -HUP mDNSResponder')
        os.system('sudo dscacheutil -flushcache')
        os.system('sudo killall -HUP mDNSResponder')
        # send user to chrome://net-internals/#dns and clear the cache?


def setup_as_administrator():
    if os.name == 'nt':
        pass
    else:
        script = os.path.join(os.getcwd(), "hosts.py")
        print("")
        print("To set up IKKE correctly, we need to add an extra DNS entry to your /private/etc/hosts file.")
        print("")
        print("This is the script being executed: %s" % script)
        print("")
        print("Please provide your adminstrator password.")
        print("")
        command = 'sudo %s %s' % (sys.executable, script)
        os.system('osascript -e \'tell application "Terminal" to do script "%s"\'' % command)
        print("")
        print("This script is launched in another Terminal (use Cmd+Tab to find it).")


if __name__ == '__main__':
    print('Setting up etc/hosts rule for Ikke')
    try:
        setup('ikke', '127.0.0.1:1964')
    except PermissionError as e:
        print("Switching to sudo")
        setup_as_administrator()
