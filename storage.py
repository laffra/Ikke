from __future__ import print_function

import cache
import datetime
from importlib import import_module
import json
import os
import re
import shutil
import stat
import stopwords
import subprocess
import time

import sys
if sys.version_info >= (3,):
    from json.decoder import JSONDecodeError
    from urllib.parse import quote
    from urllib.parse import unquote
else:
    JSONDecodeError = ValueError
    def quote(s,safe=''):
        return s.replace('/', '%2F')
    from urllib import url2pathname
    def unquote(s): return url2pathname(s)

from collections import defaultdict

HOME_DIR = os.path.join(os.path.expanduser('~'), 'IKKE')
HOME_DIR_SEGMENT_COUNT = len(HOME_DIR.split(os.path.pathsep))
CLEANUP_FILE_NAME_RE = '([^a-zA-Z0-9]|http|www|https)'
ITEMS_DIR = os.path.join(HOME_DIR, 'items')
ILLEGAL_FILENAME_CHARACTERS = re.compile(r'[~#%&*{}:<>?+|"]')

GET_COMMENT_SCRIPT = '''osascript<<END
    tell application "Finder"
        set filePath to POSIX file "%s"
        set the_File to filePath as alias
        get comment of the_File
    end tell 
END'''

SET_COMMENT_SCRIPT = '''osascript<<END
    tell application "Finder"
        set filePath to POSIX file "%s"
        set fileComment to "%s"
        set the_File to filePath as alias
        set comment of the_File to fileComment
    end tell 
END'''

FILE_FORMAT_ICONS = {
    'pdf': 'icons/pdf-icon.png',
    'rtf': 'icons/rtf-icon.png',
    'doc': 'icons/word-doc-icon.png',
    'docx': 'icons/word-doc-icon.png',
    'ics': 'icons/calendar-icon.png',
    'xls': 'icons/excel-xls-icon.png',
    'xlsx': 'icons/excel-xls-icon.png',
    'pages': 'icons/keynote-icon.png',
    'ppt': 'icons/ppt-icon.png',
    'ico': 'icons/ico.png',
    'tiff': 'icons/tiff-icon.png',
    'pptx': 'icons/ppt-icon.png',
    'www': 'icons/browser-web-icon.png',
    'txt': 'icons/text-icon.png',
    'file': 'icons/file-icon.png',
}
FILE_FORMAT_IMAGE_EXTENSIONS = { 'png', 'ico', 'jpg', 'jpeg', 'gif', 'pnm' }


