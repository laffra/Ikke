import cache
import datetime
from importlib import import_module
import json
import logging
import os
import re
import shutil
import stat
import stopwords
import subprocess
import time
from collections import defaultdict

HOME_DIR = os.path.join(os.path.expanduser('~'), 'IKKE')
HOME_DIR_SEGMENT_COUNT = len(HOME_DIR.split(os.path.pathsep))
ITEMS_DIR = os.path.join(HOME_DIR, 'items')
FILE_DIR = os.path.join(ITEMS_DIR, 'file')
MAX_NUMBER_OF_ITEMS = 250

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
        local_path = os.path.join(ITEMS_DIR, obj['kind'], obj['uid'])
        if obj['kind'] != 'file':
            local_path += '.txt'
        parent_dir = os.path.dirname(local_path)
        try:
            os.makedirs(parent_dir)
        except:
            pass # allow multiple threads to create the dir at the same time
        return local_path

    @classmethod
    def load_item(cls, kind, uid):
        # type: (str,str) -> dict
        return cls.resolve(os.path.join(ITEMS_DIR, kind, uid))

    @classmethod
    def add_file(cls, body, data, format="wb"):
        # type: (bytes,dict,str) -> None
        assert 'kind' in data, "Kind needed"
        assert 'uid' in data, "UID needed"
        assert 'timestamp' in data, "Timestamp needed"
        assert type(data['timestamp']) in (int,float), "Number timestamp needed, not %s" % type(data['timestamp'])
        cls.stats['writes'] += 1
        path = cls.get_local_path(data)
        logging.debug('write %s' % path)
        for k,v in data.items():
            logging.debug('     %09s %s' % (k,v))
        try:
            with open(path, format) as fout:
                fout.write(body)
            os.utime(path, (data['timestamp'], data['timestamp']))
            if path in cls.file_cache:
                del cls.file_cache[path]
        except IOError as e:
            logging.error('Cannot add file: %s' % e)
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
        command = cls.get_search_command(query, days)
        paths = list(filter(None, cls.run_command(command)))
        logging.info('Run command "%s" ==> %d results' % (' '.join(command), len(paths)))
        for n,p in enumerate(paths):
            logging.debug('   ', n, p)
        resolve_start = time.time()
        results = list(filter(None, map(cls.resolve, paths)))
        cls.record_search_stats(query, len(paths), time.time() - search_start, len(results), time.time() - resolve_start)
        cls.log_search_stats(query)
        return results

    @classmethod
    def record_search_stats(cls, query,  search_count, search_duration, resolve_count, resolve_duration):
        cls.stats['searches'] += 1
        cls.stats['raw results'] = search_count
        cls.stats['search time'] += search_duration
        cls.stats['results'] = resolve_count
        cls.stats['resolve time'] += resolve_duration
        cls.log_search_stats(query)

    @classmethod
    def log_search_stats(cls, query=None):
        logging.debug('Storage Statistics:')
        logging.debug(logging.LINE)
        if query:
            logging.debug('    query: "%s"' % query)
        for k,v in cls.stats.items():
            logging.debug('    %s: %s' % (k, v))
        logging.debug(logging.LINE)

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
            logging.debug('skip non file: %s' % path[len(HOME_DIR):])
            return None
        item = cls.file_cache.get(path)
        if not item:
            with open(path) as f:
                obj = None
                try:
                    obj = json.loads(f.read())
                    Storage.stats['items read'] += 1
                except Exception as e:
                    logging.debug('no json: %s' % path)
                    Storage.stats['files'] += 1
                    item = File(path)
            if obj:
                item = cls.to_item(obj, path)
            cls.file_cache[path] = item
        return item

    @classmethod
    def get_history(cls, kind):
        handler = import_module('importers.%s' % kind)
        return handler.history()

    @classmethod
    def can_load_more(cls, kind):
        try:
            handler = import_module('importers.%s' % kind)
            return handler.can_load_more()
        except Exception as e:
            logging.debug('Cannot see if can load more: %s %s' % (kind, e))
            return False

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

    @classmethod
    def get_item_count(cls, kind):
        path = os.path.join(HOME_DIR, 'items', kind)
        count = sum(len(files) for _,_,files in os.walk(path))
        return count

    @classmethod
    def load(cls, kind):
        try:
            import_module('importers.%s' % kind).load()
        except Exception as e:
            logging.debug('Could not load %s: %s' % (kind, e))

    @classmethod
    def stop_loading(cls, kind):
        try:
            import_module('importers.%s' % kind).stop_loading()
        except Exception as e:
            logging.debug('Could not stop loading %s: %s' % (kind, e))

    @classmethod
    def is_loading(cls, kind):
        try:
            return import_module('importers.%s' % kind).is_loading()
        except Exception as e:
            logging.debug('Could not check if %s is loading: %s' % (kind, e))

    @classmethod
    def delete_all(cls, kind):
        try:
            return import_module('importers.%s' % kind).delete_all()
        except Exception as e:
            logging.error('Could not stop delete all %s: %s' % (kind, e))

    @classmethod
    def clear(cls, kind):
        path = os.path.realpath(os.path.join(HOME_DIR, 'items', kind))
        if path.startswith(os.path.join(HOME_DIR, 'items')):
            shutil.rmtree(path)
            logging.info('Cleared all data for "%s"' % path)
            return True

class Data(dict):
    def __init__(self, label, obj=None):
        dict.__init__(self)
        self.kind = '<none>'
        self.color = '#888'
        self.email = ''
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

    def is_related_item(self, other):
        return False

    def get_related_items(self):
        return []

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
        extension = os.path.splitext(path)[1][1:].lower()
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

    def same_path(self, path):
        logging.debug('Same path?', self.path[:len(FILE_DIR)], path)
        return self.path[:len(FILE_DIR)] == path

    def set_message_id(self, path):
        self.message_id = os.path.basename(os.path.dirname(path))

    def update_words(self, items):
        for item in items:
            if item.kind == 'gmail' and item.message_id == self.message_id:
                self.words = item.words


Storage.setup()

if __name__ == '__main__':
    logging.set_level(logging.DEBUG)
    if False:
        path = "/Users/laffra/IKKE/gmail/content_type/text-html/kind/gmail/label/activity aler ... n alert limit/message_id/<22f44d4d-ad5a-40f6-83dc-336b2b94294c@xtnvs5mta401.xt.local>/receivers/[/1/laffra@gmail.com/senders/[/1/onlinebanking@ealerts.bankofamerica.com/subject/Activity Alert: Electronic or Online Withdrawal Over Your Chosen Alert Limit/thread/activity aler ... n alert limit - ['laffra@gmail.com', 'onlinebanking@ealerts.bankofamerica.com']/timestamp/1510537596/uid/16455 (UID 92562 RFC822 {25744}.txt"
        for k,v in Storage.resolve(path).items():
            if v:
                logging.debug('%s=%s' % (k,v))
        logging.debug()

    if True:
        for item in Storage.search('anaconda', days=91):
            if item.kind == 'contact':
                logging.debug(' %s %s' % (item.uid, item.label))
        logging.debug()

    if False:
        for kind in ['browser','file','gmail','contact']:
            logging.debug('%s: %d' % (kind, Storage.get_item_count(kind)))

    if False:
        for k,v in Storage.search_contact('messaging-digest-noreply@linkedin.com').items():
            if v:
                logging.debug('%s=%s' % (k,v))
        logging.debug()



