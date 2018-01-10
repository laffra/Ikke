import cache
import compressor
import datetime
from importlib import import_module
import logging
import os
from settings import settings
import shutil
import stat
import stopwords
import subprocess
import utils
import time
from collections import defaultdict

MAX_NUMBER_OF_ITEMS = 500

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
ITEM_KINDS = [ 'contact', 'gmail', 'browser', 'file', 'facebook' ]

logger = logging.getLogger(__name__)

item_handlers = { }

class Storage:
    stats = defaultdict(int)
    search_cache = cache.Cache(60)
    file_cache = cache.Cache(60)
    history_cache = cache.Cache(60)

    @classmethod
    def add_data(cls, data):
        # type: (dict) -> None
        obj = compressor.deserialize(compressor.serialize(data))
        cls.add_file(
            compressor.serialize(data),
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
        local_path = os.path.join(utils.ITEMS_DIR, obj['kind'], obj['uid'])
        if local_path.endswith('/'):
            local_path += '_'
        if obj['kind'] not in ('contact', 'file'):
            path_keys = item_handlers[obj['kind']].path_keys
            local_path = os.path.join(utils.ITEMS_DIR, obj['kind'], compressor.encode(obj, path_keys) + '.txt')
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
        path = cls.get_local_path(data)
        logger.debug('write %s' % path)
        for k,v in data.items():
            logger.debug('     %09s %s' % (k, v))
        try:
            with open(path, format) as fout:
                cls.stats['writes'] += 1
                fout.write(body)
            os.utime(path, (data['timestamp'], data['timestamp']))
            if path in cls.file_cache:
                del cls.file_cache[path]
        except IOError as e:
            logger.error('Cannot add file. Path len = %d' % len(path))
            raise

    @classmethod
    def get_search_command(cls, query, days):
        # type (str,int) -> list
        if os.name == 'nt':
            local_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'localsearch')
            since = cls.get_year_month_day(days)
            return ['cscript', '/nologo', os.path.join(local_dir, 'search.vbs'), utils.HOME_DIR, query, since]
        elif os.name == 'posix':
            operator = '-interpret'
            since = 'modified:%s-%s' % (cls.get_day_month_year(days), cls.get_day_month_year(-1))
            return ['mdfind', '-onlyin', utils.HOME_DIR, operator, query, since]
        else:
            raise ValueError('Unsupported OS:', os.name)

    @classmethod
    def search(cls, query, days, operator='-interpret'):
        # type: (str,int,str) -> list
        assert isinstance(query, str)
        assert isinstance(days, int), 'unexpected type %s: %s' % (type(days), days)
        cls.stats = defaultdict(int)
        search_start = time.time()
        command = cls.get_search_command(query, days)
        paths = list(filter(None, cls.run_command(command)))
        logger.info('Run command "%s" ==> %d results' % (' '.join(command), len(paths)))
        for path in paths:
            logger.debug('   %s', path)
        resolve_start = time.time()
        query_words = query.split(' ')
        results = list(filter(lambda item: item and item.matches(query_words), map(cls.resolve_path, paths)))
        logger.debug('==> %d resolved items' % len(results))
        for n,item in enumerate(results):
            logger.debug('   %d %s', n, item.kind)
        cls.record_search_stats(query, len(paths), time.time() - search_start, len(results), time.time() - resolve_start)
        return results

    @classmethod
    def record_search_stats(cls, query,  search_count, search_duration, resolve_count, resolve_duration):
        cls.stats['searches'] += 1
        cls.stats['raw_results'] = search_count
        cls.stats['search_time'] += search_duration
        cls.stats['results'] = resolve_count
        cls.stats['resolve_time'] += resolve_duration
        cls.log_search_stats(query)

    @classmethod
    def log_search_stats(cls, query=None):
        logger.debug('Storage Statistics:')
        if query:
            logger.debug('    query: "%s"' % query)
        for k,v in cls.stats.items():
            logger.debug('    %s: %s' % (k, v))

    @classmethod
    def search_contact(cls, email):
        # type: (str) -> dict
        person = cls.search_cache.get(email)
        if not person:
            path = os.path.join(utils.HOME_DIR, 'items', 'contact', email)
            if os.path.exists(path):
                with open(path, 'r') as f:
                    cls.stats['contacts_read'] += 1
                    from importers import contact
                    try:
                        person = contact.deserialize(compressor.deserialize(f.read()))
                        person.path = person['path'] = path
                    except:
                        logger.error('Could not deserialize %s', path)
            else:
                logger.error('Contact not found: %s', path)
            cls.search_cache[email] = person
        return person

    @classmethod
    def search_file(cls, filename):
        # type: (str) -> list
        return cls.search(filename, operator='-name')

    @classmethod
    def load_item(cls, path):
        with open(path) as f:
            Storage.stats['items_read'] += 1
            try:
                obj = compressor.deserialize(f.read())
                obj['kind'] = path[len(utils.ITEMS_DIR) + 1:-4].split(os.path.sep)[0]
                return cls.to_item(obj, path)
            except:
                Storage.stats['files'] += 1
                return File(path)

    @classmethod
    def resolve_path(cls, path):
        # type: (str) -> (dict,None)
        if not path or not os.path.isfile(path):
            logger.info('skip non file: %s' % path[len(utils.HOME_DIR):])
            return None
        item = cls.file_cache.get(path)
        if not item:
            kind, *parts = path[len(utils.ITEMS_DIR) + 1:-4].split(os.path.sep)
            try:
                obj = compressor.decode(os.path.sep.join(parts))
            except Exception as e:
                item = cls.load_item(path)
                cls.file_cache[path] = item
            else:
                obj['kind'] = kind
                item = cls.to_item(obj, path)
        return item

    @classmethod
    def can_load_more(cls, kind):
        return settings['%s/can_load_more' % kind]

    @classmethod
    def can_delete(cls, kind):
        return settings['%s/count' % kind] > 0

    @classmethod
    def to_item(cls, obj, path):
        handler = item_handlers[obj['kind']]
        item = handler.deserialize(obj)
        item.path = item['path'] = path
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
        if not os.path.exists(utils.HOME_DIR):
            os.mkdir(utils.HOME_DIR)
            os.chmod(utils.HOME_DIR, stat.S_IEXEC)

    @classmethod
    def get_item_count(cls, kind):
        path = os.path.join(utils.HOME_DIR, 'items', kind)
        count = sum(len(files) for _,_,files in os.walk(path))
        return count

    @classmethod
    def load(cls, kind):
        if settings['%s/loading' % kind]:
            logger.info('Already loading %s' % kind)
            return
        logger.info('Load %s' % kind)
        try:
            settings['%s/loading' % kind] = True
            item_handlers[kind].load()
        except Exception as e:
            logger.error('Could not load %s: %s' % (kind, e))
        finally:
            settings['%s/loading' % kind] = False

    @classmethod
    def stop_loading(cls, kind):
        settings['%s/loading' % kind] = False

    @classmethod
    def loading(cls, kind):
        return settings['%s/loading' % kind]

    @classmethod
    def delete_all(cls, kind):
        if settings['%s/deleting' % kind]:
            logger.info('Already loading %s' % kind)
            return
        try:
            settings['%s/deleting' % kind] = True
            import_module('importers.%s' % kind).delete_all()
            cls.clear(kind)
        except Exception as e:
            logger.error('Could not stop delete all %s: %s' % (kind, e))
        finally:
            settings['%s/deleting' % kind] = False
            settings['%s/count' % kind] = 0

    @classmethod
    def stop_deleting(cls, kind):
        settings['%s/deleting' % kind] = False

    @classmethod
    def deleting(cls, kind):
        return settings['%s/deleting' % kind]

    @classmethod
    def refresh_status(cls):
        for kind in ITEM_KINDS:
            settings['%s/count'] = cls.get_item_count(kind)

    @classmethod
    def poll(cls):
        cls.refresh_status()

    @classmethod
    def get_status(cls):
        status = {}
        start = time.time()
        for kind in ITEM_KINDS:
            if time.time()-start>0.1: logger.info('%.1fs: getting status for %s' % (time.time() - start, kind))
            status[kind] = {
                'pending': settings['%s/pending' % kind],
                'loading': cls.loading(kind),
                'deleting': cls.deleting(kind),
                'count': settings['%s/count' % kind],
                'history': item_handlers[kind].get_status(),
            }
            start = time.time()
        return status

    @classmethod
    def clear(cls, kind):
        path = os.path.realpath(os.path.join(utils.HOME_DIR, 'items', kind))
        import tempfile
        import threading
        if os.path.exists(path) and path.startswith(utils.ITEMS_DIR):
            tmpdir = tempfile.mkdtemp()
            print('mv to tmpdir: ' + tmpdir)
            shutil.move(path, tmpdir)
            threading.Thread(target=lambda: shutil.rmtree(tmpdir)).start()
        time.sleep(0.5)
        logger.info('Cleared all data for "%s"' % path)


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
        self.border = 'none'
        self.zoomed_icon_size = 0
        self.image = ''
        self.words = []
        self.timestamp = 0
        self.related_items = []
        self.duplicate = False

        dict.update(self, vars(self))
        if obj:
            dict.update(self, obj)
            for k,v in obj.items():
                setattr(self, k, v)

    def __hash__(self):
        return hash(self.uid)

    def matches(self, query_words):
        return True

    def is_related_item(self, other):
        return other in self.related_items

    def get_related_items(self):
        return self.related_items

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.uid == other.uid

    def update(self, obj):
        obj['timestamp'] = self.timestamp

    def update_words(self, items):
        pass

    def add_related(self, other):
        self.related_items.append(other)

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

    def matches(self, query_words):
        for word in query_words:
            if not word in self.filename:
                return False
        return True

    def same_path(self, path):
        logger.debug('Same path?', self.path[:len(utils.FILE_DIR)], path)
        return self.path[:len(utils.FILE_DIR)] == path

    def set_message_id(self, path):
        self.message_id = os.path.basename(os.path.dirname(path))

    def update_words(self, items):
        for item in items:
            if item.kind == 'gmail' and item.message_id == self.message_id:
                self.words = item.words


