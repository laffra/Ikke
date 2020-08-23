import importers
import logging
import pkgutil
import storage
import time
import threading

from importers import download

logger = logging.getLogger(__name__)

POLL_SLEEP_INTERVAL_SECONDS = 600

class Worker(threading.Thread):

    def __init__(self, importer):
        super(Worker, self).__init__()
        self.importer = importer
        self.running = True

    def run(self):
        while self.running:
            self.sleep()
            self.poll()

    def sleep(self):
        logger.info("Sleeping for %d seconds" % POLL_SLEEP_INTERVAL_SECONDS)
        for n in range(POLL_SLEEP_INTERVAL_SECONDS):
            time.sleep(1)
            if not self.running:
                break

    def poll(self):
        logging.info('Poll running=%s' % self.running)
        if self.running:
            logging.info('Polling importers')
            try:
                self.importer.poll()
                logging.debug('Polling %s' % self.importer.__name__)
            except Exception as e:
                logging.error('POLLER: Error polling %s: %s' % (self.importer.__name__, e))
            logging.info('Polling Storage')
            storage.Storage.poll()

    def stop(self):
        self.running = False

workers = [
    Worker(getattr(importers, name))
    for _, name, _ in pkgutil.iter_modules(['importers'])
    if hasattr(importers, name)
]


def poll():
    for worker in workers:
        worker.poll()


def start():
    for worker in workers:
        worker.start()


def stop():
    for worker in workers:
        worker.stop()
