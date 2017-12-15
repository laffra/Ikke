import importers
import logging
import pkgutil
import time
import threading

from importers import download

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
        for n in range(POLL_SLEEP_INTERVAL_SECONDS):
            time.sleep(1)
            if not self.running:
                break

    def poll(self):
        if self.running:
            try:
                self.importer.poll()
                logging.info('Polling %s' % self.importer.__name__)
            except Exception as e:
                logging.error('POLLER: Error polling ', self.importer.__name__, e)

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
