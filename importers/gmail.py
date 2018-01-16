from collections import Counter
from importers import contact
from cache import Cache
import datetime
import email
import email.header
import email.utils
import htmlparser
import imaplib
import logging
from preferences import ChromePreferences
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
MY_EMAIL_ADDRESS = ChromePreferences().get_email()

keys = (
    'uid', 'message_id', 'senders', 'ccs', 'receivers', 'thread',
    'subject', 'label', 'content_type', 'timestamp',
    'emails', 'url_domains', 'files',
)
path_keys = (
    'label', 'uid', 'emails', 'files', 'url_domains', 'words'
)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GMail():
    singleton = None
    messages_loaded = 0
    id_cache = Cache(3600)

    def __init__(self):
        self.mail_server = 'imap.googlemail.com'
        self.username = settings['gmail/username']
        self.password = settings['gmail/password']
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
    def get_attachment_path(cls, uid, filename):
        return os.path.join(utils.cleanup_filename(uid), utils.cleanup_filename(filename))

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
            path = cls.get_attachment_path(msg['uid'], filename)
            if filename and body:
                storage.Storage.add_binary_data(
                    body,
                    {
                        'uid': path,
                        'kind': 'file',
                        'timestamp': timestamp,
                    })
                files.append(filename)
                settings.increment('file/count')
                logger.debug('Attachment: %s',  path)
        return files

    @classmethod
    def get_body(cls, msg):
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type in ['text/plain', 'text/html']:
                body = part.get_payload(decode=True).decode('utf8', errors='ignore')
                url_domains = cls.get_domain_urls(body)
                if content_type == 'text/html':
                    body = htmlparser.get_text(body)
                return content_type, url_domains, body
        return '', [], ''

    @classmethod
    def get_domain_urls(cls, body):
        return list(set(map(cls.get_domain, re.findall(URL_MATCH_RE, body))))

    @classmethod
    def get_domain(cls, url):
        return urlparse(url).netloc

    @classmethod
    def load_messages(cls, count, start=0):
        try:
            logger.info('Loading gmail for the last %s days - %s days back' % (count, start))
            cls.messages_loaded = 0
            day = start
            reader = None
            while settings['gmail/loading'] and day < count:
                try:
                    if reader is None:
                        reader = GMail()
                    with reader:
                        inbox = reader.process_messages_for_day(reader.inbox, day)
                        sent = reader.process_messages_for_day(reader.sent, day)
                        contact.cleanup()
                        logger.debug('Processed %d inbox and %d sent messages for day %d' % (
                            inbox or 0, sent or 0, day
                        ))
                        logger.info(cls.get_status())
                except Exception as e:
                    logger.error('Cannot load message for day %d: %s' % (day, e))
                    import traceback
                    traceback.print_exc()
                    reader = None
                else:
                    settings['gmail/days'] = max(day, settings['gmail/days'])
                    day += 1
        finally:
            contact.cleanup()
            storage.Storage.log_search_stats()
            logger.info('Loaded %d messages in total' % cls.messages_loaded)

    def process_messages_for_day(self, connection, day):
        query = '(since "%s" before "%s")' % (self.get_day_string_internal(day), self.get_day_string_internal(day - 1))
        logger.debug('Get messages for day -%d: %s' % (day, query))
        message_ids = self.fetch_message_ids(connection, query)
        return self.parse_messages(connection, [msg_id for msg_id in message_ids if msg_id not in self.id_cache])

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
        logger.debug('Parsing %d message ids' % len(message_ids))
        logger.debug('Cache size = %d' % len(self.id_cache))
        result, responses = connection.uid('fetch', ','.join(message_ids), '(RFC822)')
        if result == 'OK':
            responses = list(filter(lambda response: len(response) > 1, responses))
            for n,response in enumerate(responses):
                self.id_cache[message_ids[n]] = True
                try:
                    self.parse_message(
                        [part.decode('utf8', errors='ignore') for part in response],
                        sent=connection == self.sent
                    )
                except Exception as e:
                    logger.error('Cannot handle response due to %s' % e)
                    logger.error('Response: %s', response)
                    logger.error(traceback.format_exc())
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

    def get_persons(self, timestamp, *person_strings):
        return [
            contact.find_contact(email_address.lower(), self.decode_header(name), timestamp=timestamp)
            for name, email_address in email.utils.getaddresses(person_strings)
            if email_address
        ]

    def parse_message(self, response, sent):
        uid, data = response
        msg = email.message_from_string(data)
        msg['uid'] = uid
        subject = self.decode_header(msg['Subject'])
        timestamp = self.get_timestamp(msg.get('Received', msg.get('Date')).split(';')[-1].strip())
        content_type, url_domains, body = self.get_body(msg)
        label, words, rest = self.parse_email_text(subject, body)
        who = msg.get('To') if sent else msg.get('From')
        persons = self.get_persons(timestamp, who)
        emails = [person.email for person in persons]
        names = [person.name for person in persons]
        thread = '%s - %s' % (label, emails)
        files = self.save_attachments(msg, timestamp)
        logger.debug('Add %s: %s', msg['uid'], subject)
        settings.increment('gmail/count')
        storage.Storage.add_data({
            'uid': msg['uid'] or msg['Message-ID'],
            'message_id': msg['Message-ID'],
            'names': names,
            'emails': emails,
            'thread': thread,
            'subject': subject,
            'label': label,
            'words': words,
            'rest': rest,
            'content_type': content_type,
            'kind': 'gmail',
            'timestamp': timestamp,
            'url_domains': url_domains,
            'files': files,
        })

    @classmethod
    def parse_email_text(cls, subject, body):
        subject_words = stopwords.remove_stopwords(subject)
        label = ' '.join(subject_words)
        body_words = [word.lower() for word in stopwords.remove_stopwords(body)]
        top_body_words = [word for word,count in Counter(body_words).most_common(10)]
        words = list(set(subject_words + top_body_words))
        rest = ' '.join(set(body_words) - set(words))
        logger.debug('subj: "%s"' % subject_words)
        logger.debug('body: "%s"' % body_words)
        logger.debug('all: "%s"' % words)
        logger.debug('rest: "%s"' % rest)
        return label, words, rest

    @classmethod
    def get_timestamp(cls, datestring):
        datestring = re.sub(DATESTRING_RE, '', datestring)
        dt = datetime.datetime.strptime(datestring, '%a, %d %b %Y %H:%M:%S')
        return int(time.mktime(dt.timetuple()))

    @classmethod
    def get_status(cls):
        count = settings['gmail/count']
        days = settings['gmail/days']
        date = str((datetime.datetime.now() - datetime.timedelta(days=days + 1)).date())
        return '%d gmail messages loaded up to %s days back to %s' % (count, days, date)

    @classmethod
    def load(cls, days_count=1, days_start=0):
        # type (int,bool) -> None
        if 'gmail/lastload' not in settings:  # this is the very first load
            days_count = MAXIMUM_DAYS_LOAD
        settings['gmail/lastload'] = time.time()
        settings['gmail/loading'] = True
        cls.load_messages(days_count, days_start)
        storage.Storage.stats.clear()


