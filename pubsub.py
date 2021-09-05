from collections import defaultdict
import logging

logger = logging.getLogger('pubsub')
handlers = defaultdict(set)

def register(event, handler):
    handlers[event].add(handler)

def unregister(event, handler):
    del handlers[event]

def notify(event, *arguments):
    logger.info("###### Notify: %s: %s" % (event, arguments))
    for handler in handlers[event]:
        handler(*arguments)