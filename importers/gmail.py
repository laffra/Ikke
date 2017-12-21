from collections import Counter
from importers import contact
import datetime
import email
import email.header
import email.utils
import htmlparser
import imaplib
import logging
from settings import settings
import os
import re
import stopwords
import storage
import time
import traceback
import utils
from urllib.parse import urlparse


MAXIMUM_DAYS_LOAD = 3650
MAXIMUM_THREAD_COUNT = 15
URL_MATCH_RE = re.compile('https?://[\w\d:#@%/;$()~_?\+-=\.&]*')
DATESTRING_RE = re.compile(' [-+].*')

CLEANUP_FILENAME_RE = re.compile('[<>@]')

PATH_ATTRIBUTES = {
    'kind',
    'uid',
    'message_id',
    'senders',
    'ccs',
    'receivers',
    'thread',
    'subject',
    'label',
    'content_type',
    'timestamp',
}

class GMail():
    is_loading_items = False
    singleton = None
    messages_loaded = 0

    def __init__(self):
        self.mail_server = 'imap.googlemail.com'
        self.username = settings.get('gu')
        self.password = settings.get('gp')
        assert self.username, 'Google email not set in: %s' % settings
        self.error = None
        self.inbox = None
        self.sent = None

    def open_connection(self, folder):
        connection = imaplib.IMAP4_SSL(self.mail_server)
        connection.login(self.username, self.password)
        connection.select(folder, readonly=True)
        return connection

    def open_connections(self):
        self.inbox = self.open_connection('"[Gmail]/All Mail"')
        self.sent = self.open_connection('"[Gmail]/Sent Mail"')

    def close_connections(self):
        try:
            self.inbox.close()
            self.sent.close()
        except:
            pass

    def __enter__(self):
        self.open_connections()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connections()

    @classmethod
    def save_attachments(cls, msg, timestamp):
        files = []
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            disposition = part.get('Content-Disposition')
            if not disposition or not disposition.startswith('attachment;'):
                continue
            filename = part.get_filename()
            body = part.get_payload(decode=True)
            path = os.path.join(utils.cleanup_filename(msg['Message-ID']), utils.cleanup_filename(filename))
            if filename and body:
                storage.Storage.add_binary_data(
                    body,
                    {
                        'uid': path,
                        'kind': 'file',
                        'timestamp': timestamp,
                    })
                files.append(path)
                logging.debug('  ', path)
        return files

    @classmethod
    def get_body(cls, msg):
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type in ['text/plain', 'text/html']:
                body = part.get_payload(decode=True).decode('utf8', errors='ignore')
                url_domains = cls.get_top_domain_urls(body)
                if content_type == 'text/html':
                    body = htmlparser.get_text(body)
                return content_type, url_domains, body
        return '', [], ''

    @classmethod
    def get_top_domain_urls(cls, body):
        return list(set(map(cls.get_top_domain, re.findall(URL_MATCH_RE, body))))

    @classmethod
    def get_top_domain(cls, url):
        return '.'.join(urlparse(url).netloc.split('.')[-2:])

    @classmethod
    def load_messages(cls, count, start=0):
        if cls.is_loading_items:
            logging.info('Already loading items, skip request for %d-%d' % (start, count))
            return
        cls.is_loading_items = True
        try:
            logging.info('Loading gmail for the last %s days - %s days back' % (count, start))
            cls.messages_loaded = 0
            day = start
            reader = None
            while cls.is_loading_items and day < count:
                try:
                    if reader is None:
                        reader = GMail()
                    with reader:
                        inbox = reader.process_messages_for_day(reader.inbox, day)
                        sent = reader.process_messages_for_day(reader.sent, day)
                        contact.cleanup()
                        logging.info('Processed %d inbox and %d sent messages for day %d' % (
                            inbox or 0, sent or 0, day
                        ))
                        logging.debug(cls.history())
                except Exception as e:
                    logging.error('Cannot load message for day %d: %s' % (day, e))
                    import traceback
                    traceback.print_exc()
                    reader = None
                else:
                    settings['gmail/days'] = max(day, settings.get('gmail/days', 0))
                    day += 1
        finally:
            contact.cleanup()
            storage.Storage.log_search_stats()
            logging.info('Loaded %d messages in total' % cls.messages_loaded)
            cls.is_loading_items = False

    def process_messages_for_day(self, connection, day):
        query = '(since "%s" before "%s")' % (self.get_day_string_internal(day), self.get_day_string_internal(day - 1))
        logging.info('Get messages for day -%d: %s' % (day, query))
        message_ids = self.fetch_message_ids(connection, query)
        return self.parse_messages(connection, message_ids[-3:])

    def fetch_message_ids(self, connection, query):
        result, message_ids = connection.uid('search', None, query)
        if result == "OK" and message_ids[0]:
            return message_ids[0].decode("utf-8").split(' ')
        return []

    @classmethod
    def get_day_string(cls, day):
        return (datetime.date.today() - datetime.timedelta(days=day)).strftime("%Y/%m/%d")

    @classmethod
    def get_day_string_internal(cls, day):
        return (datetime.date.today() - datetime.timedelta(days=day)).strftime("%d-%b-%Y")

    def parse_messages(self, connection, message_ids):
        if not message_ids:
            return
        logging.debug('Parsing %d message ids' % len(message_ids))
        result, responses = connection.uid('fetch', ','.join(message_ids), '(RFC822)')
        if result == 'OK':
            responses = list(filter(lambda response: len(response) > 1, responses))
            for response in responses:
                try:
                    self.parse_message(part.decode('utf8', errors='ignore') for part in response)
                except Exception as e:
                    logging.error('Cannot handle response due to %s' % e)
                    logging.error('Response:', response)
                    traceback.print_exc()
                else:
                    GMail.messages_loaded += 1
            return len(responses)
        else:
            raise Exception(result)

    def decode_header(self, s):
        try:
            text, encoding = email.header.decode_header(s)[0]
            return text.decode('utf8', errors='ignore')
        except:
            return s

    def get_addresses(self, persons_string, timestamp):
        return [
            contact.find_contact(email_address.lower(), self.decode_header(name), timestamp=timestamp)['email']
            for name, email_address in email.utils.getaddresses(persons_string)
            if email_address
        ]

    def parse_message(self, response):
        uid, data = response
        msg = email.message_from_string(data)
        msg['uid'] = uid
        subject = self.decode_header(msg['Subject'])
        timestamp = self.get_timestamp(msg.get('Received', msg.get('Date')).split(';')[-1].strip())
        content_type, url_domains, body = self.get_body(msg)
        logging.debug('parsing message', type(subject), type(body))
        label, words, body = self.parse_email_text(subject, body)
        senders = self.get_addresses(msg.get_all('From', []), timestamp)
        receivers = self.get_addresses(msg.get_all('To', []), timestamp)
        ccs = self.get_addresses(msg.get_all('Cc', []), timestamp)
        persons = msg.get_all('From', []) + msg.get_all('To', []) + msg.get_all('Cc', [])
        emails = sorted(list(set(receivers + ccs + senders)))
        thread = '%s - %s' % (label, emails)
        files = self.save_attachments(msg, timestamp)
        storage.Storage.add_data({
            'uid': msg['uid'] or msg['Message-ID'],
            'message_id': msg['Message-ID'],
            'senders': senders,
            'ccs': ccs,
            'receivers': receivers,
            'persons': persons,
            'thread': thread,
            'subject': subject,
            'label': label,
            'words': words,
            'body': body,
            'content_type': content_type,
            'kind': 'gmail',
            'timestamp': timestamp,
            'url_domains': url_domains,
            'files': files,
        })
        logging.debug('Add message "%s"' % subject)

    @classmethod
    def parse_email_text(cls, subject, body):
        subject_words = stopwords.remove_stopwords(subject)
        label = ' '.join(subject_words)
        body_words = [word.lower() for word in stopwords.remove_stopwords(body)]
        top_body_words = [word for word,count in Counter(body_words).most_common(10)]
        words = list(set(subject_words + top_body_words))
        rest = ' '.join(set(body_words) - set(words))
        logging.debug('subj: "%s"' % subject_words)
        logging.debug('body: "%s"' % body_words)
        logging.debug('all: "%s"' % words)
        logging.debug('rest: "%s"' % rest)
        return label, words, rest

    @classmethod
    def get_timestamp(cls, datestring):
        datestring = re.sub(DATESTRING_RE, '', datestring)
        dt = datetime.datetime.strptime(datestring, '%a, %d %b %Y %H:%M:%S')
        return int(time.mktime(dt.timetuple()))

    @classmethod
    def history(cls):
        count = storage.Storage.get_item_count('gmail')
        if count > 0:
            days = settings.get('gmail/days', 0) + 1
            date = str((datetime.datetime.now() - datetime.timedelta(days=days)).date())
            return '%d gmail messages loaded up to %s days back to %s' % (count, days, date)
        return 'Nothing loaded yet.'

    @classmethod
    def load(cls, days_count=1, days_start=0):
        # type (int,bool) -> None
        if 'gl' not in settings:  # this is the very first load
            days_count = MAXIMUM_DAYS_LOAD
        settings['gl'] = time.time()
        cls.load_messages(days_count, days_start)
        storage.Storage.stats.clear()


