import base64
from collections import Counter
from importers import contact
from importers import file
from importers import Importer
from importers import google_apis
import datetime
import email
import email.header
import email.utils
import htmlparser
import json
import logging
from preferences import ChromePreferences
from settings import settings
import os
import re
import stopwords
import storage
import time
import urllib
import utils
from urllib.parse import urlparse


MAXIMUM_THREAD_COUNT = 15
URL_MATCH_RE = re.compile(r'https?://[\w\d:#@%/;$()~_?\+-=\.&]*')
DATESTRING_RE = re.compile(' [-+].*')
CLEANUP_FILENAME_RE = re.compile('[<>@]')
MY_EMAIL_ADDRESS = ChromePreferences().get_email()
GMAIL_RETRY_DELAY = 30
MAX_RELATED_PERSON_COUNT = 11

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
gmail_service = google_apis.get_google_service("gmail", "v1")

class GMail(Importer):
    singleton = None

    def __init__(self):
        super().__init__()
        self.error = None
        self.inbox = None
        self.sent = None
        self.kind = "gmail"
        GMail.singleton = self

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
            if not filename:
                continue
            attachmentId = part["body"]["attachmentId"]
            attachment = gmail_service.users().messages().attachments().get(
                userId = "me",
                id = attachmentId,
                messageId = msg["id"]
            ).execute()

            data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
            if not data:
                continue
            file.save_file(msg['uid'], filename, timestamp, data)
            files.append(filename)
        return files

    @classmethod
    def get_body(cls, msg):
        payload = msg["payload"]
        if "parts" in payload:
            for part in msg["payload"]["parts"]:
                mime_type = part["mimeType"]
                if mime_type in ['text/plain', 'text/html']:
                    if "data" in part["body"]:
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

    def load_items(self, days_after, days_before):
        day = days_before
        while settings['gmail/loading'] and day < days_after:
            try:
                self.update_days(day)
                try:
                    query = "newer_than:{0}d older_than:{1}d".format(day + 1, day)
                    result = gmail_service.users().messages().list(userId="me", maxResults=1000, q=query).execute()
                    if "messages" in result:
                        logger.info("Load {0} => {1} messages".format(query, len(result["messages"])))
                        requests = [
                            gmail_service.users().messages().get(userId = 'me', id = msg_id['id'])
                            for msg_id in result["messages"]
                        ]
                        google_apis.batch(gmail_service, requests, self.parse_message)
                except urllib.error.URLError:
                    logger.info("Gmail service timed out. Trying again in %s seconds" % GMAIL_RETRY_DELAY)
                    time.sleep(GMAIL_RETRY_DELAY)
                    continue
                contact.cleanup()
                logger.debug('Processed %d inbox and %d sent messages for day %d' % (0, 0, day))
            except Exception as e:
                logger.error('Cannot load message for day %d: %s' % (day, e))
                import traceback
                traceback.print_exc()
                return
            else:
                day += 1

    def parse_message(self, request_id, msg, exception):
        if not settings["gmail/loading"]:
            return
        msg["payload"]["headers"] = self.parse_headers(msg["payload"])
        msg["uid"] = msg["id"]
        payload = msg['payload']
        headers = payload['headers']
        subject = self.decode_header(headers.get('Subject', msg.get("snippet", "")))
        timestamp = (headers['Date'] or int(msg.get("internalDate", "0"))) / 1000
        content_type, url_domains, body = self.get_body(msg)
        label, words, rest = self.parse_email_text(subject, body)
        who = headers.get('To') or headers.get('From')
        persons = self.get_persons(timestamp, who)
        emails = [person.email for person in persons]
        names = [person.name for person in persons]
        thread = '%s - %s' % (label, emails)
        files = self.save_attachments(msg, timestamp)
        kind = 'gmail'
        if "CHAT" in msg.get("labelIds", []):
            kind = 'hangouts'
        settings.increment('%s/count' % kind)
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
            'kind': kind,
            'timestamp': timestamp,
            'url_domains': url_domains,
            'files': files,
        })

    def parse_headers(self, part):
        headers = dict([
            (header["name"], header["value"])
            for header in part.get("headers", []) 
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
            for name, email_address in email.utils.getaddresses(filter(None, person_strings))
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
        return Importer.get_status("gmail", "email")


class GMailNode(storage.Data):
    def __init__(self, obj):
        super(GMailNode, self).__init__(obj.get('label', ''))
        self.uid = obj['uid']
        self.message_id = obj.get('message_id', '')
        self.color = 'darkred'
        self.names = obj.get('names', [])
        self.emails = obj.get('emails', [])
        self.timestamp = obj.get('timestamp', 0)
        self.persons = list(filter(None, [contact.find_contact(email, timestamp=self.timestamp) for email in self.emails]))
        self.in_reply_to = obj.get('in_reply_to', '')
        self.subject = obj.get('subject', '')
        self.rest = obj.get('rest', '')
        self.kind = obj.get('kind')
        self.icon = 'get?path=icons/gmail-icon.png'
        self.icon_size = 24
        self.font_size = 10
        self.zoomed_icon_size = 24
        self.thread = obj.get('thread')
        self.node_size = 1
        self.url_domains = obj.get('url_domains', [])
        self.files = list(filter(lambda file: not file.endswith(".ics"), obj.get('files', [])))
        self.label = self.label or ' '.join(self.words + [str(len(self.files))]) 
        self.words = self.label.split() or list(sorted(obj.get('words', []))) or self.subject.split() 
        self.connected = False
        dict.update(self, vars(self))

    def __hash__(self):
        return hash(self.uid)

    def is_related_item(self, other):
        if False and self.url_domains and other.kind == 'browser':
            related = other.domain == self.url_domains[0]
        elif other.kind == 'gmail':
            related = not self.connected and self.label == other.label
            self.connected = other.connected = True
        elif self.files and other.kind == 'file':
            related = other.filename in self.files
        elif self.persons and other.kind == 'contact':
            related = other in self.persons
        else:
            related = False
        logger.debug("related? %s %s %s %s" % (repr(self.label), self.files, repr(other.label), related))
        return related

    def get_related_items(self):
        files = [file.load_file(self.uid, filename) for filename in self.files]
        return super().get_related_items() + files + self.persons[:MAX_RELATED_PERSON_COUNT]

    def is_duplicate(self, duplicates):
        key = "gmail - %s" % ' '.join(sorted(word for word in self.words if not stopwords.is_stopword(word)))
        if key in duplicates:
            self.mark_duplicate()
            return True
        duplicates.add(key)
        return False


def _render(args):
    url = 'https://mail.google.com/mail/u/0/#search/rfc822msgid:%s' % args["message_id"]
    return '<script>document.location=\'%s\';</script>' % url


def render(args):
    import re
    words = args.get("query", "").split() + list(filter(lambda word: re.match("^[a-zA-Z]*$", word), args["subject"].split()))[:10]
    logger.info(args["subject"])
    logger.info(words)
    url = 'https://mail.google.com/mail/u/0/#search/%s' % urllib.parse.quote(' '.join(words))
    return '<script>document.location=\'%s\';</script>' % url

def load():
    GMail.singleton.load()

def poll():
    load()

def delete_all():
    pass


settings['gmail/can_load_more'] = True
settings['gmail/pending'] = 'gmail/username' not in settings

GMail.singleton = GMail()
get_status = GMail.get_status


def deserialize(obj):
    return GMailNode(obj)


def cleanup():
    pass

def test():
    global DAYS_LOAD
    global MAXIMUM_DAYS_LOAD
    logger.info("############### start")
    settings.clear()
    MAXIMUM_DAYS_LOAD = DAYS_LOAD = 1
    logger.info("############### load")
    load()
    logger.info("############### poll 1")
    poll()
    logger.info("############### poll 2")
    poll()
    logger.info("############### poll 3")
    poll()
    logger.info("############### done")