class Storage:
    stats = defaultdict(int)
    search_cache = cache.Cache(60)
    file_cache = cache.Cache(60)

    @classmethod
    def add_data(cls, data):
        # type: (dict) -> None
        cls.add_file(
            json.dumps(data),
            data,
            "w"
        )

    @classmethod
    def add_binary_data(cls, content, data):
        # type: (bytes,dict) -> None
        cls.add_file(
            content,
            data,
            "wb"
        )

    @classmethod
    def get_local_path(cls, obj):
        # type: (dict) -> str
        uid = re.sub(ILLEGAL_FILENAME_CHARACTERS, '_', obj['uid'])
        local_path = os.path.join(os.path.join(ITEMS_DIR, obj['kind']), uid)
        if obj['kind'] != 'file':
            local_path += '.txt'
        parent_dir = os.path.dirname(local_path)
        try:
            os.makedirs(parent_dir)
        except:
            pass # allow multiple threads to create the dir at the same time
        return local_path

    @classmethod
    def add_file(cls, body, data, format="wb"):
        # type: (bytes,dict,str) -> None
        assert 'kind' in data, "Kind needed"
        assert 'uid' in data, "UID needed"
        assert 'timestamp' in data, "Timestamp needed"
        assert type(data['timestamp']) in (int,float), "Number timestamp needed, not %s" % type(data['timestamp'])
        cls.stats['writes'] += 1
        path = cls.get_local_path(data)
        print('STORAGE: write %s - %s %s' % (path, data['kind'], data['uid']))
        try:
            with open(path, format) as fout:
                fout.write(body)
            os.utime(path, (data['timestamp'], data['timestamp']))
        except IOError as e:
            print(e)
            raise

    @classmethod
    def get_search_command(cls, query, days):
        # type (str,int) -> list
        if os.name == 'nt':
            local_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'localsearch')
            since = cls.get_year_month_day(days)
            return ['cscript', '/nologo', os.path.join(local_dir, 'search.vbs'), HOME_DIR, query, since]
        elif os.name == 'posix':
            operator = '-interpret'
            since = 'modified:%s-%s' % (cls.get_day_month_year(days), cls.get_day_month_year(-1))
            return ['mdfind', '-onlyin', HOME_DIR, operator, query, since]
        else:
            raise ValueError('Unsupported OS:', os.name)

    @classmethod
    def search(cls, query, days, operator='-interpret'):
        # type: (str,int,str) -> list
        assert isinstance(query, str)
        assert isinstance(days, int), 'unexpected type %s: %s' % (type(days), days)
        search_start = time.time()
        paths = list(cls.run_command(cls.get_search_command(query, days)))
        resolve_start = time.time()
        results = list(filter(None, map(cls.resolve, paths)))
        cls.log_search_stats(query, len(paths), time.time() - search_start, len(results), time.time() - resolve_start)
        return results

    @classmethod
    def log_search_stats(cls, query,  search_count, search_duration, resolve_count, resolve_duration):
        cls.stats['searches'] += 1
        cls.stats['raw results'] = search_count
        cls.stats['search time'] += search_duration
        cls.stats['results'] = resolve_count
        cls.stats['resolve time'] += resolve_duration
        cls.print_search_stats(query)

    @classmethod
    def print_search_stats(cls, query=None):
        print('STORAGE: %s STATS %s' % ('#'*32, '#'*32))
        if query:
            print('STORAGE: query: "%s"' % query)
        for k,v in cls.stats.items():
            print('STORAGE: %s: %s' % (k, v))
        print('STORAGE: %s' % ('#'*71))

    @classmethod
    def search_contact(cls, email):
        # type: (str) -> dict
        contact = cls.search_cache.get(email)
        if not contact:
            path = os.path.join(HOME_DIR, 'items', 'contact', email + '.txt')
            if os.path.exists(path):
                with open(path, 'r') as f:
                    from importers import contact
                    try:
                        contact = contact.deserialize(json.loads(f.read()))
                        cls.stats['contacts read'] += 1
                    except:
                        pass
            cls.search_cache[email] = contact
        return contact

    @classmethod
    def search_file(cls, filename):
        # type: (str) -> list
        return cls.search(filename, operator='-name')

    @classmethod
    def resolve(cls, path):
        # type: (str) -> (dict,None)
        if not path or not os.path.isfile(path):
            # print('STORAGE: skip non file: %s' % path[len(HOME_DIR):])
            return None
        item = cls.file_cache.get(path)
        if not item:
            with open(path) as f:
                obj = None
                try:
                    obj = json.loads(f.read())
                    Storage.stats['items read'] += 1
                except Exception as e:
                    Storage.stats['files'] += 1
                    item = File(path)
            if obj:
                item = cls.to_item(obj, path)
            cls.file_cache[path] = item
        return item

    @classmethod
    def to_item(cls, obj, path):
        handler = import_module('importers.%s' % obj['kind'])
        item = handler.deserialize(obj)
        item.path = item['path'] = path
        dt = datetime.datetime.fromtimestamp(float(item.timestamp))
        item.date = '%s/%s/%s %s:%s' % (dt.year, dt.month, dt.day, dt.hour, dt.minute)
        return item

    @classmethod
    def get_day_month_year(cls, days):
        # type: (int) -> str
        dt = datetime.datetime.now() - datetime.timedelta(days=days)
        return '%s/%s/%s' % (dt.day, dt.month, dt.year)

    @classmethod
    def get_year_month_day(cls, days):
        # type: (int) -> str
        dt = datetime.datetime.now() - datetime.timedelta(days=days)
        return '%4d-%02d-%02d' % (dt.year, dt.month, dt.day)

    @classmethod
    def run_command(cls, command):
        # type: (list) -> str
        print('SERVER: run %s' % ' '.join(command))
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        stdout, stderr = process.communicate()
        try:
            for line in stdout.split('\n'):
                yield line.strip()
        except:
            for line in stdout.split(b'\n'):
                yield str(line.strip(), 'utf8')

    @classmethod
    def setup(cls):
        if not os.path.exists(HOME_DIR):
            os.mkdir(HOME_DIR)
            os.chmod(HOME_DIR, stat.S_IEXEC)