class GMailNode(storage.Data):
    def __init__(self, obj):
        super(GMailNode, self).__init__(obj['label'])
        self.message_id = obj.get('message_id', '')
        self.uid = self.message_id
        self.color = 'black'
        self.senders = obj.get('senders', [])
        self.ccs = obj.get('ccs', [])
        self.receivers = obj.get('receivers', [])
        contacts = [storage.Storage.search_contact(email) for email in set(self.senders + self.receivers + self.ccs)]
        self.persons = list(filter(None, contacts))
        self.in_reply_to = obj.get('in_reply_to', '')
        self.subject = obj.get('subject', '')
        self.words = obj['words']
        self.kind = obj['kind']
        self.timestamp = obj['timestamp']
        self.icon = 'get?path=icons/gmail-icon.png'
        self.icon_size = 24
        self.font_size = 10
        self.zoomed_icon_size = 24
        self.thread = obj['thread']
        self.node_size = 1
        self.url_domains = obj['url_domains']
        self.files = obj['files']
        dict.update(self, vars(self))

    def __hash__(self):
        return hash(self.uid)

    def is_related_item(self, other):
        if self.url_domains and other.kind == 'browser':
            return GMail.get_top_domain(other.url) in self.url_domains
        if self.files and other.kind == 'file':
            return other.path[len(storage.FILE_DIR)+1:] in self.files
        if self.persons and other.kind == 'contact':
            return other in self.persons

    def get_related_items(self):
        return [storage.Storage.load_item('file', path) for path in self.files] + self.persons

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.uid == other.uid
        else:
            return False

    def is_duplicate(self, duplicates):
        if self.thread in duplicates:
            return True
        duplicates.add(self.thread)
        return False

    @classmethod
    def deserialize(cls, obj):
        return GMailNode(obj)

    @classmethod
    def render(cls, item, query):
        query = 'rfc822msgid:%s' % item.message_id
        url = 'https://mail.google.com/mail/mu/mp/485/?mui=ca#tl/search/%s' % query
        logging.info('render %s' % url)
        return '<script>document.location=\'%s\';</script>' % url


def can_load_more():
    return True


def delete_all():
    if storage.Storage.clear('gmail'):
        settings['gmail/days'] = 0


def load():
    days = settings.get('gmail/days', 0)
    GMail.load(days + 3650, days)


def stop_loading():
    GMail.is_loading_items = False


def is_loading():
    return GMail.is_loading_items


def poll():
    GMail.load(1, 0)


history = GMail.history

deserialize = GMailNode.deserialize
render = GMailNode.render


def cleanup():
    pass

if __name__ == '__main__':
    # logging.set_level(logging.DEBUG)
    # settings.clear()
    # load(1, 0, True)
    # load(3650, 0, True)
    #GMail.load(5, 0)
    # logging.info('History: %s' % history())
    # poll()
    gmail_dir = os.path.join(storage.ITEMS_DIR, 'gmail')
    for _,_,files in os.walk(gmail_dir):
        for n,filename in enumerate(files):
            path = os.path.join(gmail_dir, filename)
            obj = storage.Storage.resolve_path(path)
            if n%100 == 0:
                print(n, path)
            for person in obj.persons:
                person.timestamp = obj.timestamp
                person.save()

