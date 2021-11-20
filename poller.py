import importers
import logging
import pkgutil
import storage
import time
import threading
import memory

from importers import download

logger = logging.getLogger(__name__)

POLL_SLEEP_INTERVAL_SECONDS = 600
POLL_SLEEP_INCREMENT_SECONDS = 60

workers = []

class Worker(threading.Thread):

    def __init__(self, importer):
        super(Worker, self).__init__()
        self.importer = importer
        self.running = True
        self.index = len(workers)
        workers.append(self)

    def run(self):
        delay = POLL_SLEEP_INCREMENT_SECONDS * self.index
        logger.info("Staggered start %s for %d seconds" % (self.importer.__name__, delay))
        time.sleep(delay)
        while self.running:
            self.sleep()
            self.poll()
            memory.check(memory.GB/2)

    def sleep(self):
        delay = POLL_SLEEP_INTERVAL_SECONDS
        logger.info("Sleeping %s for %d seconds" % (self.importer.__name__, delay))
        for n in range(delay):
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
