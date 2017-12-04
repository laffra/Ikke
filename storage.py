from __future__ import print_function

import cache
import datetime
from importlib import import_module
import itertools
import json
import os
import shutil
import stat
import stopwords
import subprocess
import time
from utils import get_timestamp

import sys
if sys.version_info >= (3,):
    from json.decoder import JSONDecodeError
    from urllib.parse import quote
    from urllib.parse import unquote
else:
    JSONDecodeError = ValueError
    from urllib import pathname2url
    def quote(s,safe=''):
        return s.replace('/', '%2F')
    from urllib import url2pathname
    def unquote(s): return url2pathname(s)

import uuid
from collections import defaultdict

HOME_DIR = os.path.join(os.path.expanduser('~'), 'IKKE')
HOME_DIR_SEGMENT_COUNT = len(HOME_DIR.split(os.path.pathsep))
CLEANUP_FILE_NAME_RE = '([^a-zA-Z0-9]|http|www|https)'
SHORT_DIR = os.path.join(HOME_DIR, 'items')

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
            cls.get_filename(data),
            json.dumps(data),
            data,
            "w"
        )

    @classmethod
    def add_binary_data(cls, content, data):
        # type: (bytes,dict) -> None
        cls.add_file(
            cls.get_filename(data, extension=''),
            content,
            data,
            "wb"
        )

    @classmethod
    def get_local_path(cls, path):
        # type: (str) -> str
        local_path = os.path.join(HOME_DIR, path)
        if os.name == 'nt':
            if os.path.sep in path:
                local_path = os.path.join(SHORT_DIR, '%s.txt' % uuid.uuid4())
            local_path = '\\\\?\\' + local_path
        try:
            os.makedirs(os.path.dirname(local_path))
        except:
            pass # ignore if dirs already exist
        return local_path

    @classmethod
    def add_file(cls, filename, body, data, format="wb"):
        # type: (str,bytes,dict,str) -> None
        assert 'kind' in data, "Kind needed"
        assert 'uid' in data, "UID needed"
        assert 'timestamp' in data, "Timestamp needed"
        assert type(data['timestamp']) in (int,float), "Number timestamp needed, not %s" % type(data['timestamp'])
        cls.stats['writes'] += 1
        path = cls.get_local_path(filename)
        try:
            with open(path, format) as fout:
                fout.write(body)
            os.utime(path, (data['timestamp'], data['timestamp']))
            obj = cls.resolve(path)
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
            since = 'modified:%s-%s' % (cls.get_day_month_year(days), cls.get_day_month_year(0))
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
        cls.log_search_stats(len(paths), time.time() - search_start, len(results), time.time() - resolve_start)
        return results

    @classmethod
    def log_search_stats(cls, search_count, search_duration, resolve_count, resolve_duration):
        cls.stats['searches'] += 1
        cls.stats['raw results'] = search_count
        cls.stats['search time'] += search_duration
        cls.stats['results'] = resolve_count
        cls.stats['resolve time'] += resolve_duration
        print('STORAGE: %s STATS %s' % ('#'*32, '#'*32))
        for k,v in cls.stats.items():
            print('STORAGE: %s: %s' % (k, v))
        print('STORAGE: %s' % ('#'*71))

    @classmethod
    def get_filename(cls, data, extension='.txt'):
        # type: (dict,str) -> str
        handler = import_module('importers.%s' % data['kind'])
        def serialize(value):
            if isinstance(value, list):
                quoted = [quote(v.encode('utf8'), safe='') for v in value]
                return '[%s%s%s%s' % (os.path.sep, len(quoted), os.path.sep, os.path.sep.join(quoted))
            if isinstance(value, float):
                return '%f' % value
            if isinstance(value, int):
                return '%d' % value
            return quote(('%s' % value).encode('utf8'), '')[:250]
        kv = [(k,serialize(v)) for k,v in data.items() if k in handler.PATH_ATTRIBUTES and v]
        kv = sorted(kv, key=lambda kv: kv[0])
        segments = os.path.sep.join(itertools.chain(*kv)).split(os.path.sep)
        path = os.path.sep.join(segments)
        return os.path.join(data['kind'], '%s%s' % (path, extension))

    @classmethod
    def search_contact(cls, email):
        # type: (str) -> dict
        contact = cls.search_cache.get(email)
        if not contact:
            path = os.path.join(HOME_DIR, 'contact', 'email', quote(email))
            for root, dirs, files in os.walk(path):
                for file in files:
                    with open(os.path.join(root, file), 'r') as f:
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
        item = cls.file_cache.get(path)
        if not item:
            if path.startswith(SHORT_DIR):
                with open(path) as f:
                    text = '???'
                    obj = None
                    try:
                        text = f.read()
                        Storage.stats['items read'] += 1
                        obj = json.loads(text)
                    except UnicodeDecodeError as e:
                        Storage.stats['failed'] += 1
                        print('STORAGE: json error %s: %s' % (e, path))
                    except JSONDecodeError as e:
                        Storage.stats['failed'] += 1
                        print('STORAGE: json error %s: %s' % (e, path))
            else:
                kv = cls.split_path(path)
                kind, kv = kv[0], kv[1:]
                if kind == 'file':
                    obj = File(path)
                else:
                    keys = []
                    values = []
                    index = 0
                    while index < len(kv)-1:
                        key = kv[index]
                        value = kv[index+1]
                        if value == '[':
                            count = int(kv[index+2])
                            value = kv[index+3:index+3+count]
                            index += count + 1
                        keys.append(key)
                        values.append(value)
                        index += 2
                    if values:
                        values[-1] = values[-1][:-4]
                    obj = dict(zip(keys, [v for v in values]))
                    if not 'uid' in obj:
                        return None
                    obj['kind'] = kind
                    obj['label'] = obj.get('label', obj['uid'])
                    obj['words'] = obj['label'].split(' ')
                    t = obj.get('timestamp', get_timestamp())
                    obj['timestamp'] = float(obj.get('timestamp', get_timestamp()))
            if obj:
                item = cls.to_item(obj, path)
                cls.file_cache[path] = item
        return item

    @classmethod
    def split_path(cls, path):
        return [
            unquote(p).replace('+',' ')
            for p in path[len(HOME_DIR) + 1:].split(os.path.sep)
        ]

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

    if True:
        results = sorted((os.path.getmtime(result.path),result.path) for result in Storage.search('laffra', days=5))
        now = datetime.datetime.now()
        for timestamp,path in results[:5]:
            print('%s  %s' % (now - datetime.datetime.fromtimestamp(timestamp), path))
        print()

    if False:
        for k,v in Storage.search_contact('laffra@gmail.com').items():
            if v:
                print('%s=%s' % (k,v))
        print()



