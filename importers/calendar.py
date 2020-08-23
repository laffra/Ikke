from importers import contact
from importers import file
from importers import google_apis
from settings import settings

import base64
import datetime
import dateparser
import htmlparser
import json
import logging
import os
import stopwords
import storage
import time
import urllib
import utils

MAXIMUM_DAYS_LOAD = 365
logger = logging.getLogger(__name__)
service = google_apis.get_google_service("calendar", "v3")


class Calendar():
    singleton = None

    def __init__(self):
        self.error = None

    @classmethod
    def get_body(cls, event):
        return event

    @classmethod
    def load_events(cls, count, start=0):
        try:
            logger.info('Loading calendar events for the 1ast %s days - %s days back' % (count, start))

            day = start
            settings['calendar/count'] = 0
            while settings['calendar/loading'] and day < count:
                try:
                    before = datetime.datetime.utcnow() + datetime.timedelta(days=1) - datetime.timedelta(days=day)
                    after = before - datetime.timedelta(days=2)
                    result = service.events().list(
                        calendarId='primary',
                        timeMin=after.isoformat() + "Z",
                        timeMax=before.isoformat() + "Z"
                    ).execute()
                    cls.parse_events(result.get('items', []))
                    logger.info(cls.get_status())
                except Exception as e:
                    logger.error('Cannot load message for day %d: %s' % (day, e))
                    import traceback
                    traceback.print_exc()
                    return
                else:
                    settings['calendar/days'] = max(day, settings['calendar/days'])
                    day += 1
        finally:
            storage.Storage.load_stats()

    @classmethod
    def get_names(cls, event):
        return list(set([attendee["email"] for attendee in event.get("attendees", [])] + [event["organizer"]["email"]]))

    @classmethod
    def parse_events(cls, events):
        for event in events:
            start = event.get("start")
            if not start or not "dateTime" in start:
                continue
            when = dateparser.parse(start["dateTime"])
            timestamp = when.timestamp()
            storage.Storage.add_data({
                "kind": "calendar",
                "uid": event["id"],
                "label": event.get("summary", ""),
                "description": event.get("description", ""),
                "words": stopwords.remove_stopwords("%s %s" % (event.get("summary", ""), event.get("description", ""))),
                "names": cls.get_names(event),
                "url": event["htmlLink"],
                "start": start["dateTime"],
                "end": event["end"]["dateTime"],
                "timestamp": timestamp,
                "hangout": event.get("hangoutLink", "")
            })
            settings['calendar/count'] += 1

    @classmethod
    def get_status(cls):
        count = settings['calendar/count']
        days = settings['calendar/days']
        if settings["calendar/loading"]:
            return 'Loaded %d events' % count
        youngest = datetime.datetime.fromtimestamp(settings['calendar/youngest']).date()
        oldest = datetime.datetime.fromtimestamp(settings['calendar/oldest']).date()
        return '%d calendar events loaded up to %s days between %s and %s' % (count, days, oldest, youngest)

    @classmethod
    def load(cls, days_count=1, days_start=0):
        # type (int,bool) -> None
        if 'calendar/lastload' not in settings:  # this is the very first load
            days_count = MAXIMUM_DAYS_LOAD
        settings['calendar/lastload'] = time.time()
        settings['calendar/loading'] = True
        settings['calendar/count'] = 0

        timestamp_youngest = settings['calendar/youngest']
        days_count_youngest = 1 + (datetime.datetime.now() - datetime.datetime.fromtimestamp(timestamp_youngest)).days
        cls.load_events(days_count, 0)

        timestamp_oldest = settings['calendar/oldest']
        days_count_oldest = (datetime.datetime.now() - datetime.datetime.fromtimestamp(timestamp_oldest)).days - 1
        # cls.load_messages(days_count, days_count_oldest)

        settings['calendar/loading'] = False
        storage.Storage.stats.clear()


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
        self.label = obj["label"]
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
        return False

    def get_related_items(self):
        return []

    def is_duplicate(self, duplicates):
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
    settings['calendar/days'] = 0


def load():
    days = settings['calendar/days']
    Calendar.load(days + 365, days)


def poll():
    Calendar.load(1, 0)


def deserialize(obj):
    return CalendarNode(obj)


settings['calendar/can_load_more'] = True
settings['calendar/pending'] = True
get_status = Calendar.get_status


def cleanup():
    pass

if __name__ == '__main__':
    Calendar.load()

