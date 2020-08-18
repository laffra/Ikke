import json
import logging
import os
from settings import settings
import stopwords
import storage
import urllib
import utils


keys = ('uid', 'timestamp')
path_keys = ('label', 'uid', 'icon', 'image', 'words')
logger = logging.getLogger(__name__)

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

def deserialize(obj):
    return FileItem(obj['path'])


def get_status():
    return '%d files were loaded as attachments for gmail messages' % settings['file/count']


def delete_all():
    pass


def poll():
    pass


def can_load_more():
    return False


def load():
    pass


def save_file(uid, filename, timestamp, data):
    logger.debug('create_file %s - %s - %s - %d bytes' % (uid, filename, timestamp, len(data)))
    save_metadata(uid, filename, timestamp, data)
    save_binary_data(uid, filename, timestamp, data)


def save_metadata(uid, filename, timestamp, data):
    metadata = {
        'kind': 'file',
        'uid': uid,
        'filename': filename,
        'label': filename,
        'words': stopwords.remove_stopwords(filename.replace('+', ' ')),
        'label': filename,
        'timestamp': timestamp or utils.get_timestamp()
    }
    storage.Storage.add_data(metadata)
    write(os.path.join(utils.FILE_DIR, uid, "%s.json" % filename), "w", json.dumps(metadata, indent=4))
    settings.increment('file/count')


def load_file(uid, filename):
    with open(os.path.join(utils.FILE_DIR, uid, "%s.json" % filename)) as fin:
        return FileItem(json.load(fin))


def get_icon(path):
    extension = os.path.splitext(path)[1][1:].lower()
    icon = FILE_FORMAT_ICONS.get(extension)
    route = 'get' if icon else 'get_image'
    return '%s?path=%s' % (route, icon or urllib.parse.quote(path))


def save_binary_data(uid, filename, timestamp, data):
    write(os.path.join(utils.FILE_DIR, uid, filename), "wb", data)


def write(path, format, data):
    dir = os.path.dirname(path)
    if not os.path.exists(dir):
        os.makedirs(os.path.dirname(path))
    with open(path, format) as fout:
        fout.write(data)


def render(args):
    path = os.path.join(utils.FILE_DIR, args["uid"], args["filename"])
    return '''
        <button onclick="loadFile()">open file</button>
        <script>
            function loadFile() {
                var xhttp = new XMLHttpRequest();
                xhttp.open("GET", "/open?path=%s", true);
                xhttp.send();
            }
        </script>
        ''' % urllib.parse.quote(path)



class FileItem(storage.Data):
    def __init__(self, obj):
        super(FileItem, self).__init__(obj['label'])
        self.kind = 'file'
        self.color = 'blue'
        self.uid = obj['uid']
        self.label = obj['label']
        self.timestamp = obj['timestamp']
        self.words = obj['words']
        self.filename = obj['filename']
        self.path = os.path.join(obj["uid"], obj["filename"])
        self.icon = get_icon(self.path)
        self.icon_size = 44
        self.zoomed_icon_size = 156
        dict.update(self, vars(self))

    def __eq__(self, other):
        return self.kind == other.kind and self.path == other.path

    def __hash__(self):
        return hash(self.path)

    def __repr__(self):
        return '<File {}>'.format(self.path)
