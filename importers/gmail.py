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
from threadpool import ThreadPool
import time
import traceback

import sys
if sys.version_info >= (3,):
    import urllib.parse as urlparse
else:
    from urlparse import urlparse


MAXIMUM_DAYS_LOAD = 3650
MAXIMUM_THREAD_COUNT = 15
URL_MATCH_RE = re.compile('href=[\'"]((https?):((//)|(\\\\))+([\w\d:#@%/;$()~_?\+-=\\\.&](#!)?)*)')
DATESTRING_RE = re.compile(' [-+].*')


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
    loading_items = False
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
    def save_urls(cls, body, title, words, timestamp):
        for url in set(match[0] for match in re.findall(URL_MATCH_RE, body)):
            domain = urlparse(url).netloc
            storage.Storage.add_data({
                'kind': 'browser',
                'title': title,
                'label': domain,
                'domain': domain,
                'image': '',
                'timestamp': timestamp,
                'url': url,
                'uid': url,
                'words': words,
            })

    @classmethod
    def save_attachments(cls, msg, description, timestamp):
        count = 0
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            disposition = part.get('Content-Disposition')
            if not disposition or not disposition.startswith('attachment;'):
                continue
            filename = part.get_filename()
            body = part.get_payload(decode=True)
            if filename and body:
                storage.Storage.add_binary_data(
                    body,
                    {
                        'uid': os.path.join(msg['Message-ID'], filename),
                        'kind': 'file',
                        'timestamp': timestamp,
                    })
                count += 1
        return count

    @classmethod
    def get_body(cls, msg):
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                html = part.get_payload(decode=True).decode(errors='ignore')
                return part.get_content_type(), htmlparser.get_text(html)
        for part in msg.walk():
            if part.get_content_maintype() == 'text/plain':
                return part.get_content_type(), part.get_payload(decode=True).decode(errors='ignore')
        return '', ''

    @classmethod
    def load_messages(cls, count, start=0):
        day = start
        reader = None
        while cls.loading_items and day < count:
            try:
                if reader is None:
                    reader = GMail()
                with reader:
                    inbox = reader.process_messages_for_day(reader.inbox, day)
                    sent = reader.process_messages_for_day(reader.sent, day)
                    contact.cleanup()
                    logging.info('Processed %d inbox and %d sent messages for day %d' % (inbox or 0, sent or 0, day))
                    logging.info(cls.history())
            except Exception as e:
                logging.error('Cannot load message for day %d: %s' % (day, e))
                reader = None
            else:
                settings['gc'] = max(day, settings.get('gc', 0))
                day += 1

    def process_messages_for_day(self, connection, day):
        query = '(since "%s" before "%s")' % (self.get_day_string_internal(day), self.get_day_string_internal(day - 1))
        logging.debug('Get messages for day -%d: %s' % (day, query))
        return self.parse_messages(connection, self.fetch_message_ids(connection, query))

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
            responses = filter(lambda response: len(response) > 1, responses)
            for response in responses:
                try:
                    self.parse_message(response)
                    GMail.messages_loaded += 1
                except Exception as e:
                    logging.error('Cannot handle response due to %s' % e)
                    traceback.print_exc()
            return len(responses)
        else:
            raise Exception(result)

    def parse_utf8(self, s):
        return s.replace('=?utf-8?q?', '').replace('?=', '')

    def get_addresses(self, persons_string, timestamp):
        return [
            contact.find_contact(email_address.lower(), self.parse_utf8(name), timestamp=timestamp)['email']
            for name, email_address in email.utils.getaddresses(persons_string)
            if email_address
        ]

    def parse_message(self, response):
        uid, data = response
        try:
            msg = email.message_from_bytes(data)
        except:
            msg = email.message_from_string(data)
        msg['uid'] = uid.decode()
        subject = str(email.header.make_header(email.header.decode_header(msg['Subject'].encode('utf8'))))
        timestamp = self.get_timestamp(msg.get('Received', msg.get('Date')).split(';')[-1].strip())
        content_type, body = self.get_body(msg)
        label, words, body = self.parse_email_text(subject, body)
        senders = self.get_addresses(msg.get_all('From', []), timestamp)
        receivers = self.get_addresses(msg.get_all('To', []), timestamp)
        ccs = self.get_addresses(msg.get_all('Cc', []), timestamp)
        emails = sorted(list(set(receivers + ccs + senders)))
        thread = '%s - %s' % (label, emails)
        storage.Storage.add_data({
            'uid': msg['uid'] or msg['Message-ID'],
            'message_id': msg['Message-ID'],
            'senders': senders,
            'ccs': ccs,
            'receivers': receivers,
            'thread': thread,
            'subject': subject,
            'label': label,
            'words': words,
            'body': body,
            'content_type': content_type,
            'kind': 'gmail',
            'timestamp': timestamp,
        })
        self.save_attachments(msg, subject, timestamp)
        self.save_urls(body, subject, words, timestamp)
        logging.debug('Add message "%s"' % subject)

    @classmethod
    def parse_email_text(cls, subject, body):
        subject_words = stopwords.remove_stopwords(subject)
        label = ' '.join(subject_words)
        body_words = [word.encode('utf8').lower() for word in stopwords.remove_stopwords(body)]
        top_body_words = [word for word,count in Counter(body_words).most_common(10)]
        words = list(set(subject_words + top_body_words))
        rest = ' '.join(set(body_words) - set(words))
        if len(label) > 31:
            label = label[:13] + ' ... ' + label[-13:]
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
        days = settings.get('gc', 0) + 1
        date = str((datetime.datetime.now() - datetime.timedelta(days=days)).date())
        history = 'Gmail messages loaded %s days back to %s' % (days, date)
        if cls.loading_items:
            history += '. Loading more items...'
        return history

    @classmethod
    def load(cls, days_count=1, days_start=0, force=False):
        # type (int,bool) -> None
        logging.info('Loading gmail for the last %s - %s days' % (days_start, days_count))
        cls.messages_loaded = 0
        if force:
            settings['gl'] = time.time()
        elif not settings.get('gl', 0):
            days_count = MAXIMUM_DAYS_LOAD
        settings['gl'] = time.time()

        cls.load_messages(days_count, days_start)
        contact.cleanup()
        logging.info('Loaded %d messages in total' % cls.messages_loaded)
        storage.Storage.log_search_stats()
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
        dict.update(self, vars(self))

    def __hash__(self):
        return hash(self.uid)

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


def load():
    days = settings.get('gc', 0)
    GMail.loading_items = True
    GMail.load(days + 3650, days)


def stop_loading():
    GMail.loading_items = False

poll = GMail.load
history = GMail.history

deserialize = GMailNode.deserialize
render = GMailNode.render


def cleanup():
    pass


if __name__ == '__main__':
    # settings.clear()
    # load(1, 0, True)
    # load(3650, 0, True)
    settings['gc'] = 365
    GMail.load(1, 0, True)
    logging.info('History: %s' % history())
    # poll()