class Data(dict):
    def __init__(self, label, obj=None):
        dict.__init__(self)
        self.kind = '<none>'
        self.color = '#888'
        self.persons = []
        self.receiver = ''
        self.uid = label
        self.label = label
        self.body = ''
        self.icon = 'get?path=icons/white_pixel.png'
        self.icon_size = 0
        self.font_size = 0
        self.zoomed_icon_size = 0
        self.image = ''
        self.words = []
        self.timestamp = 0

        dict.update(self, vars(self))
        if obj:
            dict.update(self, obj)
            for k,v in obj.items():
                setattr(self, k, v)

    def __hash__(self):
        return hash(self.uid)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.uid == other.uid

    def update(self, obj):
        obj['timestamp'] = self.timestamp

    def update_words(self, items):
        pass

    def is_duplicate(self, duplicates):
        return False

    def save(self):
        Storage.stats['writes'] += 1
        Storage.add_data(self)


class File(Data):
    def __init__(self, path):
        super(File, self).__init__(path)
        self.kind = 'file'
        self.color = 'blue'
        self.path = path
        filename = os.path.basename(path)
        self.words = stopwords.remove_stopwords(filename.replace('+', ' '))
        self.filename = filename
        self.uid = filename
        self.label = filename.replace('%20', ' ')
        self.timestamp = os.path.getmtime(path)
        extension = os.path.splitext(path)[1][1:]
        self.icon_size = 32
        self.zoomed_icon_size = 128
        icon = FILE_FORMAT_ICONS.get(extension, 'icons/file-icon.png')
        if extension in FILE_FORMAT_IMAGE_EXTENSIONS:
            icon = path
            self.icon_size = 64;
            self.zoomed_icon_size = 256
        self.icon = 'get?path=%s' % icon
        dict.update(self, vars(self))
        self.set_message_id(path)

    def set_message_id(self, path):
        self.message_id = os.path.basename(os.path.dirname(path))

    def update_words(self, items):
        for item in items:
            if item.kind == 'gmail' and item.message_id == self.message_id:
                self.words = item.words


def delete_all(kind):
    # type (str) -> None
    path = Storage.get_local_path(kind)
    for n in range(10):
        print('Deleting all of %s in %d seconds' % (path, 10-n))
        time.sleep(1)
    shutil.rmtree(path)

Storage.setup()

if __name__ == '__main__':
    if False:
        path = "/Users/laffra/IKKE/gmail/content_type/text-html/kind/gmail/label/activity aler ... n alert limit/message_id/<22f44d4d-ad5a-40f6-83dc-336b2b94294c@xtnvs5mta401.xt.local>/receivers/[/1/laffra@gmail.com/senders/[/1/onlinebanking@ealerts.bankofamerica.com/subject/Activity Alert: Electronic or Online Withdrawal Over Your Chosen Alert Limit/thread/activity aler ... n alert limit - ['laffra@gmail.com', 'onlinebanking@ealerts.bankofamerica.com']/timestamp/1510537596/uid/16455 (UID 92562 RFC822 {25744}.txt"
        for k,v in Storage.resolve(path).items():
            if v:
                print('%s=%s' % (k,v))
        print()

    if False:
        results = sorted((os.path.getmtime(result.path),result.path) for result in Storage.search('laffra', days=5))
        now = datetime.datetime.now()
        for timestamp,path in results[:5]:
            print('%s  %s' % (now - datetime.datetime.fromtimestamp(timestamp), path))
        print()

    if False:
        File('/Users/laffra/IKKE/items/file/<CALA7AgVq6zqJarWf9gY+r+kPQMxqZnp3JSQovhuAh6=DryGjTg@mail.gmail.com>/Trip on 16 Nov 17 - PNR ref AMMF2I.pdf')

    if True:
        for k,v in Storage.search_contact('laffra@gmail.com').items():
            if v:
                print('%s=%s' % (k,v))
        print()



