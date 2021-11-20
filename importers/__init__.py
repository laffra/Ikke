from abc import abstractmethod
from importers import contact
from settings import settings
import datetime
import logging
import storage
import sys
import pynsights

logger = logging.getLogger(__name__)

MAXIMUM_DAYS_LOAD = 20 * 365
INITIAL_DAYS_LOAD = 365
DAYS_LOAD = 31
DAYS_TO_LOOK_INTO_THE_FUTURE = 14

class Importer():
    def __init__(self):
        self.kind = ""


    def update_days(self, days):
        self.update_timestamp((datetime.datetime.utcnow() - datetime.timedelta(days)).timestamp())


    def update_timestamp(self, timestamp):
        key_before = '%s/timestamp_before' % self.kind
        settings[key_before] = max(timestamp, settings.get(key_before, 0))
        key_after = '%s/timestamp_after' % self.kind
        settings[key_after] = min(timestamp, settings.get(key_after, sys.maxsize))


    @abstractmethod
    def load_items(self, days, start):
        pass

    @pynsights.trace
    def load(self):
        try:
            settings['%s/loading' % self.kind] = True

            # load recent items added since we last checked
            self.load_items_before(self.get_days(datetime.datetime.utcnow().timestamp()) - DAYS_TO_LOOK_INTO_THE_FUTURE)

            # load olders items and fill up the index
            days_after = self.get_days(settings['%s/timestamp_after' % self.kind]) + 1
            if days_after < MAXIMUM_DAYS_LOAD:
                self.load_items_before(days_after)
        finally:
            settings['%s/loading' % self.kind] = False
            contact.cleanup()
            storage.Storage.log_search_stats()

    def get_days(self, timestamp):
        delta = datetime.datetime.utcnow() - datetime.datetime.fromtimestamp(timestamp)
        return delta.days

    def load_items_before(self, days_before):
        days = DAYS_LOAD if '%s/count' % self.kind in settings else INITIAL_DAYS_LOAD
        last_day_before = self.get_days(settings.get('%s/timestamp_before' % self.kind, datetime.datetime.utcnow().timestamp()))
        days_after = min(last_day_before, days_before + days) if days_before <= last_day_before else days_before + days
        days_after = max(1, days_after)
        pynsights.annotate("[%s %d/%d]" % (
            self.__class__.__name__,
            days_after,
            days_before
        ))
        self.load_items(days_after, days_before)

    @classmethod
    def get_status(cls, kind, label):
        count = settings['%s/count' % kind]
        before = datetime.datetime.fromtimestamp(settings['%s/timestamp_before' % kind]).date()
        after = datetime.datetime.fromtimestamp(settings['%s/timestamp_after' % kind]).date()
        details = ' - [%s - %s]' % (after, before) if count else ""
        return '%d %s%s %s' % (count, label, "" if count == 1 else "s", details)