item_handlers.update({
    kind: import_module('importers.%s' % kind) for kind in ITEM_KINDS
})
Storage.setup()

if __name__ == '__main__':
    if False:
        path = "/Users/laffra/IKKE/gmail/content_type/text-html/kind/gmail/label/activity aler ... n alert limit/message_id/<22f44d4d-ad5a-40f6-83dc-336b2b94294c@xtnvs5mta401.xt.local>/receivers/[/1/laffra@gmail.com/senders/[/1/onlinebanking@ealerts.bankofamerica.com/subject/Activity Alert: Electronic or Online Withdrawal Over Your Chosen Alert Limit/thread/activity aler ... n alert limit - ['laffra@gmail.com', 'onlinebanking@ealerts.bankofamerica.com']/timestamp/1510537596/uid/16455 (UID 92562 RFC822 {25744}.txt"
        for k,v in Storage.resolve_path(path).items():
            if v:
                logger.debug('%s=%s' % (k, v))

    if False:
        import cProfile
        cProfile.run('Storage.search("linkedin", days=10000)', sort="cumulative")

    if True:
        Storage.search('Rowan', days=1)

    if False:
        for kind in ['browser','file','gmail','contact']:
            logger.debug('%s: %d' % (kind, Storage.get_item_count(kind)))

    if False:
        for k,v in Storage.search_contact('messaging-digest-noreply@linkedin.com').items():
            if v:
                logger.info('%s=%s' % (k, v))



