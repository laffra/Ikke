import datetime
import re

from stopwords import is_stopword, remove_stopwords
from storage import Storage
import pubsub
import memory

from importers import INITIAL_DAYS_LOAD, browser
from importers import contact
from importers import download
from importers import file
from importers import gmail
import installer
import logging
import graph
import poller
from preferences import ChromePreferences
from settings import settings
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen
import jinja2
import json
import os
import subprocess
import sys
import traceback
import threading
import utils

import pynsights

logger = logging.getLogger('server')

PORT_NUMBER = 1964
SERVER_ADDRESS = '127.0.0.1'


class Server(BaseHTTPRequestHandler):
    jinja2_env = jinja2.Environment(
        loader = jinja2.FileSystemLoader(os.path.join(utils.INSTALL_FOLDER, 'html'))
    )
    graphs = {}
    path = ''
    args = {}
    preferences = ChromePreferences()

    def do_GET(self):
        routes = {
            '/': self.get_index,
            '/clear': self.clear,
            '/stopclear': self.stop_deleting,
            '/status': self.status,
            '/load': self.load,
            '/stopload': self.stop_loading,
            '/get_related_items': self.get_related_items,
            '/extensions': self.extensions,
            '/get': self.get_resource,
            '/get_image': self.get_image,
            '/render': self.render,
            '/open': self.open_local,
            '/settings': self.settings,
            '/settings_set': self.settings_set,
            '/settings_get': self.settings_get,
            '/projects': self.projects,
            '/jquery.js': self.get_jquery,
            '/search': self.search,
            '/graph': self.get_graph,
            '/poll': self.poll,
            '/favicon.ico': self.favicon,
        }
        logger.debug('GET %s' % self.path)
        self.parse_args()
        routes.get(self.path, self.get_file)()

    def log_message(self, format, *args):
        message = format % args
        if not 'search_poll' in message:
            logger.debug(message)

    def parse_args(self):
        try:
            index = self.path.index('?')
            self.args = parse_qs(self.path[index + 1:])
            for k,v in self.args.items():
                self.args[k] = v[0] if len(v) == 1 else v
            self.path = self.path[:index]
        except ValueError:
            self.args = {}

    def settings(self):
        pynsights.annotate("[settings]")
        html = self.jinja2_env.get_template('settings.html').render({
            'memory': memory.usage(human=True),
            'location': utils.INSTALL_FOLDER,
            'kinds': graph.ALL_ITEM_KINDS[1:],
            'can_load_more': { kind: Storage.can_load_more(kind) for kind in graph.ALL_ITEM_KINDS[1:]},
            'can_delete': { kind: Storage.can_delete(kind) for kind in graph.ALL_ITEM_KINDS[1:]},
        })
        self.respond(html)
        memory.check(memory.GB/2)

    def settings_set(self):
        key = self.args["key"]
        value = self.args["value"]
        settings[key] = value
        self.respond("Ikke settings: set %s to '%s'" % (key, value))

    def settings_get(self):
        self.respond(settings[self.args["key"]])

    def projects(self):
        data = [
            "Personal",
            "Work",
            {
                "id" : "history",
                "text" : "History",
                "state" : { "opened" : True },
                "children" : [
                    {
                        "text": self.args["q"],
                        "state" : { "selected" : True },
                    },
                ]
            }
        ]
        self.respond(json.dumps(data))

    def respond(self, html, content_type=None):
        self.send_response(200)
        if content_type:
            self.send_header('Content-type', content_type)
        self.end_headers()
        try:
            message = bytes(html, 'utf8')
        except:
            message = html
        try:
            self.wfile.write(message)
        except TypeError:
            pass # ignore
        except Exception as e:
            logger.error('Client went away: %s: %s' % (type(e), e))

    def get_index(self):
        html = self.jinja2_env.get_template('index.html').render({
            'query': self.args.get('q', ''),
            'kinds': graph.ALL_ITEM_KINDS,
            'kinds_string': repr(graph.ALL_ITEM_KINDS),
            'account': self.preferences.get_account_info(),
        })
        logger.info(self.preferences.get_account_info())
        self.respond(html)

    def clear(self):
        kind = self.args.get('kind', '')
        logger.info('Clearing all history for %s' % kind)
        if Storage.delete_all(kind):
            self.respond('OK')

    def stop_deleting(self):
        Storage.stop_deleting(self.args['kind'])
        self.respond('OK')

    def status(self):
        self.respond(json.dumps(Storage.get_status()))

    def search(self):
        query = self.args.get('q', '')
        pynsights.annotate("[search]")
        email = self.args['email']
        settings['query'] = query
        duration = self.args.get('duration', 'year')
        logger.info('search %s %s %s' % (email, duration, query))
        self.graphs[query] = graph.Graph(email, query, duration)
        self.respond('OK')

    def stop_loading(self):
        Storage.stop_loading(self.args['kind'])
        self.respond('OK')

    def load(self):
        Storage.load(self.args['kind'])
        self.respond('OK')
        memory.check(memory.GB/2)

    def poll(self):
        poller.poll()

    def get_graph(self):
        query = self.args.get('q')
        pynsights.annotate("[graph]")
        keep_duplicates = self.args.get('d', '0') == '1'
        kind = self.args['kind']
        logger.info('get graph for %s: %s', kind, query)
        graph = self.graphs[query].get_graph(kind, keep_duplicates)
        logger.debug("Graph: %s" % json.dumps(graph, indent=4))
        self.respond(json.dumps(graph))

    def favicon(self):
        self.args["path"] = 'icons/favicon.ico'
        return self.get_resource()

    def get_resource(self):
        path = os.path.join(utils.INSTALL_FOLDER, 'html', self.args['path'])
        self.respond(self.load_resource(path, 'rb'))

    def get_image(self):
        filename = self.args['path']
        if not "/" in filename:
            filename = os.path.join(filename, self.args.get("filename", "No filename in %s" % json.dumps(self.args)))
        path = os.path.join(utils.FILE_DIR, filename)
        self.respond(self.load_resource(path, 'rb'))

    def render(self):
        pynsights.annotate("[render]")
        try:
            logger.info("render %s" % json.dumps(self.args, indent=4))
            handler = Storage.get_handler(self.args["kind"])
            self.respond('<html>%s<p>Args:<pre>%s</pre>' % (
                handler.render(self.args),
                json.dumps(self.args, indent=4),
            ))
        except:
            msg = 'Cannot render: %s' % traceback.format_exc()
            logging.error(msg)
            self.respond(msg)

    def get_jquery(self):
        self.respond(self.load_resource('jquery.js', 'rb'))

    def extensions(self):
        html = self.jinja2_env.get_template('extensions.html').render({
            'location': os.path.join(utils.INSTALL_FOLDER, 'extension')
        })
        self.respond(html)

    def load_items(self):
        items = Storage.search_file('"%s"' % self.args['uid'])
        for n, item in enumerate(items):
            if 'path' in item and os.path.exists(item['path']):
                path = os.path.realpath(item['path'])
                url = 'file://%s' % path
                import webbrowser
                webbrowser.open(url)
        html = '<html><script></script></html>'
        self.respond(html)

    def open_local(self):
        path = os.path.join(utils.FILE_DIR, self.args["path"])
        logger.info("Open %s" % path)
        subprocess.call(['open', path])

    def get_related_items(self):
        browser.save_image(
            self.args.get('url', ''),
            self.args.get('title', ''),
            self.args.get('image', ''),
            self.args.get('favicon', ''),
            self.args.get('selection', ''),
            self.args.get('essence', ''),
            self.args.get('keywords', ''),
            float(self.args.get('timestamp', datetime.datetime.utcnow().timestamp()))
        )
        self.notify_related()
        memory.check(memory.GB/2)

    def notify_related(self):
        query = re.sub("[^A-Za-z_0-9]", " ", self.args.get('essence', self.args.get('title', '')))
        words = [word for word in query.split() if not is_stopword(word)]
        query = " ".join(words)
        days_to_search = 365
        results = Storage.search(query, days_to_search)
        if not results:
            for word in words:
                results += Storage.search(word, days_to_search)
        results = filter(lambda result: result.kind != "time", results)
        results = sorted(results, key=lambda result: -result.timestamp)
        logger.info("Found %d related results" % len(results))
        from classify import remove_duplicates
        results = remove_duplicates(results, False)
        results = results[:30]
        results = sorted(results, key=lambda result: result.kind, reverse=True)
        pubsub.notify("related", query, results)
        self.respond(json.dumps({
            "query": query,
            "items": results,
        }))

    def get_file(self):
        try:
            payload = self.load_resource(self.path[1:])
            try:
                payload = bytes(payload, 'utf8')
            except:
                pass
            self.respond(payload)
        except Exception as e:
            logger.debug('Fail on %s: %s' % (self.path, e))
            self.send_response(404)

    def load_resource(self, filename, format='r'):
        dirname = os.path.dirname(filename).replace(' ', '+')
        basename = os.path.basename(filename)
        filename = os.path.join(dirname, basename)
        path = os.path.join(utils.INSTALL_FOLDER, os.path.join('html', filename))
        with open(path, format) as fp:
            return fp.read()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


def runServerInBackground(server):
    poller.start()
    server.serve_forever()
    poller.stop()
    for kind in graph.ALL_ITEM_KINDS[1:]:
        Storage.stop_loading(kind)

def startServer(handleRelated):
    logging.basicConfig(level=logging.INFO)
    installer.install()
    port = settings.get('port', PORT_NUMBER)
    threaded_server = ThreadedHTTPServer(('localhost', port), Server)
    threaded_server.handleRelated = handleRelated

    settings['port'] = port
    if settings['browser/count'] < 100:
        threading.Thread(target=lambda: Storage.load('browser')).start()
    threading.Thread(target=lambda: runServerInBackground(threaded_server)).start()

if __name__ == '__main__':
    if "clear" in sys.argv:
        print("Clearing...")
        settings.clear()
    else:
        def handleRelated(query, relatedItems):
            print("Related:", query, len(relatedItems))
        startServer(handleRelated)