class GMailNode(storage.Data):
    def __init__(self, obj):
        super(GMailNode, self).__init__(obj.get('label', ''))
        self.uid = obj['uid']
        self.message_id = obj.get('message_id', '')
        self.color = 'black'
        self.names = obj.get('names', [])
        self.emails = obj.get('emails', [])
        self.persons = list(filter(None, [contact.find_contact(email) for email in self.emails]))
        self.in_reply_to = obj.get('in_reply_to', '')
        self.subject = obj.get('subject', '')
        self.words = obj.get('words', [])
        self.rest = obj.get('rest', '')
        self.kind = obj.get('kind')
        self.timestamp = obj.get('timestamp')
        self.icon = 'get?path=icons/gmail-icon.png'
        self.icon_size = 24
        self.font_size = 10
        self.zoomed_icon_size = 24
        self.thread = obj.get('thread')
        self.node_size = 1
        self.url_domains = obj.get('url_domains', [])
        self.files = obj.get('files', [])
        self.fingerprint = '%s-%s' % (
            self.label,
            '-'.join(person['uid'] for person in self.persons if not person['email'] == MY_EMAIL_ADDRESS)
        )
        self.fingerprint = self.label
        self.connected = False
        dict.update(self, vars(self))

    def __hash__(self):
        return hash(self.uid)

    def is_related_item(self, other):
        if self.url_domains and other.kind == 'browser':
            related = other.domain == self.url_domains[0]
            self.keep = True
        elif other.kind == 'gmail':
            related = not self.connected and self.label == other.label
            self.connected = other.connected = True
        elif self.files and other.kind == 'file':
            related = other.filename == self.files[0]
        elif self.persons and other.kind == 'contact':
            related = other == self.persons[0]
        else:
            related = False
        return related

    def get_related_items(self):
        dir = os.path.join(utils.ITEMS_DIR, 'file', utils.cleanup_filename(self.uid))
        files = [
            storage.Storage.load_item(os.path.join(dir, path))
            for path in self.files
            if os.path.exists(os.path.join(dir, path))
        ]
        return super(GMailNode, self).get_related_items() + files + self.persons

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.uid == other.uid
        else:
            return False

    def is_duplicate(self, duplicates):
        if self.fingerprint in duplicates:
            self.duplicate = True
            return True
        logger.debug('Duplicate: %s' % self.fingerprint)
        duplicates.add(self.fingerprint)
        return False

    @classmethod
    def deserialize(cls, obj):
        try:
            return GMailNode(obj)
        except Exception as e:
            logger.error('Cannot deserialize:', e)
            for k,v in obj.items():
                logger.error('   ', k, ':', type(v), v)
            raise

    def render(self, query):
        url = 'https://mail.google.com/mail/mu/mp/485/?mui=ca#tl/search/rfc822msgid:%s' % self.message_id
        return '<html><a href="%s">view in gmail</a>' % url


def delete_all():
    settings['gmail/days'] = 0


def load():
    days = settings['gmail/days']
    GMail.load(days + 3650, days)


def poll():
    GMail.load(1, 0)


settings['gmail/can_load_more'] = True
settings['gmail/pending'] = 'gmail/username' not in settings

get_status = GMail.get_status

deserialize = GMailNode.deserialize


def cleanup():
    pass

if __name__ == '__main__':
    # settings.clear()
    # load(1, 0, True)
    # load(3650, 0, True)
    GMail.load(8, 7)
    # logging.info('History: %s' % history())
    # poll()

