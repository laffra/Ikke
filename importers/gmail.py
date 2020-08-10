import base64
from collections import Counter
from importers import contact
from cache import Cache
import datetime
import email
import email.header
import email.utils
import htmlparser
import imaplib
import json
import logging
from preferences import ChromePreferences
from settings import settings
import os
import pickle
import re
import stopwords
import storage
import time
import traceback
import utils
from urllib.parse import urlparse
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


MAXIMUM_DAYS_LOAD = 3650
MAXIMUM_THREAD_COUNT = 15
URL_MATCH_RE = re.compile('https?://[\w\d:#@%/;$()~_?\+-=\.&]*')
DATESTRING_RE = re.compile(' [-+].*')
CLEANUP_FILENAME_RE = re.compile('[<>@]')
MY_EMAIL_ADDRESS = ChromePreferences().get_email()
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

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

def get_gmail_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('importers/gmail_credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

service = get_gmail_service()


class GMail():
    singleton = None
    messages_loaded = 0
    id_cache = Cache(3600)

    def __init__(self):
        self.error = None
        self.inbox = None
        self.sent = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def get_attachment_path(self, uid, filename):
        return os.path.join(utils.cleanup_filename(uid), utils.cleanup_filename(filename))

    def save_attachments(self, msg, timestamp):
        files = []
        if not 'parts' in msg['payload']:
            return []
        for part in msg["payload"]["parts"]:
            if part["mimeType"] == 'multipart':
                continue
            headers = self.parse_headers(part)
            disposition = headers.get('Content-Disposition')
            if not disposition or not disposition.startswith('attachment;'):
                continue
            filename = part["filename"]
            attachmentId = part["body"]["attachmentId"]
            attachment = service.users().messages().attachments().get(
                userId = "me",
                id = attachmentId,
                messageId = msg["id"]
            ).execute()

            file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
            path = self.get_attachment_path(msg['uid'], filename)
            if filename and file_data:
                storage.Storage.add_binary_data(
                    file_data,
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
        payload = msg["payload"]
        if "parts" in payload:
            for part in msg["payload"]["parts"]:
                mime_type = part["mimeType"]
                if mime_type in ['text/plain', 'text/html']:
                    data = part['body']['data'].encode('UTF8')
                    return cls.parse_body(mime_type, data)
        body = payload['body']
        if body['size'] == 0:
            return '', [], ''
        mime_type = payload["mimeType"]
        data = body['data'].encode('UTF8')
        return cls.parse_body(mime_type, data)

    @classmethod
    def dump(cls, obj):
        with open("t.txt", "w") as fout:
            fout.write(json.dumps(obj, indent=4))

    @classmethod
    def parse_body(cls, mime_type, data):
        body = str(base64.urlsafe_b64decode(data), "UTF8")
        url_domains = cls.get_domain_urls(body)
        if mime_type == 'text/html':
            body = htmlparser.get_text(body)
        return mime_type, url_domains, body

    @classmethod
    def get_domain_urls(cls, body):
        return list(set(map(cls.get_domain, re.findall(URL_MATCH_RE, body))))

    @classmethod
    def get_domain(cls, url):
        return urlparse(url).netloc

    @classmethod
    def load_messages(cls, count, start=0):
        try:
            logger.info('Loading gmail for the 1ast %s days - %s days back' % (count, start))
            cls.messages_loaded = 0

            day = start
            reader = GMail()
            while settings['gmail/loading'] and day < count:
                try:
                    before = datetime.date.today() - datetime.timedelta(day)
                    after = before - datetime.timedelta(1)
                    query = "before: {0} after: {1}".format(before.strftime('%Y/%m/%d'), after.strftime('%Y/%m/%d'))
                    result = service.users().messages().list(userId="me", maxResults=1000, q=query).execute()
                    logger.info("Load {0} => {1}".format(query, len(result["messages"])))
                    for message in result["messages"]:
                        response = service.users().messages().get(userId="me", id=message["id"], format='full').execute()
                        reader.parse_message(response)
                    contact.cleanup()
                    logger.debug('Processed %d inbox and %d sent messages for day %d' % (0, 0, day))
                    logger.info(cls.get_status())
                except Exception as e:
                    logger.error('Cannot load message for day %d: %s' % (day, e))
                    import traceback
                    traceback.print_exc()
                    return
                else:
                    settings['gmail/days'] = max(day, settings['gmail/days'])
                    day += 1
        finally:
            contact.cleanup()
            storage.Storage.log_search_stats()
            logger.info('Loaded %d messages in total' % cls.messages_loaded)

    def parse_message(self, msg):
        msg["payload"]["headers"] = self.parse_headers(msg["payload"])
        msg["uid"] = msg["id"]
        payload = msg['payload']
        headers = payload['headers']
        subject = self.decode_header(headers.get('Subject', msg.get("snippet", "")))
        timestamp = headers['Date']
        content_type, url_domains, body = self.get_body(msg)
        label, words, rest = self.parse_email_text(subject, body)
        who = headers.get('To') or headers.get('From')
        persons = self.get_persons(timestamp, who)
        emails = [person.email for person in persons]
        names = [person.name for person in persons]
        thread = '%s - %s' % (label, emails)
        files = self.save_attachments(msg, timestamp)
        logger.debug('Add %s: %s', msg['uid'], subject)
        settings.increment('gmail/count')
        storage.Storage.add_data({
            'uid': msg['uid'] or msg['Message-ID'],
            'message_id': headers.get('Message-ID', msg['uid']),
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

    def parse_headers(self, part):
        headers = dict([
            (header["name"], header["value"])
            for header in part["headers"] 
        ])
        headers["Date"] = part.get("internalDate", 0)
        return headers

    def decode_header(self, s):
        try:
            text, encoding = email.header.decode_header(s)[0]
            return text.decode('utf8', errors='ignore')
        except:
            return s

    def get_persons(self, timestamp, *person_strings):
        return [
            contact.find_contact(email_address.lower(), self.decode_header(name), timestamp=timestamp)
            for name, email_address in email.utils.getaddresses(person_strings)
            if email_address
        ]

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
    GMail.load(days + 365, days)


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

