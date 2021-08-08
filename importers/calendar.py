from importers import contact
from importers import google_apis
from importers import Importer
from settings import settings

import datetime
import dateparser
import logging
import stopwords
import storage

logger = logging.getLogger(__name__)
service = google_apis.get_google_service("calendar", "v3")


class Calendar(Importer):
    singleton = None

    def __init__(self):
        super().__init__()
        self.kind = "calendar"
        self.error = None
        Calendar.singleton = self

    @classmethod
    def get_body(cls, event):
        return event

    def load_items(self, days_after, days_before):
        day = days_before
        while settings['calendar/loading'] and day < days_after:
            try:
                self.update_days(day)
                before = datetime.datetime.utcnow() + datetime.timedelta(days=1) - datetime.timedelta(days=day)
                after = before - datetime.timedelta(days=2)
                result = service.events().list(
                    calendarId='primary',
                    timeMin=after.isoformat() + "Z",
                    timeMax=before.isoformat() + "Z"
                ).execute()
                logger.info('Loading calendar events before %s after %s => %d items' % (before, after, len(result.get('items',[]))))
                self.parse_events(result.get('items', []))
            except Exception as e:
                logger.error('Cannot load message for day %d: %s' % (day, e))
                import traceback
                traceback.print_exc()
                return
            else:
                day += 1

    def get_names(self, event):
        return list(set([attendee["email"] for attendee in event.get("attendees", [])] + [event["organizer"]["email"]]))

    def parse_events(self, events):
        for event in events:
            import json
            start = event.get("start")
            if not start or not "dateTime" in start:
                continue
            when = dateparser.parse(start["dateTime"])
            timestamp = when.timestamp()
            names = self.get_names(event)
            for email_address in names:
                contact.find_contact(email_address.lower(), "", timestamp=timestamp)
            storage.Storage.add_data({
                "kind": "calendar",
                "uid": event["id"],
                "label": event.get("summary", ""),
                "description": event.get("description", ""),
                "words": stopwords.remove_stopwords("%s %s" % (event.get("summary", ""), event.get("description", ""))),
                "names": names,
                "url": event["htmlLink"],
                "start": start["dateTime"],
                "end": event["end"]["dateTime"],
                "timestamp": timestamp,
                "hangout": event.get("hangoutLink", "")
            })
            settings['calendar/count'] += 1
        contact.cleanup()

    @classmethod
    def get_status(cls):
        return Importer.get_status("calendar", "event")


class CalendarNode(storage.Data):
    def __init__(self, obj):
        super(CalendarNode, self).__init__(obj.get('label', ''))
        self.kind = 'calendar'
        self.uid = obj['uid']
        self.description = obj.get('message_id', '')
        self.color = 'blue'
        self.timestamp = obj.get('timestamp')
        self.icon = 'get?path=icons/calendar-icon.png'
        self.icon_size = 34
        self.font_size = 10
        self.zoomed_icon_size = 52
        self.label = '%s %s' % (obj['start'].split('T')[0], obj["label"])
        self.description = obj["description"]
        self.words = obj["words"]
        self.names = obj["names"]
        self.start = obj["start"]
        self.end = obj["end"]
        self.url = obj["url"]
        self.hangout = obj["hangout"]
        dict.update(self, vars(self))

    def __hash__(self):
        return hash(self.uid)

    def is_related_item(self, other):
        if other.kind != "contact":
            return False
        for name in self.names:
            if name == other.email:
                return True
        return False

    def is_duplicate(self, duplicates):
        key = "calendar - %s" % ' '.join(sorted(word for word in self.words if not stopwords.is_stopword(word)))
        if key in duplicates:
            self.mark_duplicate()
            return True
        duplicates.add(key)
        return False

    @classmethod
    def deserialize(cls, obj):
        try:
            return CalendarNode(obj)
        except Exception as e:
            logger.error('Cannot deserialize:' + e)
            for k,v in obj.items():
                logger.error('%s: %s' % (k, v))
            raise


def render(args):
    return "<p><a href=%s>Open in Calendar</a>" % args.get("url", "calendar.google.com")


def delete_all():
    pass


def load():
    Calendar.singleton.load()


def poll():
    load()


def deserialize(obj):
    return CalendarNode(obj)


settings['calendar/can_load_more'] = True
settings['calendar/pending'] = True
get_status = Calendar.get_status

Calendar.singleton = Calendar()


def cleanup():
    pass

if __name__ == '__main__':
    Calendar.singleton.load()

