from importers import contact
from importers import browser
import datetime
import email
import email.utils
import htmlparser
import imaplib
from settings import settings
import re
import stopwords
import storage
import time
import traceback

import sys
if sys.version_info >= (3,):
    import urllib.parse as urlparse
else:
    from urlparse import urlparse


MAXIMUM_DAYS_LOAD = 3650

URL_MATCH_RE = re.compile('href=[\'"]((https?):((//)|(\\\\))+([\w\d:#@%/;$()~_?\+-=\\\.&](#!)?)*)')

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
    loading = False
    singleton = None

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
        self.inbox = self.open_connection('INBOX')
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
                        'uid': filename,
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

    def process_messages(self, days_count):
        for day in range(days_count):
            self.process_messages_for_day(self.sent, day)
            self.process_messages_for_day(self.inbox, day)

    def process_messages_for_day(self, connection, day):
        query = '(since "%s" before "%s")' % (self.get_day_string_internal(day), self.get_day_string_internal(day - 1))
        print('GMAIL: Get messages %d %s' % (day, query))
        self.parse_messages(connection, self.fetch_message_ids(connection, query))
        contact.cleanup()

    def fetch_message_ids(self, connection, query):
        result, message_ids = connection.uid('search', None, query)
        if result == "OK" and message_ids[0]:
            return message_ids[0].decode("utf-8").split(' ')
        else:
            print('GMAIL: Bad query', result, repr(query))
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
        result, responses = connection.uid('fetch', ','.join(message_ids), '(RFC822)')
        if result == 'OK':
            responses = filter(lambda response: len(response) > 1, responses)
            for response in responses:
                try:
                    self.parse_message(response)
                except Exception as e:
                    print('GMAIL: Cannot handle response due to %s' % e)
                    traceback.print_exc()
        else:
            raise Exception(result)

    def get_addresses(self, persons_string, timestamp):
        return [
            contact.find_contact(email.lower(), name, timestamp=timestamp)['email']
            for name, email in email.utils.getaddresses(persons_string)
            if email
        ]

    def parse_message(self, response):
        uid, data = response
        try:
            msg = email.message_from_bytes(data)
        except:
            msg = email.message_from_string(data)
        msg['uid'] = uid.decode()
        subject = str(email.header.make_header(email.header.decode_header(msg['Subject'])))
        timestamp = self.get_timestamp(msg.get('Received', msg.get('Date')).split(';')[-1].strip())
        label, words = self.get_label_and_words(subject)
        content_type, body = self.get_body(msg)
        senders = self.get_addresses(msg.get_all('From', []), timestamp)
        receivers = self.get_addresses(msg.get_all('To', []), timestamp)
        ccs = self.get_addresses(msg.get_all('Cc', []), timestamp)
        emails = sorted(list(set(receivers + ccs + senders)))
        thread = '%s - %s' % (label, emails)
        storage.Storage.add_data({
            'uid': msg['uid'],
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
        # for k,v in msg.items(): print(k, repr(v).replace('\n',' '))
        # print('-'*120)

    @classmethod
    def get_label_and_words(cls, subject):
        words = stopwords.remove_stopwords(subject)
        label = ' '.join(words)
        if len(label) > 31:
            label = label[:13] + ' ... ' + label[-13:]
        return label, words

    @classmethod
    def get_timestamp(cls, datestring):
        try:
            dt = datetime.datetime.strptime(datestring[:-6], '%a, %d %b %Y %H:%M:%S %z')
        except:
            try:
                dt = datetime.datetime.strptime(datestring[:-6], '%a, %d %b %Y %H:%M:%S +0000')
            except:
                dt = datetime.datetime.strptime(datestring[:-6], '%a, %d %b %Y %H:%M:%S')
        return int(time.mktime(dt.timetuple()))

    @classmethod
    def load(cls, days_count=1, force=False):
        # type (int,bool) -> None
        if force:
            settings['gl'] = time.time()
        elif not settings.get('gl', 0):
            days_count = MAXIMUM_DAYS_LOAD
        settings['gl'] = time.time()

        # TODO: only fetch messages not yet received
        cls.singleton = cls.singleton or cls()
        with cls.singleton as reader:
            reader.process_messages(days_count)
        print('GMAIL: loaded %d days' % days_count, storage.Storage.stats)
        storage.Storage.stats.clear()
        contact.cleanup()
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
        self.words = self.subject.split(' ')
        self.kind = obj['kind']
        self.timestamp = obj['timestamp']
        self.icon = 'get?path=icons/gmail-icon.png'
        self.icon_size = 24
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
        return '<script>document.location=\'%s\';</script>' % url


load = GMail.load
poll = GMail.load

deserialize = GMailNode.deserialize
render = GMailNode.render


def cleanup():
    pass


if __name__ == '__main__':
    # settings.clear()
    # load(1, True)
    load(3650, True)
    # load('Error', True)
    # poll()
