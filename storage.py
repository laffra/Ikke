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

import sys
if sys.version_info >= (3,):
    from json.decoder import JSONDecodeError
    from urllib.parse import quote
    from urllib.parse import unquote
else:
    JSONDecodeError = ValueError
    from urllib import pathname2url as quote
    from urllib import url2pathname as unquote

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
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        return local_path

    @classmethod
    def add_file(cls, filename, body, data, format="wb"):
        # type: (str,bytes,dict,str) -> None
        assert 'kind' in data, "Kind needed"
        assert 'uid' in data, "UID needed"
        assert 'timestamp' in data, "Timestamp needed"
        cls.stats['writes'] += 1
        path = cls.get_local_path(filename)
        try:
            with open(path, format) as fout:
                fout.write(body)
            os.utime(path, (data['timestamp'], data['timestamp']))
            print('STORAGE: Add', path)
        except IOError as e:
            print(e)
            raise

    @classmethod
    def included(cls, obj, timestamp):
        # type: (dict,float) -> bool
        return obj and timestamp < obj['timestamp']

    @classmethod
    def get_search_command(cls, query):
        if os.name == 'nt':
            localdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'localsearch')
            return ['cscript', '/nologo', os.path.join(localdir, 'search.vbs'), HOME_DIR, query]
        elif os.name == 'posix':
            operator = '-interpret'
            operands = (query + ' ') if operator == '-interpret' else query
            return ['mdfind', '-onlyin', HOME_DIR, operator, operands]
        else:
            raise ValueError('Unsupported OS:', os.name)

    @classmethod
    def search(cls, query, timestamp, operator='-interpret'):
        # type: (str,float,str) -> list
        assert isinstance(query, str)
        assert isinstance(timestamp, float), 'unexpected type %s: %s' % (type(timestamp), timestamp)
        key = '%s-%d' % (query, timestamp % 60)
        results = cls.search_cache.get(key)
        if results is None:
            cls.stats['searches'] += 1
            start = time.time()
            paths = list(cls.run_command(cls.get_search_command(query)))
            cls.stats['raw results'] = len(paths)
            cls.stats['search-time'] += time.time() - start
            results = [result for result in (map(cls.resolve, paths)) if cls.included(result, timestamp)]
            results = cls.search_cache[key] = list(filter(None, results))
            cls.stats['results'] = len(results)
        print('STORAGE: ############## STATS')
        for k,v in cls.stats.items():
            print('STORAGE:   ', k, ':', v)
        return results

    @classmethod
    def get_filename(cls, data, extension='.txt'):
        # type: (dict,str) -> str
        handler = import_module('importers.%s' % data['kind'])
        def serialize(value):
            if isinstance(value, list):
                quoted = [quote(v, safe='') for v in value]
                return '[%s%s%s%s' % (os.path.sep, len(quoted), os.path.sep, os.path.sep.join(quoted))
            return quote(str(value), '')[:250]
        kv = [(k,serialize(v)) for k,v in data.items() if k in handler.PATH_ATTRIBUTES and v]
        kv = sorted(kv, key=lambda kv: kv[0])
        segments = os.path.sep.join(itertools.chain(*kv)).split(os.path.sep)
        path = os.path.sep.join(segments)
        return os.path.join(data['kind'], '%s%s' % (path, extension))

    @classmethod
    def search_contact(cls, email):
        # type: (str) -> dict
        path = os.path.join(HOME_DIR, 'contact', 'email', quote(email))
        for root, dirs, files in os.walk(path):
            for file in files:
                with open(os.path.join(root, file), 'r') as f:
                    from importers import contact
                    try:
                        return contact.deserialize(json.loads(f.read()))
                    except:
                        pass

    @classmethod
    def search_file(cls, filename):
        # type: (str) -> list
        return cls.search(filename, operator='-name')

    @classmethod
    def set_comment(cls, path, comment):
        # type: (str,str) -> None
        if comment:
            os.popen(SET_COMMENT_SCRIPT % (path, comment.replace('"', ' ')))

    @classmethod
    def get_comment(cls, path):
        return os.popen(GET_COMMENT_SCRIPT % path).read()

    @classmethod
    def resolve(cls, path):
        # type: (str) -> dict
        item = cls.file_cache.get(path)
        if not item:
            if path.startswith(SHORT_DIR):
                with open(path) as f:
                    text = '???'
                    obj = None
                    try:
                        text = f.read()
                        obj = json.loads(text)
                    except UnicodeDecodeError as e:
                        Storage.stats['failed'] += 1
                        print('STORAGE: Cannot convert binary content to json',e, path)
                    except JSONDecodeError as e:
                        Storage.stats['failed'] += 1
                        print('STORAGE: Cannot convert to json',e, path)
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
                        print('   ', index, key, value)
                        index += 2
                    if values:
                        values[-1] = values[-1][:-4]
                    obj = dict(zip(keys, [v for v in values]))
                    if not 'uid' in obj:
                        return None
                    obj['kind'] = kind
                    obj['label'] = obj.get('label', obj['uid'])
                    obj['words'] = obj['label'].split(' ')
                    obj['timestamp'] = float(obj.get('timestamp', time.time()))
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
        dt = datetime.datetime.fromtimestamp(item.timestamp)
        item.date = '%s/%s/%s %s:%s' % (dt.year, dt.month, dt.day, dt.hour, dt.minute)
        return item

    @classmethod
    def get_year_month_day(cls, timestamp):
        # type: (float) -> tuple
        dt = datetime.datetime.fromtimestamp(timestamp)
        return '%s' % dt.year, '%02d' % dt.month, '%02d' % dt.day

    @classmethod
    def run_command(cls, command):
        # type: (list) -> str
        print('SERVER: run', command)
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        stdout, stderr = process.communicate()
        for line in stdout.split('\n'):
            yield line.strip()

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
        self.label = filename
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
        print('Deleting all of', path, 'in', 10-n, 'seconds')
        time.sleep(1)
    shutil.rmtree(path)

Storage.setup()

if __name__ == '__main__':
    if False:
        path = "/Users/laffra/IKKE/gmail/content_type/text-html/kind/gmail/label/activity aler ... n alert limit/message_id/<22f44d4d-ad5a-40f6-83dc-336b2b94294c@xtnvs5mta401.xt.local>/receivers/[/1/laffra@gmail.com/senders/[/1/onlinebanking@ealerts.bankofamerica.com/subject/Activity Alert: Electronic or Online Withdrawal Over Your Chosen Alert Limit/thread/activity aler ... n alert limit - ['laffra@gmail.com', 'onlinebanking@ealerts.bankofamerica.com']/timestamp/1510537596/uid/16455 (UID 92562 RFC822 {25744}.txt"
        for k,v in Storage.resolve(path).items():
            if v:
                print(k,'=',v)
        print()

    if False:
        for n,p in enumerate(Storage.search('reza', timestamp=0.0)):
            print(n)
            for k,v in p.items():
                print('  ', k, repr(v))
        print(Storage.stats)
        print()

    if False:
        for k,v in Storage.search_contact('laffra@gmail.com').items():
            if v:
                print(k,'=',v)
        print(Storage.stats)
        print()

    if True:
        delete_all('file')

